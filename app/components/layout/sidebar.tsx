"use client"

import { Button } from "@/components/ui/button"
import { MessageSquare, Upload, Database, Brain, Search, Settings, LogOut, Bot } from "lucide-react"
import { AIChipIcon } from "@/components/ui/ai-chip-icon"
// import { SacredGeometryIcon } from "@/components/ui/sacred-geometry-icon" // Disabled - keeping for reference
import { useAuth } from "@/lib/auth-context"

interface SidebarProps {
  activeView: string
  onViewChange: (view: "chat" | "upload" | "knowledge" | "memory" | "llm" | "search" | "settings") => void
}

export function Sidebar({ activeView, onViewChange }: SidebarProps) {
  const { logout } = useAuth()
  const menuItems = [
    { id: "chat", label: "Chat", icon: MessageSquare },
    { id: "upload", label: "Upload", icon: Upload },
    { id: "knowledge", label: "Knowledge", icon: Database },
    { id: "memory", label: "Memory", icon: Brain },
    { id: "llm", label: "LLM", icon: Bot },
    { id: "search", label: "Search", icon: Search },
    { id: "settings", label: "Settings", icon: Settings },
  ]

  return (
    <div className="w-64 bg-sidebar border-r border-sidebar-border flex flex-col">
      <div className="p-4 border-b border-sidebar-border">
        <div className="flex items-center gap-2">
          <AIChipIcon className="h-7 w-7 text-sidebar-primary" />
          {/* <SacredGeometryIcon className="h-7 w-7 text-sidebar-primary" /> Disabled - keeping for reference */}
          <span className="font-semibold text-sidebar-foreground">Local Recall</span>
        </div>
      </div>

      <div className="px-4 py-2">
        <span className="text-xs font-medium text-sidebar-foreground/70 uppercase tracking-wide">Main</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4">
        <div className="space-y-1">
          {menuItems.map((item) => {
            const Icon = item.icon
            const isActive = activeView === item.id

            return (
              <Button
                key={item.id}
                variant="ghost"
                className={`w-full justify-start gap-3 hover:bg-sidebar-foreground/5 ${
                  isActive ? "text-white" : "text-sidebar-foreground/70"
                }`}
                onClick={() => onViewChange(item.id as any)}
              >
                <Icon className={item.id === 'llm' ? "h-[18px] w-[18px]" : "h-4 w-4"} />
                {item.label}
              </Button>
            )
          })}
        </div>
      </nav>

      <div className="p-4 border-t border-sidebar-border">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 bg-sidebar-primary rounded-full flex items-center justify-center">
            <span className="text-xs font-medium text-sidebar-primary-foreground">A</span>
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-sidebar-foreground">admin</div>
            <div className="text-xs text-sidebar-foreground/70">admin@example.com</div>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-accent">
          <div className="w-2 h-2 bg-accent rounded-full"></div>
          <span>Connected</span>
        </div>

        <Button
          variant="ghost"
          className="w-full justify-start gap-3 text-sidebar-foreground hover:bg-sidebar-foreground/5 mt-2"
          onClick={logout}
        >
          <LogOut className="h-4 w-4" />
          Log out
        </Button>
      </div>
    </div>
  )
}
