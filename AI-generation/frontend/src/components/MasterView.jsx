const CELL = 120   // px per tile in the display

export function MasterView({ master, currentTile, completed, cols, rows, onSelectTile }) {
  const displayW = cols * CELL
  const displayH = rows * CELL
  const nTiles = cols * rows

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
        Master Heightmap — {cols} × {rows} grid ({cols * 256} × {rows * 256} px)
      </div>

      <div style={{ position: 'relative', width: displayW, height: displayH, flexShrink: 0 }}>
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

        {/* SVG overlay — grid lines + tile highlighting */}
        <svg
          width={displayW} height={displayH}
          style={{ position: 'absolute', inset: 0, pointerEvents: master ? 'all' : 'none' }}
        >
          {/* vertical grid lines */}
          {Array.from({ length: cols - 1 }, (_, i) => (
            <line key={`v${i}`}
              x1={(i + 1) * CELL} y1={0} x2={(i + 1) * CELL} y2={displayH}
              stroke="rgba(255,255,255,0.3)" strokeWidth={1}
            />
          ))}
          {/* horizontal grid lines */}
          {Array.from({ length: rows - 1 }, (_, i) => (
            <line key={`h${i}`}
              x1={0} y1={(i + 1) * CELL} x2={displayW} y2={(i + 1) * CELL}
              stroke="rgba(255,255,255,0.3)" strokeWidth={1}
            />
          ))}

          {/* tile rects */}
          {Array.from({ length: nTiles }, (_, i) => {
            const r = Math.floor(i / cols)
            const c = i % cols
            const x = c * CELL
            const y = r * CELL
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
                  x={x + 7} y={y + 18}
                  fill={isActive ? '#f0c040' : isDone ? '#3ddc84' : 'rgba(255,255,255,0.5)'}
                  fontSize={13}
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