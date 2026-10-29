import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { supabase } from '../api/supabase'

const links = [
  { to: '/', label: 'Home' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/upload', label: 'Upload' },
  { to: '/about', label: 'About' },
]

export default function Layout() {
  const { user } = useAuth()
  const navigate = useNavigate()

  async function handleSignOut() {
    const { error } = await supabase.auth.signOut()

    if (error) {
      window.alert(error.message)
      return
    }

    navigate('/login')
  }

  return (
    <>
      <header className="navbar">
        <span className="brand">CS499 Project</span>

        <nav>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.to === '/'}>
              {link.label}
            </NavLink>
          ))}

          {user ? (
            <>
              <span>{user.email}</span>
              <button type="button" onClick={handleSignOut}>
                Sign out
              </button>
            </>
          ) : (
            <NavLink to="/login">Login</NavLink>
          )}
        </nav>
      </header>

      <main className="content">
        <Outlet />
      </main>
    </>
  )
}