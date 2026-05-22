import { api } from '../api.js'

export function ExportPanel({ tileIdx, enabled }) {
  function download(url, filename) {
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
        Export Tile {tileIdx + 1}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          disabled={!enabled}
          onClick={() => download(api.exportPngUrl(tileIdx), `tile_${String(tileIdx).padStart(2, '0')}.png`)}
        >
          Download PNG
        </button>
        <button
          disabled={!enabled}
          onClick={() => download(api.exportObjUrl(tileIdx), `tile_${String(tileIdx).padStart(2, '0')}.obj`)}
        >
          Download OBJ
        </button>
      </div>
      <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>
        OBJ: 150 mm × 150 mm × 30 mm, triangulated, 128² resolution
      </p>
    </div>
  )
}
