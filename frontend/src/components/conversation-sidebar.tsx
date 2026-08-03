import { type Conversation } from "@/hooks/use-conversations"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar"
import { PlusIcon, Trash2Icon, MessageSquareTextIcon } from "lucide-react"

interface Props {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
}

function formatDate(ts: number): string {
  const d = new Date(ts)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) {
    return d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })
  }
  if (days === 1) return "Hier"
  if (days < 7) return `Il y a ${days} jours`
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" })
}

export default function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
}: Props) {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              onClick={onNew}
              className="h-10 gap-2 data-open:bg-sidebar-accent"
              tooltip="Nouvelle conversation"
            >
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-primary text-sidebar-primary-foreground">
                <PlusIcon className="size-4" />
              </div>
              <span className="truncate font-semibold">Nouvelle conversation</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarSeparator />

      <SidebarContent>
        {conversations.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-4 py-8 text-center text-xs text-muted-foreground">
            <MessageSquareTextIcon className="size-8 opacity-30" />
            <p>Aucune conversation</p>
          </div>
        ) : (
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                {conversations.map((conv) => (
                  <SidebarMenuItem key={conv.id}>
                    <SidebarMenuButton
                      isActive={conv.id === activeId}
                      onClick={() => onSelect(conv.id)}
                      className="group/menu-button"
                      tooltip={conv.title}
                    >
                      <MessageSquareTextIcon className="size-4 shrink-0" />
                      <div className="flex min-w-0 flex-1 flex-col">
                        <span className="truncate text-sm">{conv.title}</span>
                        <span className="truncate text-xs text-muted-foreground">
                          {formatDate(conv.updatedAt)}
                        </span>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onDelete(conv.id)
                        }}
                        className="ml-auto flex size-5 items-center justify-center rounded-md opacity-0 transition-opacity hover:bg-sidebar-accent group-hover/menu-button:opacity-100"
                        aria-label="Supprimer"
                      >
                        <Trash2Icon className="size-3.5 text-muted-foreground hover:text-destructive" />
                      </button>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter>
        <div className="px-3 py-2">
          <p className="text-xs text-muted-foreground/60">
            Ctrl+B pour basculer
          </p>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}