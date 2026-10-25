// Lab report upload, parsing and summaries. Kept separate from client.ts.
// In dev, Vite proxies /api to http://localhost:5001 (see vite.config.ts).

import type { Biomarker, LabResult, Panel } from '../components/BiomarkerEditor'

export interface ParsedDocument {
  results: LabResult[]
  biomarkers: Biomarker[]
  panels: Panel[]
  features: { schema_version: number; values: Record<string, number | null> }
  unparsed: { line: string; page: number }[]
}

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

/** Returns the raw response so the caller can stream the plain-text summary. */
export function summarize(results: LabResult[], panels: Panel[]): Promise<Response> {
  return fetch('/api/summarize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ results, panels }),
  })
}
