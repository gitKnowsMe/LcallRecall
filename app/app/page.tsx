"use client"

import { MainApp } from "@/components/main-app"
import { AuthForm } from "@/components/auth/auth-form"
import { useAuth } from "@/lib/auth-context"
import { Button } from "@/components/ui/button"
import { Shield, Database, Upload, MessageSquare, Search } from "lucide-react"
import { AIChipIcon } from "@/components/ui/ai-chip-icon"

// Disabled - keeping for reference
/* 
const SacredGeometryIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="50" cy="50" r="15" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <circle cx="37" cy="35" r="15" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <circle cx="63" cy="35" r="15" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <circle cx="37" cy="65" r="15" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <circle cx="63" cy="65" r="15" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <circle cx="28" cy="50" r="15" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <circle cx="72" cy="50" r="15" stroke="currentColor" strokeWidth="1.5" fill="none" />
    <circle cx="50" cy="50" r="35" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.6" />
  </svg>
)
*/

export default function HomePage() {
  const { isAuthenticated, isLoading } = useAuth()

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full mx-auto"></div>
          <p className="text-muted-foreground">Loading LocalRecall...</p>
        </div>
      </div>
    )
  }

  // Show main app if authenticated
  if (isAuthenticated) {
    return <MainApp />
  }

  // Show authentication form if not authenticated
  return <AuthForm />
}
