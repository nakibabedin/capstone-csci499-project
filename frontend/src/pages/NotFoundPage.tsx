import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <section className="page-card">
      <h1>Page not found</h1>
      <p className="muted">
        This page doesn't exist. <Link to="/">Go home</Link>
      </p>
    </section>
  )
}
