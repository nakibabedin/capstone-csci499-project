import { useState, type ReactNode } from 'react'
import { summarizePanel, type PanelAnalysis, type Patient } from '../api/reports'
import type { LabResult } from './BiomarkerEditor'
import { StatusPill } from './status'

/** Renders the model's plain-text summary: "- " lines as bullets, "Heading:" lines as headings. */
function SummaryText({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let bullets: string[] = []
  const flush = () => {
    if (bullets.length) blocks.push(<ul key={blocks.length}>{bullets.map((b, i) => <li key={i}>{b}</li>)}</ul>)
    bullets = []
  }
  for (const raw of text.split('\n')) {
    const line = raw.trim()
    if (line.startsWith('- ') || line.startsWith('* ')) {
      bullets.push(line.slice(2))
      continue
    }
    flush()
    if (!line) continue
    const heading = /^([A-Z][^:]{2,60}):\s*(.*)$/.exec(line)
    if (heading) {
      blocks.push(<h3 key={blocks.length}>{heading[1]}</h3>)
      if (heading[2]) blocks.push(<p key={blocks.length}>{heading[2]}</p>)
    } else {
      blocks.push(<p key={blocks.length}>{line}</p>)
    }
  }
  flush()
  return <div className="summary-text">{blocks}</div>
}

interface Props {
  analysis: PanelAnalysis
  /** The results and patient the analysis was computed from, sent along for the summary. */
  results: LabResult[]
  patient: Patient
}

/** One panel's findings, indices and model output, with an on-demand AI summary. */
export default function PanelAnalysisCard({ analysis, results, patient }: Props) {
  const [summary, setSummary] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [summarizing, setSummarizing] = useState(false)
  const { name, coverage, findings, indices, model, inputs } = analysis

  async function summarize() {
    setSummary('')
    setError(null)
    setSummarizing(true)
    try {
      const res = await summarizePanel(analysis.id, results, patient)
      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => ({}))
        setError(data.error ?? 'Failed to generate a summary.')
        return
      }
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        setSummary((prev) => prev + value)
      }
    } catch {
      setError('Could not reach the server while summarizing.')
    } finally {
      setSummarizing(false)
    }
  }

  return (
    <section className="card panel-analysis">
      <div className="card-head">
        <div>
          <h2>{name}</h2>
          <p className="muted">{Math.round(coverage * 100)}% of this panel's tests are in the report</p>
        </div>
        <button type="button" className="primary" onClick={summarize} disabled={summarizing}>
          {summarizing ? 'Summarizing…' : summary ? 'Summarize again' : 'Summarize this panel'}
        </button>
      </div>

      {findings.length > 0 ? (
        <ul className="findings">
          {findings.map((f, i) => (
            <li key={i}>
              <StatusPill status={f.status} />
              <span className="finding-test">{f.test}</span>
              <span className="num">
                {f.value_text} <span className="muted">{f.unit}</span>
              </span>
              {f.reference_range && <span className="muted small">ref {f.reference_range}</span>}
              {f.suspect && <span className="tag tag-warn">⚠ check value</span>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No out-of-range results in this panel.</p>
      )}

      {indices.length > 0 && (
        <div className="indices">
          {indices.map((x) => (
            <div key={x.name} className="index" title={x.note}>
              <div className="index-value">{x.value}</div>
              <div className="index-name">{x.name}</div>
            </div>
          ))}
        </div>
      )}

      {model && (
        <div className="model-output">
          <span className="field-label">Model</span>
          <pre>{JSON.stringify(model, null, 2)}</pre>
        </div>
      )}

      {inputs.missing.length > 0 && <p className="muted small">Not in this report: {inputs.missing.join(', ')}</p>}

      {(summarizing || summary || error) && (
        <div className="summary">
          {summarizing && !summary && <span className="spinner" aria-label="Generating" />}
          {error ? <div className="alert">{error}</div> : summary && <SummaryText text={summary} />}
          <p className="disclaimer">
            AI-generated summary for information only — not medical advice. Please review your results with your doctor.
          </p>
        </div>
      )}
    </section>
  )
}
