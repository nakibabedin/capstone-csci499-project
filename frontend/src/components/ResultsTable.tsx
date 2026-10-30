import type { LabResult } from './BiomarkerEditor'
import { resultStatus, StatusPill } from './status'

const cell = 'border-b border-slate-200 px-2.5 py-2 align-top'
const tag = 'ml-1.5 rounded px-1.5 py-px align-middle text-[0.68rem] font-semibold'

/** Every result as read from the report, grouped under its section heading. */
export default function ResultsTable({ results }: { results: LabResult[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {['Test', 'Result', 'Reference', 'Status'].map((h) => (
              <th
                key={h}
                className="border-b border-slate-200 px-2.5 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => {
            const newSection = r.section && r.section !== results[i - 1]?.section
            return [
              newSection && (
                <tr key={`s${i}`}>
                  <td
                    colSpan={4}
                    className="bg-(--primary-soft) px-2.5 py-1.5 text-xs font-semibold uppercase tracking-wide text-(--primary)"
                  >
                    {r.section}
                  </td>
                </tr>
              ),
              <tr key={i} className="hover:bg-slate-50">
                <td className={cell}>
                  {r.canonical ?? r.test}
                  {r.derived && <span className={`${tag} bg-slate-100 text-slate-500`}>calculated</span>}
                  {r.suspect && (
                    <span
                      className={`${tag} bg-orange-100 text-orange-700`}
                      title="Outside what's physically plausible; may be misread"
                    >
                      ⚠ check
                    </span>
                  )}
                  {r.canonical && r.canonical !== r.test && <div className="text-xs text-slate-500">{r.test}</div>}
                </td>
                <td className={`${cell} whitespace-nowrap tabular-nums`}>
                  {r.value_text} <span className="text-slate-500">{r.unit}</span>
                </td>
                <td className={`${cell} whitespace-nowrap tabular-nums text-slate-500`}>{r.reference_range ?? '—'}</td>
                <td className={cell}>
                  <StatusPill status={resultStatus(r)} />
                </td>
              </tr>,
            ]
          })}
        </tbody>
      </table>
    </div>
  )
}
