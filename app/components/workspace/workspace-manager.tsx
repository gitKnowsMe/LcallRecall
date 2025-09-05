"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { FolderOpen, Plus, Settings, Trash2, FileText, Database, Clock, MoreVertical } from "lucide-react"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"

interface Workspace {
  id: string
  name: string
  description: string
  documentCount: number
  vectorCount: number
  createdAt: string
  lastAccessed: string
  isActive: boolean
}

export function WorkspaceManager() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([
    {
      id: "1",
      name: "My Knowledge Base",
      description: "Personal documents and research papers",
      documentCount: 42,
      vectorCount: 1247,
      createdAt: "2025-01-01",
      lastAccessed: "2025-01-03",
      isActive: true,
    },
    {
      id: "2",
      name: "Project Documentation",
      description: "Technical specs and API documentation",
      documentCount: 18,
      vectorCount: 523,
      createdAt: "2024-12-15",
      lastAccessed: "2025-01-02",
      isActive: false,
    },
  ])

  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [newWorkspaceName, setNewWorkspaceName] = useState("")
  const [newWorkspaceDescription, setNewWorkspaceDescription] = useState("")

  const handleCreateWorkspace = () => {
    if (!newWorkspaceName.trim()) return

    const newWorkspace: Workspace = {
      id: Date.now().toString(),
      name: newWorkspaceName,
      description: newWorkspaceDescription,
      documentCount: 0,
      vectorCount: 0,
      createdAt: new Date().toISOString().split("T")[0],
      lastAccessed: new Date().toISOString().split("T")[0],
      isActive: false,
    }

    setWorkspaces([...workspaces, newWorkspace])
    setNewWorkspaceName("")
    setNewWorkspaceDescription("")
    setShowCreateDialog(false)
  }

  const handleSwitchWorkspace = (workspaceId: string) => {
    setWorkspaces(
      workspaces.map((ws) => ({
        ...ws,
        isActive: ws.id === workspaceId,
        lastAccessed: ws.id === workspaceId ? new Date().toISOString().split("T")[0] : ws.lastAccessed,
      })),
    )
  }

  const handleDeleteWorkspace = (workspaceId: string) => {
    setWorkspaces(workspaces.filter((ws) => ws.id !== workspaceId))
  }

  return (
    <div className="flex-1 p-6 overflow-auto">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Workspace Management</h1>
            <p className="text-muted-foreground">
              Organize your documents into isolated workspaces with separate vector indices
            </p>
          </div>

          <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
            <DialogTrigger asChild>
              <Button className="gap-2">
                <Plus className="h-4 w-4" />
                New Workspace
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Workspace</DialogTitle>
                <DialogDescription>
                  Set up a new isolated workspace for your documents and AI interactions.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="workspace-name">Workspace Name</Label>
                  <Input
                    id="workspace-name"
                    value={newWorkspaceName}
                    onChange={(e) => setNewWorkspaceName(e.target.value)}
                    placeholder="e.g., Research Papers, Project Docs"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="workspace-description">Description (Optional)</Label>
                  <Input
                    id="workspace-description"
                    value={newWorkspaceDescription}
                    onChange={(e) => setNewWorkspaceDescription(e.target.value)}
                    placeholder="Brief description of this workspace"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateWorkspace} disabled={!newWorkspaceName.trim()}>
                    Create Workspace
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Active Workspace Alert */}
        <Alert>
          <FolderOpen className="h-4 w-4" />
          <AlertDescription>
            You are currently working in the <strong>{workspaces.find((ws) => ws.isActive)?.name}</strong> workspace.
            All document uploads and queries will be scoped to this workspace.
          </AlertDescription>
        </Alert>

        {/* Workspace Grid */}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {workspaces.map((workspace) => (
            <Card key={workspace.id} className={`relative ${workspace.isActive ? "ring-2 ring-primary" : ""}`}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <FolderOpen className="h-4 w-4" />
                      {workspace.name}
                      {workspace.isActive && (
                        <Badge variant="default" className="text-xs">
                          Active
                        </Badge>
                      )}
                    </CardTitle>
                    <CardDescription className="text-sm">{workspace.description || "No description"}</CardDescription>
                  </div>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem>
                        <Settings className="mr-2 h-4 w-4" />
                        Settings
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => handleDeleteWorkspace(workspace.id)}
                        disabled={workspace.isActive}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                {/* Statistics */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">Documents:</span>
                    <span className="font-medium">{workspace.documentCount}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Database className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">Vectors:</span>
                    <span className="font-medium">{workspace.vectorCount}</span>
                  </div>
                </div>

                {/* Timestamps */}
                <div className="space-y-1 text-xs text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <Clock className="h-3 w-3" />
                    <span>Created: {workspace.createdAt}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="h-3 w-3" />
                    <span>Last accessed: {workspace.lastAccessed}</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="pt-2">
                  {workspace.isActive ? (
                    <Button variant="outline" className="w-full bg-transparent" disabled>
                      Current Workspace
                    </Button>
                  ) : (
                    <Button variant="default" className="w-full" onClick={() => handleSwitchWorkspace(workspace.id)}>
                      Switch to Workspace
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Empty State */}
        {workspaces.length === 0 && (
          <Card className="text-center py-12">
            <CardContent>
              <FolderOpen className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <CardTitle className="mb-2">No Workspaces</CardTitle>
              <CardDescription className="mb-4">
                Create your first workspace to start organizing your documents
              </CardDescription>
              <Button onClick={() => setShowCreateDialog(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Create Workspace
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
