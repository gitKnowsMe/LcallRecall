"use client"

import type React from "react"

import { useState, useRef, useEffect, useCallback, useMemo } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Send, Copy, ThumbsUp, ThumbsDown, AlertCircle, RefreshCw, ChevronUp, Workflow } from "lucide-react"
import { AIChipIcon } from "@/components/ui/ai-chip-icon"
import { desktopAPI } from "@/lib/desktop-api"

interface Message {
  id: string
  type: "user" | "assistant"
  content: string
  timestamp: string
  isStreaming?: boolean
  sources?: Source[]
  error?: string
}

interface Source {
  id: string
  title: string
  content: string
  score: number
  metadata: { page?: number }
}

export function QueryInterface() {
  const [messages, setMessages] = useState<Message[]>(() => {
    // Load conversation history from localStorage
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('localrecall_chat_history')
      if (saved) {
        try {
          return JSON.parse(saved)
        } catch (e) {
          console.error('Failed to parse saved chat history:', e)
        }
      }
    }
    
    return [
      {
        id: "1",
        type: "assistant",
        content:
          "Hello! I'm your personal AI assistant. I can help you with your documents, answer questions about your knowledge base, and assist with research. What would you like to explore today?",
        timestamp: new Date().toISOString(),
      },
    ]
  })
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [currentStream, setCurrentStream] = useState<EventSource | null>(null)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [displayLimit, setDisplayLimit] = useState(10)
  const [showScrollTop, setShowScrollTop] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollViewportRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Get visible messages (last N messages based on display limit)
  const visibleMessages = useMemo(() => {
    return messages.slice(-displayLimit)
  }, [messages, displayLimit])

  const hasMoreMessages = messages.length > displayLimit

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  const scrollToTop = () => {
    scrollViewportRef.current?.scrollTo({ top: 0, behavior: "smooth" })
  }

  const loadMoreMessages = useCallback(() => {
    setDisplayLimit(prev => Math.min(prev + 10, messages.length))
  }, [messages.length])

  // Monitor scroll position to show/hide scroll-to-top button
  const handleScroll = useCallback((event: React.UIEvent<HTMLDivElement>) => {
    const target = event.currentTarget
    if (target) {
      const { scrollTop } = target
      setShowScrollTop(scrollTop > 200) // Show button when scrolled down 200px
    }
  }, [])

  // Save messages to localStorage whenever they change
  useEffect(() => {
    if (typeof localStorage !== 'undefined' && messages.length > 1) { // Don't save just the welcome message
      localStorage.setItem('localrecall_chat_history', JSON.stringify(messages))
    }
    scrollToBottom()
  }, [messages])

  
  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      if (currentStream) {
        currentStream.close()
      }
    }
  }, [])

  // Clear conversation history
  const clearHistory = useCallback(() => {
    const welcomeMessage = {
      id: "welcome",
      type: "assistant" as const,
      content: "Hello! I'm your personal AI assistant. I can help you with your documents, answer questions about your knowledge base, and assist with research. What would you like to explore today?",
      timestamp: new Date().toISOString(),
    }
    setMessages([welcomeMessage])
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('localrecall_chat_history')
    }
  }, [])

  // Copy message to clipboard
  const copyMessage = useCallback(async (content: string) => {
    if (navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(content)
        setFeedback('Copied to clipboard!')
        setTimeout(() => setFeedback(null), 2000)
      } catch (error) {
        console.error('Failed to copy:', error)
      }
    }
  }, [])

  // Handle message feedback
  const handleFeedback = useCallback((messageId: string, type: 'up' | 'down') => {
    setFeedback(`Feedback recorded: thumbs ${type}`)
    setTimeout(() => setFeedback(null), 2000)
    // TODO: Send feedback to backend
  }, [])

  // Retry failed query
  const retryQuery = useCallback((originalQuery: string) => {
    setInputValue(originalQuery)
    // Focus input for user to retry
    inputRef.current?.focus()
  }, [])

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      setInputValue('')
    } else if (e.key === 'Enter') {
      if (e.shiftKey) {
        // Shift+Enter: Allow new line (default behavior)
        return
      } else {
        // Enter: Submit form
        e.preventDefault()
        if (!isLoading && inputValue.trim()) {
          const form = e.currentTarget.closest('form')
          if (form) {
            const submitEvent = new Event('submit', { bubbles: true, cancelable: true })
            form.dispatchEvent(submitEvent)
          }
        }
      }
    }
  }, [isLoading, inputValue])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim() || isLoading) return

    const userQuery = inputValue.trim()
    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: userQuery,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInputValue("")
    setIsLoading(true)

    // Create assistant message for streaming
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      type: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      isStreaming: true,
    }

    setMessages((prev) => [...prev, assistantMessage])

    try {
      // Create streaming query
      const eventSource = desktopAPI.createQueryStream(userQuery, { top_k: 5 })
      setCurrentStream(eventSource)

      // Track streaming state
      let hasReceivedData = false
      let streamCompleted = false

      // Handle chunk events (streaming content)
      eventSource.addEventListener('chunk', (event) => {
        hasReceivedData = true
        try {
          const chunkData = event.data
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessage.id
                ? { ...msg, content: msg.content + chunkData }
                : msg
            )
          )
        } catch (error) {
          console.error('Error handling chunk:', error)
        }
      })

      // Handle metadata events (sources)
      eventSource.addEventListener('metadata', (event) => {
        hasReceivedData = true
        try {
          const data = JSON.parse(event.data)
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessage.id
                ? { ...msg, sources: data.sources || [] }
                : msg
            )
          )
        } catch (error) {
          console.error('Error handling metadata:', error)
        }
      })

      // Handle completion events
      eventSource.addEventListener('complete', (event) => {
        hasReceivedData = true
        try {
          streamCompleted = true
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessage.id
                ? { ...msg, isStreaming: false }
                : msg
            )
          )
          setIsLoading(false)
          eventSource.close()
          setCurrentStream(null)
        } catch (error) {
          console.error('Error handling completion:', error)
        }
      })

      // Handle progress events
      eventSource.addEventListener('progress', (event) => {
        try {
          JSON.parse(event.data)
        } catch (error) {
          // Error handling progress event
        }
      })

      // Fallback onmessage for any other events
      eventSource.onmessage = () => {
        hasReceivedData = true
      }

      eventSource.onerror = () => {
        
        // Only show error if stream hasn't completed normally
        if (!streamCompleted) {
          // If we received data, it's likely a connection issue
          // If no data received, could be auth issue or empty results
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === assistantMessage.id
                ? { 
                    ...msg, 
                    error: hasReceivedData 
                      ? 'Connection interrupted. Please try again.'
                      : 'No response received. Please check your connection or try logging out and back in.',
                    isStreaming: false 
                  }
                : msg
            )
          )
        }
        
        setIsLoading(false)
        eventSource.close()
        setCurrentStream(null)
      }

    } catch (error: any) {
      console.error('Query failed:', error)
      
      // Check if it's an auth error from createQueryStream
      const isAuthError = error.message && error.message.includes('AUTH_ERROR')
      const errorMessage = isAuthError 
        ? 'Please log in to continue chatting.'
        : 'Error processing your request. Please try again.'
      
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessage.id
            ? { ...msg, error: errorMessage, isStreaming: false }
            : msg
        )
      )
      setIsLoading(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col h-full relative">
      {/* Fixed Header */}
      <div className="flex-shrink-0 flex items-center justify-between p-6 border-b border-border">
        <div>
          <h1 className="text-xl font-semibold text-foreground">AI Chat</h1>
          {hasMoreMessages && (
            <p className="text-xs text-muted-foreground mt-1">
              Showing last {displayLimit} of {messages.length} messages
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={clearHistory}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Clear History
          </Button>
          {feedback && (
            <div role="status" className="text-sm text-green-600">
              {feedback}
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1 overflow-hidden">
        <div 
          className="p-6"
          ref={scrollViewportRef}
          onScroll={handleScroll}
        >
          <div 
            className="max-w-4xl mx-auto space-y-6" 
            role="log" 
            aria-live="polite"
          >
            {/* Load More Button */}
            {hasMoreMessages && (
              <div className="text-center">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadMoreMessages}
                  className="text-sm text-muted-foreground"
                >
                  <ChevronUp className="h-4 w-4 mr-2" />
                  Load {Math.min(10, messages.length - displayLimit)} older messages
                </Button>
              </div>
            )}

            {visibleMessages.map((message) => (
            <div key={message.id} className="space-y-3">
              <div className="flex gap-3 items-start">
                <div className="flex-shrink-0 w-14 h-14 flex items-center justify-center mt-1">
                  {message.type === "assistant" ? (
                    <AIChipIcon className="h-14 w-14 text-primary" isActive={!!message.isStreaming} />
                  ) : (
                    <div className="w-10 h-10 bg-primary rounded-full flex items-center justify-center">
                      <span className="text-primary-foreground font-medium text-sm">A</span>
                    </div>
                  )}
                </div>

                <div className="flex-1 space-y-2">
                  <div className="bg-card border border-border rounded-lg p-4">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap text-card-foreground">
                      {message.content}
                      {message.isStreaming && <span className="inline-block w-2 h-4 bg-current ml-1 animate-pulse" />}
                    </p>
                    {message.error && (
                      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm flex items-center gap-2">
                        <AlertCircle className="h-4 w-4" />
                        <span>{message.error}</span>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => retryQuery(messages.find(m => m.type === 'user' && m.id < message.id)?.content || '')}
                          className="ml-auto h-6 px-2 text-xs"
                        >
                          <RefreshCw className="h-3 w-3 mr-1" />
                          Retry
                        </Button>
                      </div>
                    )}
                  </div>
                  
                  {/* Sources Attribution */}
                  {message.type === 'assistant' && message.sources && message.sources.length > 0 && (
                    <div className="mt-2 p-3 bg-muted rounded-lg">
                      <h4 className="text-xs font-medium text-muted-foreground mb-2">Sources:</h4>
                      <div className="space-y-1">
                        {message.sources.map((source: any, idx) => (
                          <div key={idx} className="text-xs text-muted-foreground flex items-center justify-between">
                            <span className="truncate">
                              {source.filename || source.title || 'Unknown'}
                              {source.page && ` (Page ${source.page})`}
                            </span>
                            <span className="text-primary font-medium">{Math.round((source.relevance_score || source.score || 0) * 100)}%</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {/* Empty sources message */}
                  {message.type === 'assistant' && message.sources && message.sources.length === 0 && !message.isStreaming && (
                    <div className="mt-2 p-2 bg-yellow-50 border border-yellow-200 rounded text-yellow-700 text-xs">
                      No relevant sources found in your documents.
                    </div>
                  )}

                  {message.type === "assistant" && !message.isStreaming && !message.error && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground bg-primary/20 px-2 py-1 rounded">Local AI</span>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="h-6 w-6 p-0"
                        onClick={() => copyMessage(message.content)}
                        aria-label="Copy message"
                      >
                        <Copy className="h-3 w-3" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="h-6 w-6 p-0"
                        onClick={() => handleFeedback(message.id, 'up')}
                        aria-label="Thumbs up"
                      >
                        <ThumbsUp className="h-3 w-3" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="h-6 w-6 p-0"
                        onClick={() => handleFeedback(message.id, 'down')}
                        aria-label="Thumbs down"
                      >
                        <ThumbsDown className="h-3 w-3" />
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {isLoading && !visibleMessages.some(msg => msg.isStreaming) && (
            <div className="flex gap-3 items-start">
              <div className="flex-shrink-0 w-11 h-11 flex items-center justify-center">
                <AIChipIcon className="h-11 w-11 text-primary" data-testid="bot-icon" isActive={!!isLoading} />
              </div>
              <div className="flex-1">
                <div className="bg-card border border-border rounded-lg p-4">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <div className="flex space-x-1" data-testid="loading-dots">
                      <div className="w-2 h-2 bg-current rounded-full animate-bounce" />
                      <div
                        className="w-2 h-2 bg-current rounded-full animate-bounce"
                        style={{ animationDelay: "0.1s" }}
                      />
                      <div
                        className="w-2 h-2 bg-current rounded-full animate-bounce"
                        style={{ animationDelay: "0.2s" }}
                      />
                    </div>
                    <span>Generating response...</span>
                  </div>
                </div>
              </div>
            </div>
          )}

            <div ref={messagesEndRef} />
          </div>
        </div>
      </ScrollArea>

      {/* Scroll to Top Button */}
      {showScrollTop && (
        <Button
          className="fixed bottom-20 right-6 rounded-full shadow-lg z-10 w-10 h-10 p-0"
          onClick={scrollToTop}
          title="Scroll to top"
        >
          <ChevronUp className="h-4 w-4" />
        </Button>
      )}

      {/* Fixed Input Area - Enlarged */}
      <div className="flex-shrink-0 p-6 pb-12 border-t border-border" style={{ minHeight: '140px' }}>
        <div className="max-w-4xl mx-auto">
          <form onSubmit={handleSubmit} className="flex gap-3 items-start">
            <div className="flex-1">
              <textarea
                ref={inputRef as any}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask me anything about your documents..."
                disabled={isLoading}
                className="w-full min-h-[84px] px-3 py-3 text-sm border-2 border-input rounded-md bg-background resize-none focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
                aria-label="Type your message here"
                role="textbox"
                style={{ fontFamily: 'inherit', lineHeight: '1.5' }}
              />
            </div>
            <Button type="submit" disabled={isLoading || !inputValue.trim()} className="gap-2 mt-2" aria-label="Send message">
              <Send className="h-4 w-4" />
              Send
            </Button>
          </form>
          <p className="text-xs text-muted-foreground mt-1">Press Enter to send, Shift+Enter for new line</p>
        </div>
      </div>
    </div>
  )
}
