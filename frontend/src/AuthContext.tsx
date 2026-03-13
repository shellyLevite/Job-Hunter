import { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import { login as apiLogin, register as apiRegister, fetchMe, logoutApi } from './api'

interface AuthCtx {
  userEmail: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
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

  const login = async (email: string, password: string) => {
    const { email: confirmedEmail } = await apiLogin(email, password)
    setUserEmail(confirmedEmail)
  }

  const register = async (email: string, password: string) => {
    const { email: confirmedEmail } = await apiRegister(email, password)
    setUserEmail(confirmedEmail)
  }

  const logout = async () => {
    await logoutApi()
    setUserEmail(null)
  }

  return (
    <AuthContext.Provider value={{ userEmail, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
