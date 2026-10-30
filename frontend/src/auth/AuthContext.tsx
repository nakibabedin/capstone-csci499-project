import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'
import type { User } from '@supabase/supabase-js'
import { supabase, supabaseDisabled } from '../api/supabase'

// Stand-in user while Supabase is disabled; only id and email are read.
const DEV_USER = {
  id: '00000000-0000-0000-0000-000000000000',
  email: 'dev@localhost',
} as User

type AuthContextType = {
  user: User | null
  loading: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(
    supabaseDisabled ? DEV_USER : null,
  )
  const [loading, setLoading] = useState(!supabaseDisabled)

  useEffect(() => {
    if (supabaseDisabled) return

    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null)
      setLoading(false)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null)
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (context === undefined) {
    throw new Error('useAuth must be used inside AuthProvider')
  }

  return context
}