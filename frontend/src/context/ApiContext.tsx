'use client'

import axios from 'axios'
import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL
const TOKEN_STORAGE_KEY = 'ai-campaign-token'

interface ApiContextType {
  authToken: string | null
  login: (token: string) => void
  logout: () => void
  api: ReturnType<typeof axios.create>
}

const ApiContext = createContext<ApiContextType | undefined>(undefined)

export const ApiProvider = ({ children }: { children: ReactNode }) => {
  const [authToken, setAuthToken] = useState<string | null>(null)

  const api = useMemo(() => {
    const instance = axios.create({
      baseURL: API_URL,
    })
    return instance
  }, [])

  // Hydrate auth token from localStorage on first load
  useEffect(() => {
    if (typeof window === 'undefined') return
    const storedToken = window.localStorage.getItem(TOKEN_STORAGE_KEY)
    if (storedToken) {
      setAuthToken(storedToken)
    }
  }, [])

  // Sync axios headers and storage whenever the auth token changes
  useEffect(() => {
    if (authToken) {
      api.defaults.headers.common['Authorization'] = `Bearer ${authToken}`
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(TOKEN_STORAGE_KEY, authToken)
      }
    } else {
      delete api.defaults.headers.common['Authorization']
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(TOKEN_STORAGE_KEY)
      }
    }
  }, [authToken, api])

  const login = (token: string) => setAuthToken(token)
  const logout = () => setAuthToken(null)

  return (
    <ApiContext.Provider value={{ authToken, login, logout, api }}>
      {children}
    </ApiContext.Provider>
  )
}

export const useApi = () => {
  const context = useContext(ApiContext)
  if (!context) {
    throw new Error('useApi must be used within an ApiProvider')
  }
  return context
}
