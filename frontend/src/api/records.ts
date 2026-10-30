// Reports saved to the user's dashboard; see backend/records.py.

import { authHeaders } from './supabase'
import type { PanelAnalysis, ParsedDocument, ReportDate } from './reports'
import type { LabResult, Panel } from '../components/BiomarkerEditor'

export interface SavedReport {
  id: string
  upload_id: string
  original_filename: string
  /** YYYY-MM-DD when known. */
  test_date: string | null
  report_date: ReportDate | null
  num_pages: number
  status: string
  /** When it was saved (ISO timestamp). */
  created_at: string
  summary: { tests: number; in_range: number; out_of_range: number; no_range: number }
  panels: Pick<Panel, 'id' | 'name' | 'status'>[]
}

export interface SavedReportDetail extends SavedReport {
  document: ParsedDocument
  /** The results after the user reviewed and corrected them, if they did. */
  confirmed_results: LabResult[] | null
  confirmed_analyses: PanelAnalysis[] | null
}

async function call(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(`/api${path}`, { ...init, headers: await authHeaders(init.headers) })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.error ?? `Request failed: ${res.status}`)
  }
  return res
}

/** Saves an uploaded report to the signed-in user's dashboard. Pass `results` when the
 *  user has reviewed and corrected them. Saving the same upload again returns the
 *  existing record. */
export async function saveReport(uploadId: string, filename: string, results?: LabResult[]): Promise<SavedReport> {
  const res = await call('/records', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ upload_id: uploadId, filename, results }),
  })
  const { record } = await res.json()
  return record
}

export async function listReports(): Promise<SavedReport[]> {
  const { records } = await (await call('/records')).json()
  return records
}

export async function getReport(id: string): Promise<SavedReportDetail> {
  const { record } = await (await call(`/records/${id}`)).json()
  return record
}

export async function deleteReport(id: string): Promise<void> {
  await call(`/records/${id}`, { method: 'DELETE' })
}

/** The original PDF. Fetched with the login token, so it can't be a plain link. */
export async function getReportPdf(id: string): Promise<Blob> {
  return (await call(`/records/${id}/pdf`)).blob()
}
