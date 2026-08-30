import { type FormEvent, useEffect, useRef, useState } from "react"
import { useStream } from "@langchain/react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import {
  Message,
  MessageAvatar,
  MessageContent,
} from "@/components/ui/message"
import {
  MessageScroller,
  MessageScrollerProvider,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerViewport,
  MessageScrollerButton,
} from "@/components/ui/message-scroller"
import { SidebarTrigger } from "@/components/ui/sidebar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SendIcon,
  FactoryIcon,
  SparklesIcon,
  BarChart3Icon,
  WrenchIcon,
  ChevronDownIcon,
  DatabaseIcon,
  CheckIcon,
} from "lucide-react"
import type { StoredMessage } from "@/hooks/use-conversations"

interface Props {
  onMessagesChange: (messages: StoredMessage[]) => void
  onTitleGenerated?: (title: string) => void
}

const SUGGESTIONS = [
  {
    icon: BarChart3Icon,
    label: "Average downtime",
    text: "What is the average downtime in the handling area?",
  },
  {
    icon: WrenchIcon,
    label: "Top failures",
    text: "Show the 5 pieces of equipment with the most failures",
  },
  {
    icon: SparklesIcon,
    label: "Performance",
    text: "What is the equipment availability this month?",
  },
]

const DATABASES = [
  { id: "auto", label: "Auto" },
  { id: "handling", label: "Handling" },
  { id: "ship-loading", label: "Ship Loading" },
  { id: "rail", label: "Rail" },
  { id: "belt-conveyor", label: "Belt Conveyor" },
]

function DatabaseSelector({
  value,
  onChange,
  disabled,
}: {
  value: string
  onChange: (id: string) => void
  disabled: boolean
}) {
  const current = DATABASES.find((d) => d.id === value) ?? DATABASES[0]

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            type="button"
            disabled={disabled}
            className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-muted-foreground ring-sidebar-ring outline-hidden transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-2 disabled:opacity-40"
          >
            <DatabaseIcon className="size-3.5" />
            <span className="hidden sm:inline">{current.label}</span>
            <ChevronDownIcon className="size-3" />
          </button>
        }
      />
      <DropdownMenuContent align="start" sideOffset={6}>
        {DATABASES.map((db) => (
          <DropdownMenuItem key={db.id} onSelect={() => onChange(db.id)}>
            <span className="flex-1">{db.label}</span>
            {db.id === value && (
              <CheckIcon className="size-3.5 text-primary" />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function ChatInput({
  input,
  setInput,
  isLoading,
  handleSubmit,
  database,
  onDatabaseChange,
  large = false,
}: {
  input: string
  setInput: (v: string) => void
  isLoading: boolean
  handleSubmit: (e: FormEvent) => Promise<void>
  database: string
  onDatabaseChange: (id: string) => void
  large?: boolean
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (large && inputRef.current) inputRef.current.focus()
  }, [large])

  return (
    <form onSubmit={handleSubmit} className={large ? "w-full max-w-2xl" : ""}>
      <div
        className={
          large
            ? "flex items-center gap-2 rounded-2xl border border-input bg-card shadow-lg shadow-black/5 p-2 focus-within:border-ring focus-within:ring-4 focus-within:ring-ring/15 transition-all duration-200"
            : "flex items-center gap-1.5 bg-card rounded-xl border border-input shadow-sm p-1.5 focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/10 transition-all duration-200"
        }
      >
        <DatabaseSelector
          value={database}
          onChange={onDatabaseChange}
          disabled={isLoading}
        />

        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.currentTarget.value)}
          placeholder={
            isLoading
              ? "Assistant is thinking..."
              : large
                ? "Ask a question about production data..."
                : "Ask a question..."
          }
          disabled={isLoading}
          className={
            large
              ? "flex-1 bg-transparent px-1 py-3 text-base outline-none placeholder:text-muted-foreground/40 disabled:opacity-50"
              : "flex-1 bg-transparent px-1 py-2 text-sm outline-none placeholder:text-muted-foreground/40 disabled:opacity-50"
          }
        />
        <Button
          type="submit"
          variant={input.trim() && !isLoading ? "default" : "secondary"}
          disabled={isLoading || !input.trim()}
          size={large ? "lg" : "default"}
          className={
            large
              ? "shrink-0 rounded-xl px-5"
              : "shrink-0"
          }
        >
          <SendIcon data-icon="inline-start" />
          {large ? "Send" : null}
        </Button>
      </div>
    </form>
  )
}

export default function Chat({ onMessagesChange, onTitleGenerated }: Props) {
  const [input, setInput] = useState("")
  const [database, setDatabase] = useState("auto")

  const { messages, submit, isLoading, error, client } = useStream({
    apiUrl: "http://localhost:2024",
    assistantId: "agent",
  })

  // ── Title generation on first AI response ──
  const titleGenerated = useRef(false)

  useEffect(() => {
    if (titleGenerated.current) return
    // First AI response = 2 messages (human + ai)
    if (messages.length !== 2) return
    const last = messages.at(-1)
    if (!last || last.type !== "ai") return

    titleGenerated.current = true
    const firstHuman = messages[0]
    const question =
      typeof firstHuman.content === "string"
        ? firstHuman.content
        : JSON.stringify(firstHuman.content)

    client.runs
      .wait(null, "title-generator", {
        input: {
          messages: [{ type: "human" as const, content: question }],
        },
      })
      .then((result) => {
        const values = result as Record<string, unknown>
        const resultMessages = values.messages as Array<{ content: string }>
        const title = resultMessages?.at?.(-1)?.content
        if (title && onTitleGenerated) {
          onTitleGenerated(title.trim())
        }
      })
      .catch(() => {
        // Silently fall back to client-side truncation
      })
  }, [messages, onTitleGenerated, client])

  // Sync messages to parent for localStorage persistence
  const prevJson = useRef<string>("")
  useEffect(() => {
    if (messages.length === 0) return
    const stored: StoredMessage[] = messages.map((m) => ({
      id: m.id ?? crypto.randomUUID(),
      type: m.type === "human" ? "human" : "ai",
      text:
        typeof m.content === "string"
          ? m.content
          : JSON.stringify(m.content),
    }))
    const json = JSON.stringify(stored)
    if (json !== prevJson.current) {
      prevJson.current = json
      onMessagesChange(stored)
    }
  }, [messages, onMessagesChange])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const content = input.trim()
    if (!content || isLoading) return
    setInput("")
    // TODO: pass database to backend when endpoint supports it
    await submit({
      messages: [{ type: "human", content }],
    })
  }

  const handleSuggestion = (text: string) => {
    setInput(text)
  }

  const isEmpty = messages.length === 0 && !isLoading

  // ── Empty state: big centered landing ──
  if (isEmpty) {
    return (
      <div className="relative h-full flex flex-col items-center justify-center px-6">
        {/* Floating sidebar trigger */}
        <div className="absolute top-3 left-3">
          <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
        </div>

        {/* Logo */}
        <div className="mb-8 flex flex-col items-center gap-5">
          <div className="size-16 rounded-2xl bg-primary shadow-lg shadow-primary/20 flex items-center justify-center ring-1 ring-black/5 dark:ring-white/10">
            <span className="text-primary-foreground text-2xl font-bold tracking-tight">
              SQL
            </span>
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              SQL Assistant
            </h1>
            <p className="mt-1.5 text-sm text-muted-foreground max-w-sm">
              Query production data in natural language.
              Ask a question, the assistant translates it into
              SQL and answers with the numbers.
            </p>
          </div>
        </div>

        {/* Suggestion chips */}
        <div className="mb-8 flex flex-wrap justify-center gap-2 max-w-xl">
          {SUGGESTIONS.map((s) => (
            <button
              key={s.text}
              type="button"
              onClick={() => handleSuggestion(s.text)}
              className="inline-flex items-center gap-1.5 rounded-full border border-input bg-card px-3.5 py-1.5 text-xs font-medium text-muted-foreground shadow-sm transition-all hover:border-ring hover:bg-accent hover:text-foreground hover:shadow-md active:scale-[0.97]"
            >
              <s.icon className="size-3.5" />
              {s.label}
            </button>
          ))}
        </div>

        {/* Big input */}
        <ChatInput
          input={input}
          setInput={setInput}
          isLoading={isLoading}
          handleSubmit={handleSubmit}
          database={database}
          onDatabaseChange={setDatabase}
          large
        />
      </div>
    )
  }

  // ── Active chat: messages + bottom input ──
  const lastMessage = messages.at(-1)
  const showLoadingIndicator =
    isLoading && lastMessage?.type === "human"

  return (
    <div className="relative h-full flex flex-col">
      {/* Floating sidebar trigger */}
      <div className="absolute top-3 left-3 z-10">
        <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
      </div>

      <MessageScrollerProvider autoScroll>
        <MessageScroller className="flex-1 pt-2">
          <MessageScrollerViewport>
            <MessageScrollerContent>
              {messages.map((msg) => {
                const key = msg.id ?? msg.text.slice(0, 30)
                if (msg.type === "human") {
                  return (
                    <MessageScrollerItem key={key} scrollAnchor>
                      <Message align="end">
                        <MessageContent>
                          <Bubble variant="default" align="end">
                            <BubbleContent>
                              <p className="whitespace-pre-wrap">
                                {msg.text}
                              </p>
                            </BubbleContent>
                          </Bubble>
                        </MessageContent>
                      </Message>
                    </MessageScrollerItem>
                  )
                }
                if (msg.type === "ai") {
                  return (
                    <MessageScrollerItem key={key}>
                      <Message align="start">
                        <MessageAvatar>
                          <Avatar className="size-8">
                            <AvatarFallback className="bg-primary text-primary-foreground">
                              <FactoryIcon className="size-4" />
                            </AvatarFallback>
                          </Avatar>
                        </MessageAvatar>
                        <MessageContent>
                          <Bubble variant="secondary">
                            <BubbleContent>
                              <article className="prose prose-sm prose-neutral prose-code:bg-muted prose-code:px-1.5 prose-code:rounded prose-code:text-sm max-w-none dark:prose-invert">
                                <ReactMarkdown
                                  remarkPlugins={[remarkGfm]}
                                >
                                  {msg.text}
                                </ReactMarkdown>
                              </article>
                            </BubbleContent>
                          </Bubble>
                        </MessageContent>
                      </Message>
                    </MessageScrollerItem>
                  )
                }
                return null
              })}

              {showLoadingIndicator && (
                <MessageScrollerItem>
                  <Message align="start">
                    <MessageAvatar>
                      <Avatar className="size-8">
                        <AvatarFallback className="bg-primary text-primary-foreground">
                          <FactoryIcon className="size-4" />
                        </AvatarFallback>
                      </Avatar>
                    </MessageAvatar>
                    <MessageContent>
                      <Bubble variant="secondary">
                        <BubbleContent>
                          <div className="flex gap-1.5 py-1">
                            <span className="size-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:-0.3s]" />
                            <span className="size-2 bg-muted-foreground/40 rounded-full animate-bounce [animation-delay:-0.15s]" />
                            <span className="size-2 bg-muted-foreground/40 rounded-full animate-bounce" />
                          </div>
                        </BubbleContent>
                      </Bubble>
                    </MessageContent>
                  </Message>
                </MessageScrollerItem>
              )}

              {Boolean(error) && (
                <MessageScrollerItem>
                  <Message align="start">
                    <MessageContent>
                      <Bubble variant="destructive">
                        <BubbleContent>
                          {String(error)}
                        </BubbleContent>
                      </Bubble>
                    </MessageContent>
                  </Message>
                </MessageScrollerItem>
              )}
            </MessageScrollerContent>
          </MessageScrollerViewport>
          <MessageScrollerButton />
        </MessageScroller>
      </MessageScrollerProvider>

      {/* Bottom input */}
      <div className="shrink-0 px-4 md:px-8 pb-4 pt-2 flex justify-center">
        <div className="w-full max-w-3xl">
          <ChatInput
            input={input}
            setInput={setInput}
            isLoading={isLoading}
            handleSubmit={handleSubmit}
            database={database}
            onDatabaseChange={setDatabase}
          />
        </div>
      </div>
    </div>
  )
}