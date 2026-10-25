import type { LabResult } from './BiomarkerEditor'

export type Status = 'high' | 'low' | 'abnormal' | 'normal' | 'unknown'

/** Mirrors result_status() in backend/summarizer.py: the report's flag, else the reference range. */
export function resultStatus(r: Pick<LabResult, 'flag' | 'value' | 'value_text' | 'ref_low' | 'ref_high'>): Status {
  if (r.flag === 'H' || r.flag === 'HH') return 'high'
  if (r.flag === 'L' || r.flag === 'LL') return 'low'
  if (r.flag) return 'abnormal'
  // A value like ">60" can't be compared precisely, so trust the (absent) flag.
  if (r.value_text && '<>'.includes(r.value_text[0])) return 'normal'
  if (r.value == null || (r.ref_low == null && r.ref_high == null)) return 'unknown'
  if (r.ref_high != null && r.value > r.ref_high) return 'high'
  if (r.ref_low != null && r.value < r.ref_low) return 'low'
  return 'normal'
}

export const STATUS_LABEL: Record<Status, string> = {
  high: 'High',
  low: 'Low',
  abnormal: 'Abnormal',
  normal: 'In range',
  unknown: 'No range',
}

export function StatusPill({ status }: { status: Status }) {
  return <span className={`pill pill-${status}`}>{STATUS_LABEL[status]}</span>
}
