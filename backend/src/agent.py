from pathlib import Path
from typing import Any

from langchain.agents import create_agent, AgentState
from langchain.tools import tool
from langchain_openrouter import ChatOpenRouter

from langgraph.runtime import Runtime
from langchain.agents.middleware import before_model


from langchain.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES 

import duckdb

model = ChatOpenRouter(
    model="deepseek/deepseek-v4-flash",
    openrouter_provider={"data_collection": "deny"})



@before_model
def trim_memory(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """Keep only the last few messages to fit context window."""
    RECENT_COUNT = 10
    messages = state["messages"]
    tools_used = sum(msg.type == "tool" for msg in messages)
    if len(messages) <= RECENT_COUNT:
        return None  # No changes needed

    first_msg = messages[0]
    recent_messages = messages[-RECENT_COUNT:] if (len(messages)+tools_used) % 2 == 0 else messages[-(RECENT_COUNT + 1):]
    new_messages = [first_msg] + recent_messages

    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *new_messages
        ]
    }

@tool
def query_db(sql: str) -> str:
    """Input to this tool is a detailed and correct SQL query, output is a result from the database.
    If the query is not correct, an error message will be returned.
    If an error is returned, rewrite the query, check the query, and try again.
    If you encounter an issue with Unknown column 'xxxx' in 'field list', use the schemas provided again."""
    with duckdb.connect("demo.db") as con:
        try:
            result = con.execute(sql).df().to_string(index=False)
            return result
        except Exception as e:
            return f"Error occurred: {e}"

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "ocp_schema.md"
SCHEMA = SCHEMA_PATH.read_text() if SCHEMA_PATH.exists() else ""

system_prompt = f"""Tu es un assistant SQL spécialisé pour les données de production
et maintenance industrielle (cas d'étude : phosphates, Maroc).
Tu aides à interroger une base DuckDB de données de production et maintenance.

## Schéma de la base
Le schéma complet est fourni ci-dessous. Ne fais PAS de SHOW TABLES ou DESCRIBE.
Utilise exactement ces noms de tables et colonnes dans tes requêtes.

{SCHEMA}

## Règles

1. **Langue** — Pose des questions en français, réponds en français.

2. **Requêtes** — Génère du SQL DuckDB valide. Limite à 10 résultats sauf si
   l'utilisateur demande un nombre précis. Utilise ORDER BY pour montrer les
   résultats les plus pertinents.

3. **Colonnes** — Ne SELECT * que pour explorer une table inconnue. Sinon,
   ne requête que les colonnes pertinentes.

4. **Sécurité** — JAMAIS de DML (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE).
   Lecture seule uniquement.

5. **Erreurs** — Si une requête échoue, analyse l'erreur, corrige la syntaxe
   et réessaie. Maximum 3 tentatives.

6. **Format de réponse** — Structure tes réponses ainsi :
   - La question posée
   - La requête SQL exécutée (dans un bloc code)
   - Les résultats chiffrés (pas de tableau brut, une phrase concise)
   - La source : quelle table et combien de lignes consultées
   - Si applicable, une tendance ou insight

7. **Précision** — Donne des valeurs exactes avec leurs unités
   (heures, tonnes, etc.). Ne dis pas "environ".

8. **Colonnes** — Les noms sont en français ou anglais. Utilise-les tels quels.
"""


agent = create_agent(model=model,
                     tools=[query_db],
                     system_prompt=system_prompt,
                     middleware=[trim_memory],
                     )

# ── Title generator ────────────────────────────────────────────────
# Lightweight agent for conversation naming, used via stateless run
# from the frontend after the first message of a new thread.

title_system_prompt = """Tu génères des titres courts pour des conversations.

À partir du premier message d'un utilisateur, génère un titre en français
qui résume le sujet de la conversation.

Règles :
- 3 à 6 mots maximum
- En français
- Pas de ponctuation finale
- Pas de guillemets
- Ne donne RIEN d'autre que le titre
- Exemple : "Temps d'arrêt handling" au lieu de "Quel est le temps d'arrêt moyen dans le handling ?"
- Le titre doit être concis et informatif"""

title_generator = create_agent(
    model=model,
    system_prompt=title_system_prompt,
)
