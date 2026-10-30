import { useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { supabase, supabaseDisabled } from '../api/supabase'

const links = [
  { to: '/', label: 'Home' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/upload', label: 'Upload' },
  { to: '/about', label: 'About' },
]

function SignOutIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5M21 12H9" />
    </svg>
  )
}

export default function Layout() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [signingOut, setSigningOut] = useState(false)

  async function handleSignOut() {
    setSigningOut(true)
    const { error } = await supabase.auth.signOut()
    setSigningOut(false)

    if (error) {
      window.alert(error.message)
      return
    }

    navigate('/login')
  }

  return (
    <>
      <header className="navbar">
        <Link to="/" className="brand">
          <span className="brand-mark" aria-hidden="true">
            CS
          </span>
          CS499 Project
        </Link>

        <nav className="nav-links">
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.to === '/'}>
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="nav-user">
          {supabaseDisabled ? (
            <span className="dev-badge" title="VITE_DISABLE_SUPABASE=true">
              Dev mode · no login
            </span>
          ) : user ? (
            <>
              <span className="avatar" aria-hidden="true">
                {user.email?.[0] ?? '?'}
              </span>
              <span className="user-email" title={user.email}>
                {user.email}
              </span>
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={handleSignOut}
                disabled={signingOut}
              >
                <SignOutIcon />
                {signingOut ? 'Signing out…' : 'Sign out'}
              </button>
            </>
          ) : (
            <Link to="/login" className="btn btn-primary btn-sm">
              Log in
            </Link>
          )}
        </div>
      </header>

      <main className="content">
        <Outlet />
      </main>
    </>
  )
}
