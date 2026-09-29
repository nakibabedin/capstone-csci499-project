import { NavLink, Outlet } from 'react-router-dom'

const links = [
  { to: '/', label: 'Home' },
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/upload', label: 'Upload' },
  { to: '/about', label: 'About' },
]

export default function Layout() {
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
        </nav>
      </header>
      <main className="content">
        <Outlet />
      </main>
    </>
  )
}
