import { useState } from 'react'
import { resultStatus, StatusPill, type Status } from './status'

export interface LabResult {
  test: string
  canonical: string | null
  value: number | null
  value_text: string | null
  unit: string | null
  flag: string | null
  reference_range: string | null
  ref_low: number | null
  ref_high: number | null
  section?: string | null
  page?: number | null
  loinc?: string | null
  value_std?: number | null
  unit_std?: string | null
  suspect?: boolean
  derived?: boolean
}

export interface Biomarker extends LabResult {
  canonical: string
  found: boolean
  panel: string
  canonical_unit: string | null
  plausible: [number, number]
}

export interface Panel {
  id: string
  name: string
  status: 'complete' | 'partial'
  found: string[]
  missing: string[]
}

interface Draft {
  value: string
  unit: string
  low: string
  high: string
}

type Errors = Partial<Record<keyof Draft, string>>

const VALUE_RE = /^([<>]=?)?\s*(\d*\.?\d+)$/
const NUMBER_RE = /^\d*\.?\d+$/

function toDraft(b: Biomarker): Draft {
  return {
    value: b.value_text ?? '',
    unit: b.unit ?? '',
    low: b.ref_low?.toString() ?? '',
    high: b.ref_high?.toString() ?? '',
  }
}

function validate(d: Draft): Errors {
  const errors: Errors = {}
  if (d.value.trim() && !VALUE_RE.test(d.value.trim())) errors.value = 'Enter a number, e.g. 5.4 or >60'
  if (d.low.trim() && !NUMBER_RE.test(d.low.trim())) errors.low = 'Not a number'
  if (d.high.trim() && !NUMBER_RE.test(d.high.trim())) errors.high = 'Not a number'
  if (!errors.low && !errors.high && d.low.trim() && d.high.trim() && Number(d.low) > Number(d.high)) {
    errors.high = 'Must be ≥ low'
  }
  return errors
}

function isEdited(b: Biomarker, d: Draft) {
  return JSON.stringify(d) !== JSON.stringify(toDraft(b))
}

/** The corrected biomarker in the result shape /summarize expects, or null if it has no value. */
function toResult(b: Biomarker, d: Draft): LabResult | null {
  const match = VALUE_RE.exec(d.value.trim())
  if (!match) return null
  const original = toDraft(b)
  const low = d.low.trim() ? Number(d.low) : null
  const high = d.high.trim() ? Number(d.high) : null
  const range =
    low != null && high != null ? `${low}-${high}` : high != null ? `<=${high}` : low != null ? `>=${low}` : null
  const valueOrRangeEdited = d.value !== original.value || d.low !== original.low || d.high !== original.high
  return {
    test: b.test,
    canonical: b.canonical,
    value: Number(match[2]),
    value_text: d.value.trim().replace(/\s+/g, ''),
    unit: d.unit.trim() || null,
    // The PDF's flag describes the printed value; once edited, status comes from the range.
    flag: valueOrRangeEdited ? null : b.flag,
    reference_range: range,
    ref_low: low,
    ref_high: high,
  }
}

/** The draft value in the biomarker's canonical unit, or null if the unit can't be converted.
 *  Uses the conversion the backend applied to the parsed value when the unit is unchanged. */
function standardize(b: Biomarker, value: number, unit: string): number | null {
  if (unit === (b.canonical_unit ?? '')) return value
  if (unit === (b.unit ?? '') && b.value && b.value_std != null) return (value * b.value_std) / b.value
  return null
}

const round = (x: number) => Number(x.toPrecision(4))

/** Where the value sits relative to its reference range, as percentages of the bar. */
function rangeGeometry(value: number | null, low: number | null, high: number | null) {
  if (low == null && high == null) return null
  let min: number, max: number
  if (low != null && high != null) {
    const pad = (high - low) * 0.5 || Math.abs(high) * 0.5 || 1
    ;[min, max] = [low - pad, high + pad]
  } else if (high != null) {
    ;[min, max] = [0, high * 1.5 || 1]
  } else {
    ;[min, max] = [0, low! * 2 || 1]
  }
  const pct = (x: number) => Math.min(100, Math.max(0, ((x - min) / (max - min)) * 100))
  return {
    bandStart: low != null ? pct(low) : 0,
    bandEnd: high != null ? pct(high) : 100,
    marker: value != null ? pct(value) : null,
  }
}

function RangeBar({ value, low, high, status }: { value: number | null; low: number | null; high: number | null; status: Status }) {
  const g = rangeGeometry(value, low, high)
  if (!g) return <div className="range-empty">No reference range</div>
  return (
    <div className="range">
      <div className="range-track">
        <div className="range-band" style={{ left: `${g.bandStart}%`, width: `${g.bandEnd - g.bandStart}%` }} />
        {g.marker != null && <div className={`range-marker marker-${status}`} style={{ left: `${g.marker}%` }} />}
      </div>
      <div className="range-labels">
        <span style={{ left: `${g.bandStart}%` }}>{low ?? ''}</span>
        <span style={{ left: `${g.bandEnd}%` }}>{high ?? ''}</span>
      </div>
    </div>
  )
}

interface Props {
  biomarkers: Biomarker[]
  panels: Panel[]
  disabled: boolean
  onChange: () => void
  onConfirm: (corrected: LabResult[]) => void
}

function BiomarkerEditor({ biomarkers, panels, disabled, onChange, onConfirm }: Props) {
  const [drafts, setDrafts] = useState<Draft[]>(() => biomarkers.map(toDraft))
  // Panels start open when they have missing tests or values to check.
  const [open, setOpen] = useState<Set<string>>(
    () =>
      new Set(
        panels
          .filter((p) =>
            biomarkers.some(
              (b) => b.panel === p.id && (!b.found || b.suspect || !['normal', 'unknown'].includes(resultStatus(b))),
            ),
          )
          .map((p) => p.id),
      ),
  )
  const errors = drafts.map(validate)
  const hasErrors = errors.some((e) => Object.keys(e).length > 0)
  const editedCount = biomarkers.filter((b, i) => isEdited(b, drafts[i])).length

  function update(i: number, patch: Partial<Draft>) {
    setDrafts((prev) => prev.map((d, j) => (j === i ? { ...d, ...patch } : d)))
    onChange()
  }

  function toggle(id: string, isOpen: boolean) {
    setOpen((prev) => {
      const next = new Set(prev)
      if (isOpen) next.add(id)
      else next.delete(id)
      return next
    })
  }

  function confirm() {
    const corrected = biomarkers
      .map((b, i) => toResult(b, drafts[i]))
      .filter((r): r is LabResult => r !== null)
    onConfirm(corrected)
  }

  function field(i: number, key: keyof Draft, label: string, className = '') {
    const error = errors[i][key]
    return (
      <label className={`field ${className}`}>
        <span className="field-label">{label}</span>
        <input
          value={drafts[i][key]}
          placeholder="—"
          onChange={(e) => update(i, { [key]: e.target.value })}
          className={error ? 'invalid' : ''}
        />
        {error && <span className="field-error">{error}</span>}
      </label>
    )
  }

  function card(b: Biomarker, i: number) {
    const edited = isEdited(b, drafts[i])
    const preview = toResult(b, drafts[i])
    const status = preview ? resultStatus(preview) : 'unknown'
    const std = preview?.value != null ? standardize(b, preview.value, preview.unit ?? '') : null
    const [low, high] = b.plausible
    const suspect = std != null && (std < low || std > high)
    const converted = std != null && (preview?.unit ?? '') !== (b.canonical_unit ?? '')
    return (
      <div key={b.canonical} className={`biomarker status-${preview ? status : 'missing'}`}>
        <div className="biomarker-head">
          <div>
            <div className="biomarker-name">{b.canonical}</div>
            <div className="biomarker-source">
              {b.found ? `“${b.test}” · page ${b.page}` : 'Not found in report'}
            </div>
          </div>
          {preview ? <StatusPill status={status} /> : <span className="pill pill-missing">No value</span>}
        </div>

        <div className="biomarker-reading">
          {field(i, 'value', 'Value', 'field-value')}
          {field(i, 'unit', 'Unit', 'field-unit')}
        </div>

        {converted && (
          <div className="biomarker-converted">
            ≈ {round(std!)} {b.canonical_unit}
          </div>
        )}
        {suspect && <div className="biomarker-suspect">⚠ Check this value — it's outside what's physically plausible</div>}

        <RangeBar value={preview?.value ?? null} low={preview?.ref_low ?? null} high={preview?.ref_high ?? null} status={status} />

        <div className="biomarker-ref">
          {field(i, 'low', 'Ref low')}
          <span className="ref-dash">–</span>
          {field(i, 'high', 'Ref high')}
        </div>

        {edited && (
          <div className="biomarker-edited">
            <span className="edited-badge">Edited</span>
            <button type="button" className="link" onClick={() => update(i, toDraft(b))}>
              Reset to parsed
            </button>
          </div>
        )}
      </div>
    )
  }

  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h2>Biomarkers by panel</h2>
          <p className="muted">Check these against your report and correct anything that was read incorrectly.</p>
        </div>
      </div>
      <fieldset disabled={disabled} className="plain">
        {panels.length === 0 && <p className="muted">No standard test panels were recognized in this report.</p>}
        {panels.map((panel) => {
          const members = biomarkers.map((b, i) => [b, i] as const).filter(([b]) => b.panel === panel.id)
          if (members.length === 0) return null
          return (
            <details
              key={panel.id}
              className="panel-group"
              open={open.has(panel.id)}
              onToggle={(e) => toggle(panel.id, e.currentTarget.open)}
            >
              <summary>
                <span className="panel-name">{panel.name}</span>
                <span className={`pill pill-panel-${panel.status}`}>
                  {panel.status === 'complete' ? 'Complete' : `${panel.missing.length} not tested`}
                </span>
                <span className="muted small">{members.length} tests</span>
              </summary>
              <div className="biomarker-grid">{members.map(([b, i]) => card(b, i))}</div>
            </details>
          )
        })}
        <div className="card-foot">
          <span className="muted">
            {editedCount > 0 ? `${editedCount} correction${editedCount > 1 ? 's' : ''} made` : 'No corrections made'}
          </span>
          <button type="button" className="primary" onClick={confirm} disabled={hasErrors}>
            {disabled ? 'Generating summary…' : 'Confirm & summarize'}
          </button>
        </div>
      </fieldset>
    </section>
  )
}

export default BiomarkerEditor
