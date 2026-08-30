# Schéma DuckDB — Production & Maintenance Industrielle

## Table: `downtime` (99 lignes)
Description: Arrêts de production — durée, cause, équipement concerné.

| Colonne | Type | Description | NA |
|---------|------|-------------|----|
| `down_time_start` | TIMESTAMP | Début de l'arrêt | 2 |
| `down_time_end` | TIMESTAMP | Fin de l'arrêt | 8 |
| `area` | VARCHAR | Zone (ex: Handling, Production) | 0 |
| `departement` | VARCHAR | Département (Electrique, Mécanique) | 21 |
| `equipement_name` | VARCHAR | Nom de l'équipement | 14 |
| `description` | VARCHAR | Description de la panne | 7 |
| `action` | VARCHAR | Action corrective | 44 |
| `time_usage_allocation` | DOUBLE | Allocation temps | 99 |
| `equipment_type` | DOUBLE | Type d'équipement | 99 |
| `cause` | DOUBLE | Code cause | 99 |
| `reason` | VARCHAR | Raison textuelle | 94 |
| `created` | TIMESTAMP | Date création entrée | 0 |
| `target_hours` | BIGINT | Heures cibles | 0 |
| `duration` | DOUBLE | Durée de l'arrêt | 99 |
| `other_loss_category` | DOUBLE | Catégorie de perte | 99 |
| `item_type` | VARCHAR | Type d'élément | 0 |
| `path` | VARCHAR | Chemin source | 0 |

## Table: `downtime_handling` (144 lignes)
Description: Arrêts de manutention — équipement, durée, type d'intervention.

| Colonne | Type | Description | NA |
|---------|------|-------------|----|
| `heure_debut` | TIMESTAMP | Début de l'arrêt | 0 |
| `heure_fin` | TIMESTAMP | Fin de l'arrêt | 0 |
| `equipement` | VARCHAR | Équipement (ex: RP140, T13, TM) | 2 |
| `interne_externe` | VARCHAR | Interne ou Externe | 0 |
| `description` | VARCHAR | Description de l'arrêt | 0 |
| `created` | TIMESTAMP | Date de création | 0 |
| `cree_par` | VARCHAR | Créé par (ex: opérateur) | 0 |
| `type` | VARCHAR | Type (destockage, stockage) | 0 |
| `duration` | DOUBLE | Durée en heures | 0 |
| `period` | VARCHAR | Période (Nuit, Jour) | 0 |
| `categorie` | VARCHAR | Catégorie | 118 |
| `id` | BIGINT | Identifiant unique | 0 |
| `time_usage_allocation` | DOUBLE | Allocation temps | 144 |
| `item_type` | VARCHAR | Type d'élément | 0 |
| `path` | VARCHAR | Chemin source | 0 |

## Table: `handling_storage` (55 lignes)
Description: Opérations de stockage/déstockage — qualité, durée, quantité.

| Colonne | Type | Description | NA |
|---------|------|-------------|----|
| `id` | BIGINT | Identifiant unique | 0 |
| `qualite` | VARCHAR | Qualité produit (C3, BT, PS;#C3) | 2 |
| `heure_debut` | TIMESTAMP | Début de l'opération | 0 |
| `heure_fin` | TIMESTAMP | Fin de l'opération | 0 |
| `mode_stockage` | VARCHAR | Mode (ex: Chevron) | 29 |
| `type` | VARCHAR | Type (stockage, destockage) | 0 |
| `duration` | DOUBLE | Durée en heures | 0 |
| `stockage` | BIGINT | Quantité stockée | 0 |
| `cree_par` | VARCHAR | Créé par | 0 |
| `period` | VARCHAR | Période (Nuit, Jour) | 0 |
| `numero_tas` | DOUBLE | Numéro du tas | 29 |
| `numero_tas_tas_text` | VARCHAR | Texte du tas (ex: MPII) | 29 |
| `numero_tas_id` | DOUBLE | ID du tas | 29 |
| `item_type` | VARCHAR | Type d'élément | 0 |
| `totalisateur_fin` | DOUBLE | Totalisateur fin | 55 |
| `totalisateur_debut` | DOUBLE | Totalisateur début | 55 |