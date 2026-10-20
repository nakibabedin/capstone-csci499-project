import { useState, type DragEvent, type FormEvent, type ReactNode } from 'react'
import BiomarkerEditor, { type Biomarker, type LabResult } from './BiomarkerEditor'
import { resultStatus, StatusPill, type Status } from './status'

interface ParsedDocument {
  results: LabResult[]
  biomarkers: Biomarker[]
  unparsed: { line: string; page: number }[]
}

function Steps({ current }: { current: number }) {
  const steps = ['Upload report', 'Review biomarkers', 'AI summary']
  return (
    <ol className="steps">
      {steps.map((label, i) => (
        <li key={label} className={i < current ? 'done' : i === current ? 'active' : ''}>
          <span className="step-num">{i < current ? '✓' : i + 1}</span>
          {label}
        </li>
      ))}
    </ol>
  )
}

function Overview({ results }: { results: LabResult[] }) {
  const counts: Record<Status, number> = { high: 0, low: 0, abnormal: 0, normal: 0, unknown: 0 }
  for (const r of results) counts[resultStatus(r)]++
  const stats = [
    { label: 'Tests found', value: results.length, className: '' },
    { label: 'In range', value: counts.normal, className: 'stat-normal' },
    { label: 'Out of range', value: counts.high + counts.low + counts.abnormal, className: 'stat-out' },
    { label: 'No reference range', value: counts.unknown, className: 'stat-unknown' },
  ]
  return (
    <div className="stats">
      {stats.map((s) => (
        <div key={s.label} className={`stat ${s.className}`}>
          <div className="stat-value">{s.value}</div>
          <div className="stat-label">{s.label}</div>
        </div>
      ))}
    </div>
  )
}

/** Renders the model's plain-text summary: "- " lines as bullets, "Heading:" lines as headings. */
function SummaryText({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let bullets: string[] = []
  const flush = () => {
    if (bullets.length) blocks.push(<ul key={blocks.length}>{bullets.map((b, i) => <li key={i}>{b}</li>)}</ul>)
    bullets = []
  }
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (line.startsWith('- ') || line.startsWith('* ')) {
      bullets.push(line.slice(2))
      continue
    }
    flush()
    if (!line) continue
    const heading = /^([A-Z][^:]{2,60}):\s*(.*)$/.exec(line)
    if (heading) {
      blocks.push(<h3 key={blocks.length}>{heading[1]}</h3>)
      if (heading[2]) blocks.push(<p key={blocks.length}>{heading[2]}</p>)
    } else {
      blocks.push(<p key={blocks.length}>{line}</p>)
    }
  }
  flush()
  return <div className="summary-text">{blocks}</div>
}

function ResultsTable({ results }: { results: LabResult[] }) {
  return (
    <div className="table-wrap">
      <table className="results">
        <thead>
          <tr>
            <th>Test</th>
            <th>Result</th>
            <th>Reference</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => {
            const newSection = r.section && r.section !== results[i - 1]?.section
            return [
              newSection && (
                <tr key={`s${i}`} className="section-row">
                  <td colSpan={4}>{r.section}</td>
                </tr>
              ),
              <tr key={i}>
                <td>
                  {r.canonical ?? r.test}
                  {r.canonical && r.canonical !== r.test && <div className="muted small">{r.test}</div>}
                </td>
                <td className="num">
                  {r.value_text} <span className="muted">{r.unit}</span>
                </td>
                <td className="num muted">{r.reference_range ?? '—'}</td>
                <td>
                  <StatusPill status={resultStatus(r)} />
                </td>
              </tr>,
            ]
          })}
        </tbody>
      </table>
    </div>
  )
}

function App() {
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [document, setDocument] = useState<ParsedDocument | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [summary, setSummary] = useState('')
  const [summaryError, setSummaryError] = useState<string | null>(null)
  const [summarizing, setSummarizing] = useState(false)
  // Bumped on each upload so the editor starts fresh from the new parse.
  const [uploadId, setUploadId] = useState(0)

  function clearSummary() {
    setSummary('')
    setSummaryError(null)
  }

  async function summarize(corrected: LabResult[]) {
    if (!document) return
    // Corrected key biomarkers replace their parsed versions.
    const keyNames = new Set(document.biomarkers.map((b) => b.canonical))
    const results = [...corrected, ...document.results.filter((r) => !keyNames.has(r.canonical ?? ''))]
    if (results.length === 0) {
      setSummaryError('No results to summarize.')
      return
    }
    clearSummary()
    setSummarizing(true)
    try {
      const res = await fetch('http://localhost:5002/summarize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ results }),
      })
      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => ({}))
        setSummaryError(data.error ?? 'Failed to generate a summary.')
        return
      }
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        setSummary((prev) => prev + value)
      }
    } catch {
      setSummaryError('Could not reach the server while summarizing.')
    } finally {
      setSummarizing(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setDocument(null)
    setError(null)
    clearSummary()
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
        setUploadId((id) => id + 1)
      } else {
        setError(data.error)
      }
    } catch {
      setError('Could not reach the server. Is the Flask backend running?')
    } finally {
      setLoading(false)
    }
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    const dropped = e.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }

  const step = summary || summarizing ? 2 : document ? 1 : 0

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <svg className="brand-mark" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 2.5c-3.6 4.6-6.5 8.3-6.5 11.8a6.5 6.5 0 0 0 13 0C18.5 10.8 15.6 7.1 12 2.5z" />
          </svg>
          <div>
            <div className="brand-name">Blood Test Analyzer</div>
            <div className="brand-tag">Understand your lab report</div>
          </div>
        </div>
      </header>

      <main className="container">
        <Steps current={step} />

        <section className="card">
          <form onSubmit={handleSubmit} className="upload">
            <label
              className={`dropzone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
            >
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <svg viewBox="0 0 24 24" className="dropzone-icon" aria-hidden="true">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <path d="M14 2v6h6M12 18v-6M9 15l3-3 3 3" />
              </svg>
              {file ? (
                <>
                  <strong>{file.name}</strong>
                  <span className="muted">{(file.size / 1024).toFixed(0)} KB · click to choose a different file</span>
                </>
              ) : (
                <>
                  <strong>Drop your blood test report here</strong>
                  <span className="muted">or click to browse · PDF only</span>
                </>
              )}
            </label>
            <button type="submit" className="primary" disabled={!file || loading}>
              {loading ? 'Analyzing…' : 'Analyze report'}
            </button>
          </form>
          {error && <div className="alert">{error}</div>}
        </section>

        {document != null && (
          <>
            <Overview results={document.results} />

            <BiomarkerEditor
              key={uploadId}
              biomarkers={document.biomarkers}
              disabled={summarizing}
              onChange={clearSummary}
              onConfirm={summarize}
            />
          </>
        )}

        {(summarizing || summary || summaryError) && (
          <section className="card summary">
            <div className="card-head">
              <h2>Summary</h2>
              {summarizing && <span className="spinner" aria-label="Generating" />}
            </div>
            {summaryError ? (
              <div className="alert">{summaryError}</div>
            ) : summary ? (
              <SummaryText text={summary} />
            ) : (
              <p className="muted">Reading your results…</p>
            )}
            <p className="disclaimer">
              AI-generated summary for information only — not medical advice. Please review your results with your doctor.
            </p>
          </section>
        )}

        {document != null && document.results.length > 0 && (
          <section className="card">
            <div className="card-head">
              <h2>All results</h2>
              <span className="muted">As read from the report</span>
            </div>
            <ResultsTable results={document.results} />
          </section>
        )}

        {document != null && (
          <details className="raw">
            <summary>Raw parsed output</summary>
            <pre>{JSON.stringify(document, null, 2)}</pre>
          </details>
        )}
      </main>
    </div>
  )
}

export default App
