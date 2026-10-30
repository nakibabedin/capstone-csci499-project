import { useEffect, useState, type DragEvent, type FormEvent } from 'react'
import { analyze, uploadReport, type PanelAnalysis, type ParsedDocument } from '../api/reports'
import BiomarkerEditor, { type LabResult, type Panel } from '../components/BiomarkerEditor'
import { Link, useNavigate } from 'react-router-dom'
import { saveReport } from '../api/records'
import { useAuth } from '../auth/AuthContext'
import PanelAnalysisCard from '../components/PanelAnalysis'
import ResultsTable from '../components/ResultsTable'
import { resultStatus, type Status } from '../components/status'
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

// Results kept in this browser tab while the user logs in to save them.
const PENDING_SAVE_KEY = 'pendingSave'

interface PendingSave {
  uploadRef: string
  filename: string
  document: ParsedDocument
  confirmed: { results: LabResult[]; analyses: PanelAnalysis[] } | null
}

function takePendingSave(): PendingSave | null {
  try {
    const raw = sessionStorage.getItem(PENDING_SAVE_KEY)
    sessionStorage.removeItem(PENDING_SAVE_KEY)
    return raw ? (JSON.parse(raw) as PendingSave) : null
  } catch {
    return null
  }
}

function storePendingSave(pending: PendingSave) {
  try {
    sessionStorage.setItem(PENDING_SAVE_KEY, JSON.stringify(pending))
  } catch {
    // Storage full or blocked: the user can upload again after logging in.
  }
}

type SaveState = { kind: 'idle' } | { kind: 'saving' } | { kind: 'saved' } | { kind: 'error'; message: string }

function SaveResults({
  loggedIn,
  hasCorrections,
  state,
  onSave,
}: {
  loggedIn: boolean
  hasCorrections: boolean
  state: SaveState
  onSave: () => void
}) {
  if (state.kind === 'saved') {
    return (
      <section className="card save-card saved">
        <div>
          <h2>✓ Saved to your dashboard</h2>
          <p className="muted">You can find this report on your dashboard any time.</p>
        </div>
        <Link to="/dashboard" className="btn btn-primary">
          View dashboard
        </Link>
      </section>
    )
  }

  return (
    <section className="card save-card">
      <div>
        <h2>Save results</h2>
        <p className="muted">
          {loggedIn
            ? 'Keep this report and its results on your dashboard.'
            : "Log in to keep this report on your dashboard. We'll save it as soon as you're logged in."}
          {hasCorrections
            ? ' Your corrected values will be saved.'
            : ' Confirm your biomarkers above first if you want to save corrected values.'}
        </p>
        {state.kind === 'error' && <div className="alert">{state.message}</div>}
      </div>
      <button type="button" className="btn btn-primary" onClick={onSave} disabled={state.kind === 'saving'}>
        {state.kind === 'saving' ? 'Saving…' : 'Save Results'}
      </button>
    </section>
  )
}

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [document, setDocument] = useState<ParsedDocument | null>(null)
  // The server's ID for the uploaded PDF and its original name, needed to save it.
  const [uploadRef, setUploadRef] = useState<string | null>(null)
  const [filename, setFilename] = useState('')
  const [saveState, setSaveState] = useState<SaveState>({ kind: 'idle' })
  // Set when the user comes back from logging in, to finish saving.
  const [autoSave, setAutoSave] = useState(false)
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()
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

  // Coming back from the login page: put the results back and finish saving.
  useEffect(() => {
    const pending = takePendingSave()
    if (!pending) return
    setDocument(pending.document)
    setConfirmed(pending.confirmed)
    setUploadRef(pending.uploadRef)
    setFilename(pending.filename)
    setUploadId((id) => id + 1)
    setConfirmId((id) => id + 1)
    setAutoSave(true)
  }, [])

  async function save() {
    if (!uploadRef) return
    if (!user) {
      if (document) storePendingSave({ uploadRef, filename, document, confirmed })
      navigate('/login', { state: { from: { pathname: '/upload' } } })
      return
    }
    setSaveState({ kind: 'saving' })
    try {
      await saveReport(uploadRef, filename, confirmed?.results)
      setSaveState({ kind: 'saved' })
    } catch (err) {
      setSaveState({
        kind: 'error',
        message: err instanceof TypeError ? 'Could not reach the server while saving.' : (err as Error).message,
      })
    }
  }

  useEffect(() => {
    if (!autoSave || authLoading) return
    setAutoSave(false)
    // Only save if they did log in; otherwise the button is still there.
    if (user) void save()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runs once auth has settled
  }, [autoSave, authLoading, user])

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
    setUploadRef(null)
    setSaveState({ kind: 'idle' })
    clearAnalysis()
    if (!file) return

    setLoading(true)
    try {
      const { document, uploadId: ref } = await uploadReport(file)
      setDocument(document)
      setUploadRef(ref)
      setFilename(file.name)
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

      {document != null && uploadRef && (
        <SaveResults loggedIn={user != null} hasCorrections={confirmed != null} state={saveState} onSave={save} />
      )}
    </div>
  )
}
