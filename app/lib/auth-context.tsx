"use client"

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { desktopAPI } from '@/lib/desktop-api'

interface User {
  id: string
  username: string
  workspaceId?: number
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  error: string | null
  clearError: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const isAuthenticated = !!user

  // Check for existing authentication on mount
  useEffect(() => {
    checkAuthStatus()
  }, [])

  const checkAuthStatus = async () => {
    try {
      setIsLoading(true)
      const userData = await desktopAPI.getCurrentUser()
      setUser(userData)
    } catch (error) {
      // User not authenticated or token expired
      console.log('User not authenticated:', error)
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  const login = async (username: string, password: string) => {
    try {
      setIsLoading(true)
      setError(null)
      
      const response = await desktopAPI.login(username, password)
      
      if (response.access_token && response.username) {
        // Create user object from response data
        setUser({
          id: response.user_id.toString(),
          username: response.username,
          workspaceId: response.workspace_id
        })
      } else {
        throw new Error('Invalid response from login')
      }
    } catch (error: any) {
      console.error('Login error:', error)
      setError(error.message || 'Login failed. Please check your credentials.')
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const register = async (username: string, password: string) => {
    try {
      setIsLoading(true)
      setError(null)
      
      const response = await desktopAPI.register(username, password)
      
      if (response.access_token && response.username) {
        // Create user object from response data
        setUser({
          id: response.user_id.toString(),
          username: response.username,
          workspaceId: response.workspace_id
        })
      } else {
        throw new Error('Invalid response from registration')
      }
    } catch (error: any) {
      console.error('Registration error:', error)
      setError(error.message || 'Registration failed. Please try again.')
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const logout = async () => {
    try {
      setIsLoading(true)
      await desktopAPI.logout()
    } catch (error) {
      console.error('Logout error:', error)
      // Continue with logout even if API call fails
    } finally {
      setUser(null)
      setIsLoading(false)
    }
  }

  const clearError = () => {
    setError(null)
  }

  const value: AuthContextType = {
    user,
    isAuthenticated,
    isLoading,
    login,
    register,
    logout,
    error,
    clearError
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}