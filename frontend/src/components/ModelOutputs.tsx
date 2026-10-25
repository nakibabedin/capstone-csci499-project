import type { ModelOutput } from '../api/reports'

/** Formula and model results as tiles: value and unit, then what it means (or what it needs). */
export default function ModelOutputs({ outputs }: { outputs: ModelOutput[] }) {
  if (outputs.length === 0) return null
  return (
    <div className="model-outputs">
      {outputs.map((m) => (
        <div key={m.name} className={`model-output ${m.value == null ? 'model-output-missing' : ''}`}>
          <div className="model-output-head">
            <span className="model-output-name">{m.name}</span>
            {m.value != null && (
              <span className="model-output-value">
                {m.value} {m.unit && <span className="muted small">{m.unit}</span>}
              </span>
            )}
          </div>
          <p className="small">{m.error ? 'Could not be calculated.' : m.interpretation}</p>
        </div>
      ))}
    </div>
  )
}
