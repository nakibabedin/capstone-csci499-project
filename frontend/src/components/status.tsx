import type { LabResult } from './BiomarkerEditor'

export type Status = 'high' | 'low' | 'abnormal' | 'normal' | 'unknown'

/** Mirrors result_status() in backend/status.py: the report's flag, else the reference
 *  range, or for a word answer what the answer means. */
export function resultStatus(
  r: Pick<LabResult, 'flag' | 'value' | 'value_text' | 'ref_low' | 'ref_high' | 'text_status'>,
): Status {
  if (r.flag === 'H' || r.flag === 'HH') return 'high'
  if (r.flag === 'L' || r.flag === 'LL') return 'low'
  if (r.flag) return 'abnormal'
  if (r.value == null && r.text_status) return r.text_status === 'normal' ? 'normal' : 'abnormal'
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

const PILL_COLORS: Record<Status, string> = {
  high: 'bg-orange-100 text-orange-700',
  low: 'bg-blue-100 text-blue-700',
  abnormal: 'bg-red-100 text-red-700',
  normal: 'bg-green-100 text-green-700',
  unknown: 'bg-slate-100 text-slate-500',
}

export function StatusPill({ status }: { status: Status }) {
  return (
    <span
      className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${PILL_COLORS[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  )
}
