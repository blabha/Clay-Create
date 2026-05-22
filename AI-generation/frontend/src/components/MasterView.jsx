const CELL = 140

export function MasterView({ master, currentTile, completed, cols, rows, onSelectTile }) {
  const displayW = cols * CELL
  const displayH = rows * CELL
  const nTiles = cols * rows

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 2, marginBottom: 4 }}>
          Master Heightmap
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {cols} × {rows} grid — {cols * 256} × {rows * 256} px
        </div>
      </div>

      <div style={{ position: 'relative', width: displayW, height: displayH, borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border)' }}>
        {master
          ? <img src={master} width={displayW} height={displayH}
              style={{ display: 'block', imageRendering: 'pixelated' }} />
          : <div style={{
              width: displayW, height: displayH, background: 'var(--surface2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--text-muted)', fontSize: 13,
            }}>
              No heightmap yet
            </div>
        }

        <svg
          width={displayW} height={displayH}
          style={{ position: 'absolute', inset: 0, pointerEvents: master ? 'all' : 'none' }}
        >
          {/* Grid lines */}
          {Array.from({ length: cols - 1 }, (_, i) => (
            <line key={`v${i}`}
              x1={(i + 1) * CELL} y1={0} x2={(i + 1) * CELL} y2={displayH}
              stroke="rgba(255,255,255,0.30)" strokeWidth={1}
            />
          ))}
          {Array.from({ length: rows - 1 }, (_, i) => (
            <line key={`h${i}`}
              x1={0} y1={(i + 1) * CELL} x2={displayW} y2={(i + 1) * CELL}
              stroke="rgba(255,255,255,0.30)" strokeWidth={1}
            />
          ))}

          {/* Tile overlays */}
          {Array.from({ length: nTiles }, (_, i) => {
            const r = Math.floor(i / cols), c = i % cols
            const x = c * CELL, y = r * CELL
            const isActive = i === currentTile
            const isDone = completed.includes(i)
            return (
              <g key={i} style={{ cursor: 'pointer' }} onClick={() => onSelectTile(i)}>
                <rect
                  x={x} y={y} width={CELL} height={CELL}
                  fill={isActive ? 'rgba(184,112,80,0.20)' : isDone ? 'rgba(107,158,112,0.16)' : 'transparent'}
                  stroke={isActive ? '#B87050' : isDone ? '#6B9E70' : 'rgba(255,255,255,0)'}
                  strokeWidth={isActive ? 2.5 : 1.5}
                />
                <text x={x + 8} y={y + 20}
                  fill={isActive ? '#B87050' : isDone ? '#6B9E70' : 'rgba(255,255,255,0.55)'}
                  fontSize={13} fontWeight="700"
                  style={{ userSelect: 'none', fontFamily: "'DM Sans', system-ui, sans-serif" }}
                >
                  {i + 1}
                </text>
              </g>
            )
          })}
        </svg>
      </div>

      <div style={{ display: 'flex', gap: 14, fontSize: 11, color: 'var(--text-muted)' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: '#B87050', display: 'inline-block' }} />
          Active
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: '#6B9E70', display: 'inline-block' }} />
          Carved
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--border)', display: 'inline-block' }} />
          Pending
        </span>
      </div>
    </div>
  )
}