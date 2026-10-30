import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  deleteReport,
  getReport,
  getReportPdf,
  listReports,
  type SavedReport,
  type SavedReportDetail,
} from '../api/records'
import type { ReportDate } from '../api/reports'
import ResultsTable from '../components/ResultsTable'

// Styled with Tailwind classes only; colors come from the variables in index.css.
const card = 'rounded-xl border border-slate-200 bg-white p-5 shadow-sm'
const actionButton =
  'rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 transition-colors disabled:cursor-not-allowed disabled:opacity-50'
const alert = 'rounded-lg bg-red-100 px-3.5 py-2.5 text-sm text-red-700'

function errorMessage(err: unknown) {
  // fetch rejects with a TypeError only when the server can't be reached.
  return err instanceof TypeError ? 'Could not reach the server. Is the Flask backend running?' : (err as Error).message
}

function formatReportDate(date: ReportDate | null) {
  if (!date) return 'Report date not found'
  if (!date.iso) return `${date.label} ${date.text}`
  const [y, m, d] = date.iso.split('-').map(Number)
  const shown = new Date(y, m - 1, d).toLocaleDateString(undefined, { dateStyle: 'medium' })
  return `${date.label} ${shown}`
}

function Stat({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className={`rounded-lg border-l-[3px] bg-slate-50 px-3 py-2 ${accent}`}>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-lg font-bold tabular-nums">{value}</dd>
    </div>
  )
}

function SavedReportCard({ report, onDeleted }: { report: SavedReport; onDeleted: (id: string) => void }) {
  const [detail, setDetail] = useState<SavedReportDetail | null>(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function toggleResults() {
    setError(null)
    if (open) return setOpen(false)
    if (!detail) {
      setBusy(true)
      try {
        setDetail(await getReport(report.id))
      } catch (err) {
        setError(errorMessage(err))
        return
      } finally {
        setBusy(false)
      }
    }
    setOpen(true)
  }

  async function viewPdf() {
    setError(null)
    // Open the tab now: browsers block pop-ups opened after an await.
    const tab = window.open('', '_blank')
    try {
      const url = URL.createObjectURL(await getReportPdf(report.id))
      if (tab) tab.location.href = url
      else window.location.href = url
      // Long enough for the tab to load it.
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (err) {
      tab?.close()
      setError(errorMessage(err))
    }
  }

  async function remove() {
    if (!window.confirm(`Delete "${report.original_filename}" from your dashboard?`)) return
    setError(null)
    setBusy(true)
    try {
      await deleteReport(report.id)
      onDeleted(report.id)
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  const { summary } = report
  return (
    <article className={`${card} flex flex-col gap-4`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="mb-1 break-words text-base font-semibold">
            {report.original_filename}
            {report.status === 'reviewed' && (
              <span
                className="ml-2 rounded bg-slate-100 px-1.5 py-px align-middle text-[0.68rem] font-semibold text-slate-500"
                title="Saved with the values you reviewed and corrected"
              >
                Reviewed
              </span>
            )}
          </h3>
          <p className="text-xs text-slate-500">
            {formatReportDate(report.report_date)} · Saved{' '}
            {new Date(report.created_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })} ·{' '}
            {report.num_pages} {report.num_pages === 1 ? 'page' : 'pages'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className={`${actionButton} hover:border-(--primary) hover:text-(--primary)`}
            onClick={viewPdf}
          >
            View PDF
          </button>
          <button
            type="button"
            className={`${actionButton} hover:enabled:border-(--primary) hover:enabled:text-(--primary)`}
            onClick={toggleResults}
            disabled={busy}
          >
            {open ? 'Hide results' : 'Show results'}
          </button>
          <button
            type="button"
            className={`${actionButton} hover:enabled:border-red-700 hover:enabled:text-red-700`}
            onClick={remove}
            disabled={busy}
          >
            Delete
          </button>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Tests" value={summary.tests} accent="border-(--primary)" />
        <Stat label="In range" value={summary.in_range} accent="border-green-700" />
        <Stat label="Out of range" value={summary.out_of_range} accent="border-orange-700" />
        <Stat label="No range" value={summary.no_range} accent="border-slate-500" />
      </dl>

      {report.panels.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {report.panels.map((p) => (
            <span
              key={p.id}
              className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                p.status === 'complete' ? 'border-green-700 text-green-700' : 'border-dashed border-slate-300 text-slate-500'
              }`}
            >
              {p.name}
              {p.status === 'complete' && ' ✓'}
            </span>
          ))}
        </div>
      )}

      {error && <div className={alert}>{error}</div>}

      {open && detail && <ResultsTable results={detail.confirmed_results ?? detail.document.results} />}
    </article>
  )
}

export default function DashboardPage() {
  const [reports, setReports] = useState<SavedReport[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listReports()
      .then(setReports)
      .catch((err) => setError(errorMessage(err)))
  }, [])

  return (
    <div className="flex flex-col gap-5 pb-16 text-[15px] text-slate-800">
      <h1>Dashboard</h1>

      <section className="flex flex-col gap-3.5">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="text-lg font-semibold">Saved reports</h2>
          {reports && reports.length > 0 && (
            <span className="text-xs text-slate-500">
              {reports.length} {reports.length === 1 ? 'report' : 'reports'}
            </span>
          )}
        </div>

        {error && <div className={alert}>{error}</div>}
        {!error && reports === null && <p className="text-slate-500">Loading…</p>}
        {reports?.length === 0 && (
          <div className={`${card} flex flex-col gap-1 text-center`}>
            <p>No saved reports yet.</p>
            <p className="text-slate-500">
              <Link to="/upload" className="text-(--primary) underline">
                Upload a report
              </Link>{' '}
              and click Save Results to keep it here.
            </p>
          </div>
        )}
        {reports?.map((r) => (
          <SavedReportCard
            key={r.id}
            report={r}
            onDeleted={(id) => setReports((list) => list?.filter((x) => x.id !== id) ?? null)}
          />
        ))}
      </section>
    </div>
  )
}
