import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

export default function HomePage() {
  const [status, setStatus] = useState<'checking' | 'ok' | 'down'>('checking')

  useEffect(() => {
    api
      .health()
      .then((res) => setStatus(res.status === 'ok' ? 'ok' : 'down'))
      .catch(() => setStatus('down'))
  }, [])

  const statusText = { checking: 'Checking backend…', ok: 'Backend connected', down: 'Backend unreachable' }[status]

  return (
    <section className="page-card hero">
      <h1>Understand your blood test results</h1>
      <p>
        Upload a lab report PDF to see which results are in range, review the biomarkers we found, and get a
        plain-language summary of each panel. Every report you analyze is saved to your dashboard.
      </p>
      <div className="hero-actions">
        <Link to="/upload" className="btn btn-primary">
          Upload a report
        </Link>
        <Link to="/dashboard" className="btn btn-outline">
          View dashboard
        </Link>
      </div>
      <p className="status-line">
        <span className={`status-dot ${status === 'checking' ? '' : status}`} aria-hidden="true" />
        {statusText}
      </p>
    </section>
  )
}
