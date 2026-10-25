// Lab report upload, parsing and summaries. Kept separate from client.ts.
// In dev, Vite proxies /api to http://localhost:5001 (see vite.config.ts).

import type { Biomarker, LabResult, Panel } from '../components/BiomarkerEditor'

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

/** Age (years) and sex from the report header, confirmed or corrected by the user. */
export interface Patient {
  age: number | null
  sex: 'male' | 'female' | null
  /** The header line they were read from. */
  source?: string | null
}

export interface ParsedDocument {
  results: LabResult[]
  biomarkers: Biomarker[]
  panels: Panel[]
  patient: Patient
  analyses: PanelAnalysis[]
  unparsed: { line: string; page: number }[]
}

const json = (body: unknown): RequestInit => ({
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

async function postJson<T>(path: string, options: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { method: 'POST', ...options })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error ?? `Request failed: ${res.status}`)
  return body as T
}

/** Saves the PDF via /api/upload, then parses the saved copy. */
export async function uploadReport(file: File): Promise<ParsedDocument> {
  const form = new FormData()
  form.append('file', file)
  const { upload_id } = await postJson<{ upload_id: string }>('/upload', { body: form })
  const { document } = await postJson<{ document: ParsedDocument }>(`/uploads/${upload_id}/parse`, {})
  return document
}

/** Re-analyzes every panel from (possibly user-corrected) results. */
export async function analyze(results: LabResult[], patient: Patient): Promise<PanelAnalysis[]> {
  const { analyses } = await postJson<{ analyses: PanelAnalysis[] }>('/analyze', json({ results, patient }))
  return analyses
}

/** Returns the raw response so the caller can stream the panel's plain-text summary. */
export function summarizePanel(panelId: string, results: LabResult[], patient: Patient): Promise<Response> {
  return fetch(`/api/panels/${encodeURIComponent(panelId)}/summarize`, { method: 'POST', ...json({ results, patient }) })
}
