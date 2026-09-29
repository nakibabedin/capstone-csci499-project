import { useEffect, useState } from 'react'
import { api } from '../api/client'

export default function HomePage() {
  const [status, setStatus] = useState('checking...')

  useEffect(() => {
    api
      .health()
      .then((res) => setStatus(res.status))
      .catch(() => setStatus('unreachable'))
  }, [])

  return (
    <div>
      <h1>Home</h1>
      <p>Backend status: {status}</p>
    </div>
  )
}
