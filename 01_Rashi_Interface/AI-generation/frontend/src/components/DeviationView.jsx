const IMG_SIZE = 200

function HeightmapImg({ src, label }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>
        {label}
      </div>
      {src
        ? <img src={src} width={IMG_SIZE} height={IMG_SIZE}
            style={{ imageRendering: 'pixelated', borderRadius: 4, border: '1px solid var(--border)' }} />
        : <div style={{
            width: IMG_SIZE, height: IMG_SIZE,
            background: 'var(--surface2)', borderRadius: 4,
            border: '1px dashed var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--text-muted)', fontSize: 11,
          }}>
            —
          </div>
      }
    </div>
  )
}

export function DeviationView({ tile }) {
  if (!tile) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
        Tile {tile.idx + 1} — Comparison
      </div>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <HeightmapImg src={tile.intended}     label="Intended" />
        <HeightmapImg src={tile.scanned}      label="Scanned" />
        <HeightmapImg src={tile.deviation_color} label="Deviation" />
      </div>
      {tile.deviation_color && (
        <div style={{ display: 'flex', gap: 14, fontSize: 11, alignItems: 'center' }}>
          <span style={{ color: '#4fa8ff' }}>■ under-carved</span>
          <span style={{ color: '#7a7f8e' }}>■ neutral</span>
          <span style={{ color: '#ff6b6b' }}>■ over-raised</span>
        </div>
      )}
    </div>
  )
}
