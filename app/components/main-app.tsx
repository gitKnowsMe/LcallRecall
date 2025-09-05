"use client"

import { useState, useEffect } from "react"
import { Sidebar } from "@/components/layout/sidebar"
import { DocumentUpload } from "@/components/documents/document-upload"
import { QueryInterface } from "@/components/query/query-interface"
import { WorkspaceManager } from "@/components/workspace/workspace-manager"
import { StatusDashboard } from "@/components/status/status-dashboard"
import { desktopAPI } from "@/lib/desktop-api"
import { useAuth } from "@/lib/auth-context"
import { Button } from "@/components/ui/button"
import { LogOut, User } from "lucide-react"

type ActiveView = "chat" | "upload" | "knowledge" | "memory" | "search" | "settings"
type BackendStatus = "connecting" | "connected" | "disconnected" | "error"

export function MainApp() {
  const { user, logout } = useAuth()
  const [activeView, setActiveView] = useState<ActiveView>("chat")
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("connecting")
  const [backendPort, setBackendPort] = useState(8000)

  // Check backend status on mount
  useEffect(() => {
    const checkBackend = async () => {
      try {
        const status = await desktopAPI.getBackendStatus()
        setBackendStatus(status.ready ? "connected" : "connecting")
        setBackendPort(status.port)
      } catch (error) {
        setBackendStatus("error")
      }
    }

    checkBackend()

    // Listen for backend status changes (if in Electron)
    if (desktopAPI.isDesktopApp()) {
      desktopAPI.onBackendStatusChange((status) => {
        if (status.status === "ready") {
          setBackendStatus("connected")
          setBackendPort(status.port || 8000)
        } else if (status.status === "stopped") {
          setBackendStatus("disconnected")
        } else if (status.status === "error") {
          setBackendStatus("error")
        }
      })
    }

    return () => {
      if (desktopAPI.isDesktopApp()) {
        desktopAPI.removeAllListeners("backend-status")
      }
    }
  }, [])

  const renderActiveView = () => {
    switch (activeView) {
      case "chat":
        return <QueryInterface />
      case "upload":
        return <DocumentUpload />
      case "knowledge":
        return <WorkspaceManager />
      case "memory":
        return <StatusDashboard />
      case "search":
        return <QueryInterface />
      case "settings":
        return <StatusDashboard />
      default:
        return <QueryInterface />
    }
  }

  const getStatusDisplay = () => {
    switch (backendStatus) {
      case "connected":
        return {
          color: "text-green-500",
          bg: "bg-green-500",
          text: "Connected",
          detail: `Backend running on http://localhost:${backendPort}`
        }
      case "connecting":
        return {
          color: "text-yellow-500",
          bg: "bg-yellow-500",
          text: "Connecting",
          detail: "Starting backend..."
        }
      case "disconnected":
        return {
          color: "text-gray-500",
          bg: "bg-gray-500",
          text: "Disconnected",
          detail: "Backend stopped"
        }
      case "error":
        return {
          color: "text-red-500",
          bg: "bg-red-500",
          text: "Error",
          detail: "Backend failed to start"
        }
    }
  }

  const status = getStatusDisplay()

  return (
    <div className="h-screen bg-background flex flex-col window-content">
      <div className="flex items-center justify-between bg-background border-b border-border desktop-titlebar">
        <div className="macos-controls">
          <div 
            className="macos-control red" 
            onClick={() => desktopAPI.closeWindow()}
            title="Close"
          ></div>
          <div 
            className="macos-control yellow" 
            onClick={() => desktopAPI.minimizeWindow()}
            title="Minimize"
          ></div>
          <div 
            className="macos-control green" 
            onClick={() => desktopAPI.maximizeWindow()}
            title="Maximize"
          ></div>
        </div>

        <div className="flex items-center gap-4 px-4 py-2">
          <div className={`desktop-connectivity ${backendStatus}`}>
            <div className="status-indicator"></div>
            <span className="font-medium">{status.text}</span>
            <span className="text-muted-foreground text-xs">{status.detail}</span>
          </div>
          
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-sm">
              <User className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">
                {user?.username || user?.email || 'User'}
              </span>
            </div>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={logout}
              className="h-8 w-8 p-0"
              title="Logout"
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <Sidebar activeView={activeView} onViewChange={setActiveView} />
        <main className="flex-1 overflow-hidden">{renderActiveView()}</main>
      </div>
    </div>
  )
}
