import { useState } from 'react'

const PRESETS = [
  { label: 'Waves',    text: 'concentric waves ripples water surface pattern' },
  { label: 'Dots',     text: 'evenly spaced circular dots bumps raised spheres pattern' },
  { label: 'Lines',    text: 'parallel lines ridges grooves striped surface pattern' },
  { label: 'Grid',     text: 'square grid crosshatch lattice recessed lines pattern' },
  { label: 'Scales',   text: 'overlapping fish scales scallop repeating arc pattern' },
  { label: 'Hex',      text: 'hexagonal honeycomb cells raised edges geometric pattern' },
  { label: 'Organic',  text: 'organic cellular voronoi cracked mud irregular pattern' },
  { label: 'Woven',    text: 'woven fabric basket weave interlaced threads pattern' },
]

export function PromptInput({ onGenerate, loading }) {
  const [prompt, setPrompt] = useState('concentric waves ripples water surface pattern')
  const [steps, setSteps] = useState(25)

  function handlePreset(text) {
    setPrompt(text)
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (prompt.trim()) onGenerate(prompt.trim(), steps)
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

      {/* Preset chips */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {PRESETS.map(p => (
          <button
            key={p.label}
            type="button"
            onClick={() => handlePreset(p.text)}
            style={{
              padding: '4px 12px',
              fontSize: 12,
              background: prompt === p.text ? 'var(--accent)' : 'var(--surface2)',
              color: prompt === p.text ? '#111' : 'var(--text-muted)',
              border: `1px solid ${prompt === p.text ? 'var(--accent)' : 'var(--border)'}`,
              borderRadius: 20,
              fontWeight: prompt === p.text ? 700 : 400,
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Custom prompt */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Custom description (combined with macro texture prefix automatically)
        </label>
        <input
          type="text"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder="e.g. honeycomb cells raised edges geometric pattern"
          disabled={loading}
        />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label style={{ whiteSpace: 'nowrap' }}>Steps</label>
          <input
            type="number"
            value={steps}
            min={10}
            max={50}
            onChange={e => setSteps(Number(e.target.value))}
            disabled={loading}
            style={{ width: 70 }}
          />
        </div>
        <button
          type="submit"
          className="primary"
          disabled={loading || !prompt.trim()}
          style={{ flex: 1 }}
        >
          {loading ? 'Generating…' : 'Generate Heightmap'}
        </button>
      </div>

      {loading && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
          SD → MiDaS → CLAHE enhance… tiles will appear when done.
        </p>
      )}
    </form>
  )
}
