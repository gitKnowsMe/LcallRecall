"use client"

import type React from "react"

import { useState, useRef, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Send, Bot, Copy, ThumbsUp, ThumbsDown, Mic, AlertCircle, RefreshCw } from "lucide-react"
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
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

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
    }
  }, [])

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
          console.log('Progress:', JSON.parse(event.data))
        } catch (error) {
          console.error('Error handling progress:', error)
        }
      })

      // Fallback onmessage for any other events
      eventSource.onmessage = (event) => {
        hasReceivedData = true
        console.log('Generic message event:', event)
      }

      eventSource.onerror = (error) => {
        console.error('SSE Error:', error)
        
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
    <div className="flex-1 flex flex-col h-screen">
      <div className="flex items-center justify-between p-6 border-b border-border">
        <div>
          <h1 className="text-xl font-semibold text-foreground">AI Chat</h1>
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
      <ScrollArea className="flex-1 p-6">
        <div 
          className="max-w-4xl mx-auto space-y-6" 
          role="log" 
          aria-live="polite"
        >
          {messages.map((message) => (
            <div key={message.id} className="space-y-3">
              <div className="flex gap-3 items-start">
                <div className="flex-shrink-0 w-8 h-8 bg-primary rounded-full flex items-center justify-center">
                  {message.type === "assistant" ? (
                    <Bot className="h-4 w-4 text-primary-foreground" data-testid="bot-icon" />
                  ) : (
                    <div className="w-4 h-4 bg-primary-foreground rounded-full" />
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

          {isLoading && (
            <div className="flex gap-3 items-start">
              <div className="flex-shrink-0 w-8 h-8 bg-primary rounded-full flex items-center justify-center">
                <Bot className="h-4 w-4 text-primary-foreground" data-testid="bot-icon" />
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
      </ScrollArea>

      <div className="p-6 border-t border-border">
        <div className="max-w-4xl mx-auto">
          <form onSubmit={handleSubmit} className="flex gap-3 items-end">
            <div className="flex-1 relative">
              <Input
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask me anything about your documents..."
                disabled={isLoading}
                className="pr-10"
                aria-label="Type your message here"
                role="textbox"
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="absolute right-2 top-1/2 -translate-y-1/2 h-6 w-6 p-0"
              >
                <Mic className="h-4 w-4" />
              </Button>
            </div>
            <Button type="submit" disabled={isLoading || !inputValue.trim()} className="gap-2" aria-label="Send message">
              <Send className="h-4 w-4" />
              Send
            </Button>
          </form>
          <p className="text-xs text-muted-foreground mt-2">Press Enter to send, Shift+Enter for new line</p>
        </div>
      </div>
    </div>
  )
}
