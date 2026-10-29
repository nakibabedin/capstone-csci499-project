import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../api/supabase'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [isSigningUp, setIsSigningUp] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage('')
    setIsLoading(true)

    if (isSigningUp) {
      const { data, error } = await supabase.auth.signUp({ email, password })

      if (error) {
        setMessage(error.message)
      } else if (data.session) {
        navigate('/dashboard')
      } else {
        setMessage('Account created. Check your email to confirm it, then log in.')
      }
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password })

      if (error) {
        setMessage(error.message)
      } else {
        navigate('/dashboard')
      }
    }

    setIsLoading(false)
  }

  return (
    <section>
      <h1>{isSigningUp ? 'Create an account' : 'Log in'}</h1>

      <form onSubmit={handleSubmit}>
        <p>
          <label>
            Email
            <br />
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
        </p>

        <p>
          <label>
            Password
            <br />
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
        </p>

        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Please wait…' : isSigningUp ? 'Sign up' : 'Log in'}
        </button>
      </form>

      <p>{message}</p>

      <button type="button" onClick={() => setIsSigningUp(!isSigningUp)}>
        {isSigningUp ? 'I already have an account' : 'Create an account'}
      </button>
    </section>
  )
}