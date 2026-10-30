import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate, type Location } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { supabase, supabaseDisabled } from '../api/supabase'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState<{ text: string; kind: 'error' | 'success' } | null>(null)
  const [isSigningUp, setIsSigningUp] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()

  // ProtectedRoute sends people here with the page they wanted in state.from.
  const from = (location.state as { from?: Location } | null)?.from?.pathname ?? '/dashboard'

  if (supabaseDisabled) { //Used for when no env variables are set for Supabase
    return (
      <section className="page-card auth-page">
        <h1>Log in</h1>
        <p className="muted">
          Login is turned off (VITE_DISABLE_SUPABASE=true). You are using the app as a local dev user.
        </p>
      </section>
    )
  }

  if (user) {
    return <Navigate to={from} replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage(null)
    setIsLoading(true)

    if (isSigningUp) {
      const { data, error } = await supabase.auth.signUp({ email, password })

      if (error) {
        setMessage({ text: error.message, kind: 'error' })
      } else if (data.session) {
        navigate(from, { replace: true })
      } else {
        setMessage({ text: 'Account created. Check your email to confirm it, then log in.', kind: 'success' })
        setIsSigningUp(false)
      }
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password })

      if (error) {
        setMessage({ text: error.message, kind: 'error' })
      } else {
        navigate(from, { replace: true })
      }
    }

    setIsLoading(false)
  }

  return (
    <section className="page-card auth-page">
      <h1>{isSigningUp ? 'Create an account' : 'Welcome back'}</h1>
      <p className="muted">
        {isSigningUp ? 'Sign up to save your reports to your dashboard.' : 'Log in to see your saved reports.'}
      </p>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="field">
          Email
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </label>

        <label className="field">
          Password
          <input
            type="password"
            autoComplete={isSigningUp ? 'new-password' : 'current-password'}
            minLength={isSigningUp ? 6 : undefined}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </label>

        {message && <p className={`notice notice-${message.kind}`}>{message.text}</p>}

        <button type="submit" className="btn btn-primary" disabled={isLoading}>
          {isLoading ? 'Please wait…' : isSigningUp ? 'Sign up' : 'Log in'}
        </button>
      </form>

      <p className="auth-switch">
        {isSigningUp ? 'Already have an account? ' : "Don't have an account? "}
        <button
          type="button"
          className="btn-link"
          onClick={() => {
            setIsSigningUp(!isSigningUp)
            setMessage(null)
          }}
        >
          {isSigningUp ? 'Log in' : 'Create one'}
        </button>
      </p>
    </section>
  )
}
