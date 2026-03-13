import { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { fetchMe, logoutApi } from './api'

interface AuthCtx {
  userEmail: string | null
  isLoading: boolean
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthCtx>(null!)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [userEmail, setUserEmail] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // On mount, verify the httpOnly cookie session by calling /auth/me
  useEffect(() => {
    fetchMe()
      .then(({ email }) => setUserEmail(email))
      .catch(() => setUserEmail(null))
      .finally(() => setIsLoading(false))
  }, [])

  const logout = async () => {
    await logoutApi()
    setUserEmail(null)
  }

  return (
    <AuthContext.Provider value={{ userEmail, isLoading, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
