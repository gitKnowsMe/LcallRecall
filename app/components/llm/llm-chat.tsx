'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Send, Copy, RefreshCw, Zap } from 'lucide-react';
import { desktopAPI } from '@/lib/desktop-api';

interface Message {
  id: string;
  type: "user" | "assistant";
  content: string;
  timestamp: string;
  isStreaming?: boolean;
  error?: string;
}

export function LLMChat() {
  const [messages, setMessages] = useState<Message[]>(() => {
    // Load LLM conversation history from localStorage
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('localrecall_llm_chat_history');
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch (e) {
          console.error('Failed to parse saved LLM chat history:', e);
        }
      }
    }
    
    return [
      {
        id: "1",
        type: "assistant",
        content: "Hello! I'm Phi-2, your direct AI assistant. I can help with general questions, coding, creative writing, and more. Unlike the RAG chat, I don't have access to your documents - this is pure AI conversation. What would you like to talk about?",
        timestamp: new Date().toISOString(),
      }
    ];
  });

  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Save messages to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem('localrecall_llm_chat_history', JSON.stringify(messages));
  }, [messages]);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    const userMessageObj: Message = {
      id: Date.now().toString(),
      type: "user",
      content: userMessage,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessageObj]);
    setInput("");
    setIsLoading(true);

    // Create streaming assistant message
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      type: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
      isStreaming: true,
    };

    setMessages(prev => [...prev, assistantMessage]);

    try {
      // Create streaming request to LLM endpoint
      const eventSource = desktopAPI.createLLMStream(userMessage);
      
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === 'token' && data.content) {
            // Append token to the streaming message
            setMessages(prev => 
              prev.map(msg => 
                msg.id === assistantMessage.id 
                  ? { ...msg, content: msg.content + data.content }
                  : msg
              )
            );
          } else if (data.type === 'end') {
            // Mark streaming as complete
            setMessages(prev => 
              prev.map(msg => 
                msg.id === assistantMessage.id 
                  ? { ...msg, isStreaming: false }
                  : msg
              )
            );
            eventSource.close();
            setIsLoading(false);
          } else if (data.type === 'error') {
            // Handle error
            setMessages(prev => 
              prev.map(msg => 
                msg.id === assistantMessage.id 
                  ? { ...msg, content: "Sorry, I encountered an error. Please try again.", error: data.message, isStreaming: false }
                  : msg
              )
            );
            eventSource.close();
            setIsLoading(false);
          }
        } catch (parseError) {
          console.error('Failed to parse streaming data:', parseError);
        }
      };

      eventSource.onerror = (error) => {
        console.error('LLM streaming error:', error);
        setMessages(prev => 
          prev.map(msg => 
            msg.id === assistantMessage.id 
              ? { ...msg, content: "Connection error. Please check your connection and try again.", error: "Network error", isStreaming: false }
              : msg
          )
        );
        eventSource.close();
        setIsLoading(false);
      };

    } catch (error) {
      console.error('LLM chat error:', error);
      setMessages(prev => 
        prev.map(msg => 
          msg.id === assistantMessage.id 
            ? { ...msg, content: "Failed to send message. Please try again.", error: String(error), isStreaming: false }
            : msg
        )
      );
      setIsLoading(false);
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const clearHistory = () => {
    const initialMessage: Message = {
      id: "1",
      type: "assistant", 
      content: "Hello! I'm Phi-2, your direct AI assistant. I can help with general questions, coding, creative writing, and more. Unlike the RAG chat, I don't have access to your documents - this is pure AI conversation. What would you like to talk about?",
      timestamp: new Date().toISOString(),
    };
    setMessages([initialMessage]);
  };

  return (
    <div className="h-full flex flex-col p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-yellow-500" />
            <h1 className="text-2xl font-bold">Direct LLM Chat</h1>
          </div>
          <Badge variant="secondary" className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
            Phi-2 Direct
          </Badge>
        </div>
        
        <Button
          onClick={clearHistory}
          variant="outline"
          size="sm"
          className="flex items-center gap-2"
        >
          <RefreshCw className="h-4 w-4" />
          Clear History
        </Button>
      </div>

      {/* Chat Area */}
      <div className="flex-1 flex flex-col min-h-0">
        <ScrollArea className="flex-1 rounded-lg border bg-background" ref={scrollAreaRef}>
          <div className="p-4 space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.type === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-4 py-3 ${
                    message.type === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {message.type === "assistant" && (
                      <div className="flex-shrink-0 mt-0.5">
                        <Zap className="h-4 w-4 text-yellow-500" />
                      </div>
                    )}
                    <div className="flex-1 space-y-2">
                      <div className="prose dark:prose-invert max-w-none">
                        <p className="whitespace-pre-wrap break-words m-0">
                          {message.content}
                          {message.isStreaming && (
                            <span className="inline-block w-2 h-5 bg-current animate-pulse ml-1" />
                          )}
                        </p>
                        {message.error && (
                          <p className="text-sm text-red-500 mt-2">Error: {message.error}</p>
                        )}
                      </div>
                      {message.type === "assistant" && !message.isStreaming && (
                        <div className="flex items-center justify-between pt-2 border-t">
                          <span className="text-xs text-muted-foreground">
                            Direct Phi-2 • {new Date(message.timestamp).toLocaleTimeString()}
                          </span>
                          <Button
                            onClick={() => copyToClipboard(message.content)}
                            variant="ghost"
                            size="sm"
                            className="h-6 px-2"
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Input Area */}
        <form onSubmit={handleSubmit} className="flex gap-3 mt-4">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask me anything..."
            disabled={isLoading}
            className="flex-1"
            maxLength={4000}
          />
          <Button type="submit" disabled={isLoading || !input.trim()}>
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </div>
    </div>
  );
}