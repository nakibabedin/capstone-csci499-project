import { useState, type DragEvent, type FormEvent } from 'react'
import { analyze, uploadReport, type PanelAnalysis, type ParsedDocument } from '../api/reports'
import BiomarkerEditor, { type LabResult, type Panel } from '../components/BiomarkerEditor'
import PanelAnalysisCard from '../components/PanelAnalysis'
import { resultStatus, StatusPill, type Status } from '../components/status'
import './UploadPage.css'

function PanelChips({ panels }: { panels: Panel[] }) {
  if (panels.length === 0) return null
  return (
    <div className="panel-chips">
      <span className="muted small">Panels detected</span>
      {panels.map((p) => (
        <span
          key={p.id}
          className={`chip chip-${p.status}`}
          title={p.missing.length ? `Not tested: ${p.missing.join(', ')}` : 'All core tests present'}
        >
          {p.name}
          {p.status === 'complete' ? ' ✓' : ` · ${p.missing.length} missing`}
        </span>
      ))}
    </div>
  )
}

function Steps({ current }: { current: number }) {
  const steps = ['Upload report', 'Review biomarkers', 'Panel analysis']
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
                  {r.derived && <span className="tag">calculated</span>}
                  {r.suspect && <span className="tag tag-warn" title="Outside what's physically plausible; may be misread">⚠ check</span>}
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

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [document, setDocument] = useState<ParsedDocument | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  // The confirmed (possibly corrected) results and the panel analyses computed from them.
  const [confirmed, setConfirmed] = useState<{ results: LabResult[]; analyses: PanelAnalysis[] } | null>(null)
  const [analyzeError, setAnalyzeError] = useState<string | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  // Bumped on each upload so the editor starts fresh from the new parse,
  // and on each confirmation so panel cards drop summaries of old values.
  const [uploadId, setUploadId] = useState(0)
  const [confirmId, setConfirmId] = useState(0)

  function clearAnalysis() {
    setConfirmed(null)
    setAnalyzeError(null)
  }

  async function confirm(corrected: LabResult[]) {
    if (!document) return
    // Corrected biomarkers replace their parsed versions. Derived values are left
    // out: they may be stale after a correction, so the backend recomputes them.
    const keyNames = new Set(document.biomarkers.map((b) => b.canonical))
    const results = [
      ...corrected,
      ...document.results.filter((r) => !keyNames.has(r.canonical ?? '') && !r.derived),
    ]
    if (results.length === 0) {
      setAnalyzeError('No results to analyze.')
      return
    }
    clearAnalysis()
    setAnalyzing(true)
    try {
      setConfirmed({ results, analyses: await analyze(results) })
      setConfirmId((id) => id + 1)
    } catch (err) {
      setAnalyzeError(err instanceof TypeError ? 'Could not reach the server while analyzing.' : (err as Error).message)
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setDocument(null)
    setError(null)
    clearAnalysis()
    if (!file) return

    setLoading(true)
    try {
      setDocument(await uploadReport(file))
      setUploadId((id) => id + 1)
    } catch (err) {
      // fetch rejects with a TypeError only when the server can't be reached.
      setError(
        err instanceof TypeError
          ? 'Could not reach the server. Is the Flask backend running?'
          : (err as Error).message,
      )
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

  const step = confirmed ? 2 : document ? 1 : 0

  return (
    <div className="analyzer">
      <h1>Upload</h1>
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
          <Overview results={document.results.filter((r) => !r.derived)} />
          <PanelChips panels={document.panels} />

          <BiomarkerEditor
            key={uploadId}
            biomarkers={document.biomarkers}
            panels={document.panels}
            disabled={analyzing}
            onChange={clearAnalysis}
            onConfirm={confirm}
          />
        </>
      )}

      {analyzeError && <div className="alert">{analyzeError}</div>}

      {confirmed && (
        <>
          <h2 className="section-title">Panel analysis</h2>
          {confirmed.analyses.length === 0 && (
            <p className="muted">None of this report's panels have enough tests to analyze.</p>
          )}
          {confirmed.analyses.map((a) => (
            <PanelAnalysisCard key={`${confirmId}-${a.id}`} analysis={a} results={confirmed.results} />
          ))}
        </>
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
    </div>
  )
}
