import { useState, useCallback, useEffect, useRef } from "react"

export interface StoredMessage {
  id: string
  type: "human" | "ai"
  text: string
}

export interface Conversation {
  id: string
  title: string
  messages: StoredMessage[]
  createdAt: number
  updatedAt: number
}

const STORAGE_KEY = "sql-assistant-conversations"
const MAX_TITLE_LEN = 40

function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
}

function loadAll(): Conversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function inferTitle(messages: StoredMessage[]): string {
  const first = messages.find((m) => m.type === "human")
  if (!first) return "New conversation"
  const text = first.text.trim().replace(/\n/g, " ")
  return text.length > MAX_TITLE_LEN
    ? text.slice(0, MAX_TITLE_LEN) + "…"
    : text
}

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>(() =>
    loadAll(),
  )
  const [activeId, setActiveId] = useState<string | null>(null)
  const syncTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Debounced sync to localStorage
  useEffect(() => {
    if (syncTimer.current) clearTimeout(syncTimer.current)
    syncTimer.current = setTimeout(() => {
      saveAll(conversations)
    }, 300)
    return () => {
      if (syncTimer.current) clearTimeout(syncTimer.current)
    }
  }, [conversations])

  const createConversation = useCallback(() => {
    const id = generateId()
    const conv: Conversation = {
      id,
      title: "New conversation",
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }
    setConversations((prev) => [conv, ...prev])
    setActiveId(id)
    return id
  }, [])

  const deleteConversation = useCallback((id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id))
    setActiveId((prev) => (prev === id ? null : prev))
  }, [])

  const renameConversation = useCallback((id: string, title: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title, updatedAt: Date.now() } : c)),
    )
  }, [])

  const saveMessages = useCallback(
    (id: string, messages: StoredMessage[]) => {
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== id) return c
          const title = c.title === "New conversation" ? inferTitle(messages) : c.title
          return { ...c, messages, title, updatedAt: Date.now() }
        }),
      )
    },
    [],
  )

  const activeConversation =
    conversations.find((c) => c.id === activeId) ?? null

  return {
    conversations,
    activeId,
    activeConversation,
    setActiveId,
    createConversation,
    deleteConversation,
    renameConversation,
    saveMessages,
  }
}

function saveAll(convs: Conversation[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(convs))
}