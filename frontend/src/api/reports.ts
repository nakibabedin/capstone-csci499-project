// Lab report upload, parsing and summaries. Kept separate from client.ts.
// In dev, Vite proxies /api to http://localhost:5001 (see vite.config.ts).

import type { Biomarker, LabResult, Panel } from '../components/BiomarkerEditor'
import { authHeaders } from './supabase'

/** One panel's analysis; see available_analyses() in backend/analysis.py. */
export interface PanelAnalysis {
  id: string
  name: string
  /** Fraction of the panel's inputs present on the report. */
  coverage: number
  /** Model inputs: canonical-unit values (0/1 for word answers), in the panel's fixed order. */
  inputs: {
    schema_version: number
    values: Record<string, number | null>
    out_of_range: Record<string, 0 | 1 | null>
    missing: string[]
  }
  findings: {
    test: string
    value_text: string | null
    unit: string | null
    reference_range: string | null
    status: 'high' | 'low' | 'abnormal'
    suspect: boolean
  }[]
  indices: { name: string; value: number; note: string }[]
  /** The panel's ML model output, once one is registered. */
  model: Record<string, unknown> | null
}

export interface ParsedDocument {
  results: LabResult[]
  biomarkers: Biomarker[]
  panels: Panel[]
  analyses: PanelAnalysis[]
  unparsed: { line: string; page: number }[]
  /** When the sample was taken, if the report labels it; see backend/report_date.py. */
  report_date: ReportDate | null
}

export interface ReportDate {
  label: 'Collected' | 'Reported' | 'Received' | 'Date'
  /** As printed on the report. */
  text: string
  /** YYYY-MM-DD, or null when day and month are ambiguous (03/04/2025). */
  iso: string | null
}

const json = (body: unknown): RequestInit => ({
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

async function postJson<T>(path: string, options: RequestInit): Promise<T> {
  // Sends the login token when there is one.
  const headers = await authHeaders(options.headers)
  const res = await fetch(`/api${path}`, { method: 'POST', ...options, headers })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error ?? `Request failed: ${res.status}`)
  return body as T
}

/** Saves the PDF via /api/upload, then parses the saved copy. No login needed;
 *  pass `uploadId` to saveReport() in records.ts to keep it on the dashboard. */
export async function uploadReport(file: File): Promise<{ document: ParsedDocument; uploadId: string }> {
  const form = new FormData()
  form.append('file', file)
  const { upload_id } = await postJson<{ upload_id: string }>('/upload', { body: form })
  const { document } = await postJson<{ document: ParsedDocument }>(`/uploads/${upload_id}/parse`, {})
  return { document, uploadId: upload_id }
}

/** Re-analyzes every panel from (possibly user-corrected) results. */
export async function analyze(results: LabResult[]): Promise<PanelAnalysis[]> {
  const { analyses } = await postJson<{ analyses: PanelAnalysis[] }>('/analyze', json({ results }))
  return analyses
}

/** Returns the raw response so the caller can stream the panel's plain-text summary. */
export function summarizePanel(panelId: string, results: LabResult[]): Promise<Response> {
  return fetch(`/api/panels/${encodeURIComponent(panelId)}/summarize`, { method: 'POST', ...json({ results }) })
}
