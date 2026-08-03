import { useCallback, useEffect, useRef, useState } from "react"
import Chat from "./Chat.tsx"
import ConversationSidebar from "./components/conversation-sidebar.tsx"
import {
  SidebarProvider,
  SidebarInset,
} from "@/components/ui/sidebar"
import { useConversations } from "@/hooks/use-conversations"

export default function App() {
  const {
    conversations,
    activeId,
    setActiveId,
    createConversation,
    deleteConversation,
    renameConversation,
    saveMessages,
  } = useConversations()

  // Key to force Chat remount when switching conversations
  const [chatKey, setChatKey] = useState<string>("new")

  // Create first conversation on mount if none exists
  const hasInit = useRef(false)
  useEffect(() => {
    if (hasInit.current) return
    hasInit.current = true
    if (!activeId && conversations.length === 0) {
      createConversation()
    } else if (!activeId && conversations.length > 0) {
      setActiveId(conversations[0].id)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleNew = useCallback(() => {
    createConversation()
    setChatKey("new-" + Date.now())
  }, [createConversation])

  const handleSelect = useCallback(
    (id: string) => {
      setActiveId(id)
      setChatKey(id)
    },
    [setActiveId],
  )

  const handleDelete = useCallback(
    (id: string) => {
      const isActive = id === activeId
      deleteConversation(id)
      if (isActive) {
        const remaining = conversations.filter((c) => c.id !== id)
        if (remaining.length > 0) {
          setActiveId(remaining[0].id)
          setChatKey(remaining[0].id)
        } else {
          setChatKey("new-" + Date.now())
        }
      }
    },
    [activeId, deleteConversation, setActiveId, conversations],
  )

  const handleSaveMessages = useCallback(
    (messages: Array<{ id: string; type: "human" | "ai"; text: string }>) => {
      if (activeId) {
        saveMessages(activeId, messages)
      }
    },
    [activeId, saveMessages],
  )

  const handleTitleGenerated = useCallback(
    (title: string) => {
      if (activeId) {
        renameConversation(activeId, title)
      }
    },
    [activeId, renameConversation],
  )

  return (
    <SidebarProvider defaultOpen={true}>
      <ConversationSidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={handleSelect}
        onNew={handleNew}
        onDelete={handleDelete}
      />
      <SidebarInset className="h-dvh overflow-hidden">
        <Chat
          key={chatKey}
          onMessagesChange={handleSaveMessages}
          onTitleGenerated={handleTitleGenerated}
        />
      </SidebarInset>
    </SidebarProvider>
  )
}