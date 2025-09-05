"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Activity,
  Brain,
  Database,
  Cpu,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Settings,
  RefreshCw,
  Zap,
  Clock,
} from "lucide-react"

interface SystemStatus {
  component: string
  status: "healthy" | "warning" | "error"
  message: string
  lastChecked: string
}

interface SystemMetrics {
  cpuUsage: number
  memoryUsage: number
  diskUsage: number
  modelMemory: number
  vectorIndexSize: number
  totalDocuments: number
  totalVectors: number
  avgQueryTime: number
}

export function StatusDashboard() {
  const [systemStatus] = useState<SystemStatus[]>([
    {
      component: "Phi-2 Model",
      status: "healthy",
      message: "Model loaded and ready",
      lastChecked: "2025-01-03T10:30:00Z",
    },
    {
      component: "FAISS Vector Store",
      status: "healthy",
      message: "All workspace indices operational",
      lastChecked: "2025-01-03T10:30:00Z",
    },
    {
      component: "SQLite Database",
      status: "healthy",
      message: "Database connections stable",
      lastChecked: "2025-01-03T10:30:00Z",
    },
    {
      component: "Document Processing",
      status: "warning",
      message: "2 documents in processing queue",
      lastChecked: "2025-01-03T10:29:00Z",
    },
  ])

  const [metrics] = useState<SystemMetrics>({
    cpuUsage: 45,
    memoryUsage: 68,
    diskUsage: 32,
    modelMemory: 2.4,
    vectorIndexSize: 156.7,
    totalDocuments: 42,
    totalVectors: 1247,
    avgQueryTime: 1.2,
  })

  const [settings, setSettings] = useState({
    autoProcessing: true,
    streamingResponses: true,
    contextWindow: "4096",
    chunkSize: "512",
    chunkOverlap: "50",
    maxConcurrentProcessing: "2",
  })

  const getStatusIcon = (status: SystemStatus["status"]) => {
    switch (status) {
      case "healthy":
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case "warning":
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />
      case "error":
        return <XCircle className="h-4 w-4 text-red-500" />
    }
  }

  const getStatusBadge = (status: SystemStatus["status"]) => {
    const variants = {
      healthy: "default",
      warning: "secondary",
      error: "destructive",
    } as const

    const labels = {
      healthy: "Healthy",
      warning: "Warning",
      error: "Error",
    }

    return <Badge variant={variants[status]}>{labels[status]}</Badge>
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B"
    const k = 1024
    const sizes = ["B", "KB", "MB", "GB"]
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Number.parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i]
  }

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
  }

  return (
    <div className="flex-1 p-6 overflow-auto">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
              <Activity className="h-6 w-6" />
              System Status & Settings
            </h1>
            <p className="text-muted-foreground">Monitor system health and configure LocalRecall settings</p>
          </div>
          <Button variant="outline" className="gap-2 bg-transparent">
            <RefreshCw className="h-4 w-4" />
            Refresh Status
          </Button>
        </div>

        <Tabs defaultValue="status" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="status">System Status</TabsTrigger>
            <TabsTrigger value="metrics">Performance</TabsTrigger>
            <TabsTrigger value="settings">Settings</TabsTrigger>
          </TabsList>

          {/* System Status Tab */}
          <TabsContent value="status" className="space-y-6">
            {/* Overall Health */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-green-500" />
                  System Health
                </CardTitle>
                <CardDescription>All core components are operational</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  {systemStatus.map((status, index) => (
                    <Card key={index}>
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium">{status.component}</span>
                          {getStatusIcon(status.status)}
                        </div>
                        <div className="space-y-2">
                          {getStatusBadge(status.status)}
                          <p className="text-xs text-muted-foreground">{status.message}</p>
                          <p className="text-xs text-muted-foreground flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatTime(status.lastChecked)}
                          </p>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Model Information */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="h-5 w-5" />
                  AI Model Information
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Model</Label>
                    <p className="text-sm text-muted-foreground">Phi-2 Instruct Q4_K_M</p>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Memory Usage</Label>
                    <p className="text-sm text-muted-foreground">{metrics.modelMemory} GB</p>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-sm font-medium">Context Window</Label>
                    <p className="text-sm text-muted-foreground">4,096 tokens</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Performance Metrics Tab */}
          <TabsContent value="metrics" className="space-y-6">
            {/* Resource Usage */}
            <div className="grid gap-6 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Cpu className="h-5 w-5" />
                    System Resources
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>CPU Usage</span>
                      <span>{metrics.cpuUsage}%</span>
                    </div>
                    <Progress value={metrics.cpuUsage} />
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Memory Usage</span>
                      <span>{metrics.memoryUsage}%</span>
                    </div>
                    <Progress value={metrics.memoryUsage} />
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Disk Usage</span>
                      <span>{metrics.diskUsage}%</span>
                    </div>
                    <Progress value={metrics.diskUsage} />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Database className="h-5 w-5" />
                    Data Statistics
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-foreground">{metrics.totalDocuments}</div>
                      <div className="text-sm text-muted-foreground">Documents</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-foreground">{metrics.totalVectors}</div>
                      <div className="text-sm text-muted-foreground">Vectors</div>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>Vector Index Size</span>
                      <span>{formatBytes(metrics.vectorIndexSize * 1024 * 1024)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span>Avg Query Time</span>
                      <span>{metrics.avgQueryTime}s</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Performance Chart Placeholder */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap className="h-5 w-5" />
                  Performance Trends
                </CardTitle>
                <CardDescription>Query response times and system load over time</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-64 flex items-center justify-center bg-muted/20 rounded-lg">
                  <div className="text-center space-y-2">
                    <Activity className="h-12 w-12 text-muted-foreground mx-auto" />
                    <p className="text-sm text-muted-foreground">Performance charts will be displayed here</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Settings Tab */}
          <TabsContent value="settings" className="space-y-6">
            <div className="grid gap-6 md:grid-cols-2">
              {/* Processing Settings */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Settings className="h-5 w-5" />
                    Processing Settings
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="auto-processing">Auto-process uploads</Label>
                    <Switch
                      id="auto-processing"
                      checked={settings.autoProcessing}
                      onCheckedChange={(checked) => setSettings({ ...settings, autoProcessing: checked })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="chunk-size">Chunk Size (tokens)</Label>
                    <Select
                      value={settings.chunkSize}
                      onValueChange={(value) => setSettings({ ...settings, chunkSize: value })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="256">256</SelectItem>
                        <SelectItem value="512">512</SelectItem>
                        <SelectItem value="1024">1024</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="chunk-overlap">Chunk Overlap (tokens)</Label>
                    <Input
                      id="chunk-overlap"
                      value={settings.chunkOverlap}
                      onChange={(e) => setSettings({ ...settings, chunkOverlap: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="max-concurrent">Max Concurrent Processing</Label>
                    <Select
                      value={settings.maxConcurrentProcessing}
                      onValueChange={(value) => setSettings({ ...settings, maxConcurrentProcessing: value })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">1</SelectItem>
                        <SelectItem value="2">2</SelectItem>
                        <SelectItem value="4">4</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </CardContent>
              </Card>

              {/* AI Settings */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Brain className="h-5 w-5" />
                    AI Settings
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="streaming">Streaming Responses</Label>
                    <Switch
                      id="streaming"
                      checked={settings.streamingResponses}
                      onCheckedChange={(checked) => setSettings({ ...settings, streamingResponses: checked })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="context-window">Context Window (tokens)</Label>
                    <Select
                      value={settings.contextWindow}
                      onValueChange={(value) => setSettings({ ...settings, contextWindow: value })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="2048">2,048</SelectItem>
                        <SelectItem value="4096">4,096</SelectItem>
                        <SelectItem value="8192">8,192</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Save Settings */}
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium">Configuration Changes</h3>
                    <p className="text-sm text-muted-foreground">Some settings require a restart to take effect</p>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline">Reset to Defaults</Button>
                    <Button>Save Settings</Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
