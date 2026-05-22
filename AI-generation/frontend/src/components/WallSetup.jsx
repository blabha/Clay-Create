import { useState } from 'react'

const BLOCK_CM = 15

export function WallSetup({ onConfirm }) {
  const [widthCm, setWidthCm] = useState('')
  const [heightCm, setHeightCm] = useState('')

  const cols = Math.floor(Number(widthCm) / BLOCK_CM) || 0
  const rows = Math.floor(Number(heightCm) / BLOCK_CM) || 0
  const nBlocks = cols * rows
  const valid = cols >= 1 && rows >= 1

  const actualW = cols * BLOCK_CM
  const actualH = rows * BLOCK_CM

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Wall Dimensions</h2>
        <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Clay blocks are {BLOCK_CM} cm × {BLOCK_CM} cm × 3 cm. Enter your wall size to calculate the grid.
        </p>
      </div>

      {/* Inputs */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Wall width (cm)</label>
          <input
            type="number"
            value={widthCm}
            min={BLOCK_CM}
            step={1}
            onChange={e => setWidthCm(e.target.value)}
            placeholder={`e.g. ${BLOCK_CM * 4}`}
            style={{ width: 140 }}
          />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Wall height (cm)</label>
          <input
            type="number"
            value={heightCm}
            min={BLOCK_CM}
            step={1}
            onChange={e => setHeightCm(e.target.value)}
            placeholder={`e.g. ${BLOCK_CM * 3}`}
            style={{ width: 140 }}
          />
        </div>
      </div>

      {/* Grid preview */}
      {valid ? (
        <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start', flexWrap: 'wrap' }}>
          {/* Mini grid */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
              Grid preview
            </div>
            <div style={{
              display: 'grid',
              gridTemplateColumns: `repeat(${cols}, 28px)`,
              gridTemplateRows: `repeat(${rows}, 28px)`,
              gap: 3,
            }}>
              {Array.from({ length: nBlocks }, (_, i) => (
                <div
                  key={i}
                  style={{
                    width: 28, height: 28,
                    background: 'var(--surface2)',
                    border: '1px solid var(--border)',
                    borderRadius: 3,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 9, color: 'var(--text-muted)',
                  }}
                >
                  {i + 1}
                </div>
              ))}
            </div>
          </div>

          {/* Summary */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
              Summary
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
              <span>
                <span style={{ color: 'var(--text-muted)' }}>Grid: </span>
                <span style={{ fontWeight: 600, color: 'var(--accent)' }}>{cols} × {rows}</span>
              </span>
              <span>
                <span style={{ color: 'var(--text-muted)' }}>Blocks: </span>
                <span style={{ fontWeight: 600 }}>{nBlocks}</span>
              </span>
              <span>
                <span style={{ color: 'var(--text-muted)' }}>Covered area: </span>
                <span style={{ fontWeight: 600 }}>{actualW} × {actualH} cm</span>
              </span>
              {(Number(widthCm) % BLOCK_CM !== 0 || Number(heightCm) % BLOCK_CM !== 0) && (
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                  Rounded down — partial blocks excluded
                </span>
              )}
            </div>
          </div>
        </div>
      ) : (
        widthCm || heightCm ? (
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Minimum {BLOCK_CM} cm in each dimension to fit at least one block.
          </p>
        ) : null
      )}

      <button
        className="primary"
        disabled={!valid}
        onClick={() => onConfirm({ cols, rows, widthCm: Number(widthCm), heightCm: Number(heightCm) })}
        style={{ alignSelf: 'flex-start', minWidth: 160 }}
      >
        Confirm layout →
      </button>
    </div>
  )
}