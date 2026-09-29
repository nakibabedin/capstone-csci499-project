import { useState, type FormEvent } from 'react'

function App() {
  const [file, setFile] = useState<File | null>(null)
  const [document, setDocument] = useState<unknown>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setDocument(null)
    setError(null)
    if (!file) return

    const formData = new FormData()
    formData.append('file', file)

    setLoading(true)
    try {
      const res = await fetch('http://localhost:5002/upload', {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (res.ok) {
        setDocument(data.document)
      } else {
        setError(data.error)
      }
    } catch {
      setError('Could not reach the server. Is the Flask backend running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 700, margin: '2rem auto', fontFamily: 'sans-serif' }}>
      <h1>PDF Parser</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button type="submit" disabled={!file || loading}>
          {loading ? 'Parsing…' : 'Upload & Parse'}
        </button>
      </form>

      {error && <p style={{ color: 'red' }}>{error}</p>}

      {document != null && (
        <>
          <h2>Parsed Content</h2>
          <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: '1rem' }}>
            {JSON.stringify(document, null, 2)}
          </pre>
        </>
      )}
    </div>
  )
}

export default App
