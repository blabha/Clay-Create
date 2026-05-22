const DISPLAY = 450   // px — rendered size of the master canvas
const CELL = DISPLAY / 3

export function MasterView({ master, currentTile, completed, onSelectTile }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
        Master Heightmap (768 px)
      </div>

      <div style={{ position: 'relative', width: DISPLAY, height: DISPLAY, flexShrink: 0 }}>
        {master
          ? <img src={master} width={DISPLAY} height={DISPLAY}
              style={{ display: 'block', imageRendering: 'pixelated' }} />
          : <div style={{
              width: DISPLAY, height: DISPLAY, background: 'var(--surface2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--text-muted)', fontSize: 13,
            }}>
              No heightmap yet
            </div>
        }

        {/* SVG overlay — grid + tile highlighting */}
        <svg
          width={DISPLAY} height={DISPLAY}
          style={{ position: 'absolute', inset: 0, pointerEvents: master ? 'all' : 'none' }}
        >
          {/* grid lines */}
          {[1, 2].map(i => (
            <g key={i}>
              <line x1={i * CELL} y1={0} x2={i * CELL} y2={DISPLAY}
                stroke="rgba(255,255,255,0.3)" strokeWidth={1} />
              <line x1={0} y1={i * CELL} x2={DISPLAY} y2={i * CELL}
                stroke="rgba(255,255,255,0.3)" strokeWidth={1} />
            </g>
          ))}

          {/* tile rects */}
          {Array.from({ length: 9 }, (_, i) => {
            const r = Math.floor(i / 3), c = i % 3
            const x = c * CELL, y = r * CELL
            const isActive = i === currentTile
            const isDone = completed.includes(i)
            return (
              <g key={i} style={{ cursor: 'pointer' }} onClick={() => onSelectTile(i)}>
                <rect
                  x={x} y={y} width={CELL} height={CELL}
                  fill={isActive ? 'rgba(240,192,64,0.18)' : isDone ? 'rgba(61,220,132,0.12)' : 'transparent'}
                  stroke={isActive ? '#f0c040' : isDone ? '#3ddc84' : 'rgba(255,255,255,0)'}
                  strokeWidth={isActive ? 2.5 : 1.5}
                />
                <text
                  x={x + 8} y={y + 20}
                  fill={isActive ? '#f0c040' : isDone ? '#3ddc84' : 'rgba(255,255,255,0.6)'}
                  fontSize={15}
                  fontWeight="bold"
                  style={{ userSelect: 'none' }}
                >
                  {i + 1}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      <div style={{ display: 'flex', gap: 12, fontSize: 12 }}>
        <span style={{ color: '#f0c040' }}>■ active</span>
        <span style={{ color: '#3ddc84' }}>■ carved</span>
        <span style={{ color: 'var(--text-muted)' }}>■ pending</span>
      </div>
    </div>
  )
}
