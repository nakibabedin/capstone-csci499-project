// Lab report upload, parsing and summaries. Kept separate from client.ts.
// In dev, Vite proxies /api to http://localhost:5001 (see vite.config.ts).

import type { Biomarker, LabResult, Panel } from '../components/BiomarkerEditor'

/** A formula's or trained model's result; see the MODELS comment in backend/analysis.py. */
export interface ModelOutput {
  name: string
  /** null when it couldn't be computed; `missing` then says what it needed. */
  value: number | null
  unit: string | null
  interpretation: string | null
  model_version?: string
  missing?: string[]
  /** Risk band for trained risk models. */
  band?: 'low' | 'intermediate' | 'high'
  error?: string
}

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
  /** Outputs of the panel's formulas and models. */
  models: ModelOutput[]
}

/** Age (years) and sex from the report header, confirmed or corrected by the user,
 *  and optional height and weight the user enters (the backend computes BMI). */
export interface Patient {
  age: number | null
  sex: 'male' | 'female' | null
  height_cm?: number | null
  weight_kg?: number | null
  /** The header line they were read from. */
  source?: string | null
}

export interface ParsedDocument {
  results: LabResult[]
  biomarkers: Biomarker[]
  panels: Panel[]
  patient: Patient
  analyses: PanelAnalysis[]
  /** Outputs of models that use several panels at once (biological age). */
  overall: ModelOutput[]
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
export interface Analysis {
  analyses: PanelAnalysis[]
  overall: ModelOutput[]
}

export function analyze(results: LabResult[], patient: Patient): Promise<Analysis> {
  return postJson<Analysis>('/analyze', json({ results, patient }))
}

/** Returns the raw response so the caller can stream the panel's plain-text summary. */
export function summarizePanel(panelId: string, results: LabResult[], patient: Patient): Promise<Response> {
  return fetch(`/api/panels/${encodeURIComponent(panelId)}/summarize`, { method: 'POST', ...json({ results, patient }) })
}
