import { useRef } from 'react'
import { DeviationView } from './DeviationView.jsx'
import { ExportPanel } from './ExportPanel.jsx'
import { Surface3D } from './Surface3D.jsx'

const IMG_SIZE = 180

function HeightmapImg({ src, label }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
        {label}
      </div>
      {src
        ? <img src={src} width={IMG_SIZE} height={IMG_SIZE}
            style={{ imageRendering: 'pixelated', borderRadius: 6, border: '1px solid var(--border)' }} />
        : <div style={{
            width: IMG_SIZE, height: IMG_SIZE,
            background: 'var(--surface2)', borderRadius: 6,
            border: '1px dashed var(--border)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--text-muted)', fontSize: 11,
          }}>—</div>
      }
    </div>
  )
}

export function TileWorkflow({ tile, surfaceData, onUploadScan, onLoadSurface, onRegenerate, hasUncarved, loading }) {
  const fileRef = useRef(null)

  if (!tile) return null

  const isDone = !!tile.scanned
  const tileLabel = `Tile ${tile.idx + 1}`

  function handleFileChange(e) {
    const f = e.target.files?.[0]
    if (f) onUploadScan(tile.idx, f)
    e.target.value = ''
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 18, fontWeight: 600 }}>{tileLabel}</span>
        <span className={`tag ${isDone ? 'tag-done' : 'tag-active'}`}>
          {isDone ? 'Carved' : 'In progress'}
        </span>
        {isDone && (
          <button style={{ marginLeft: 'auto', fontSize: 12, padding: '6px 12px' }} onClick={() => onLoadSurface(tile.idx)}>
            Refresh 3D
          </button>
        )}
      </div>

      {/* Intended heightmap + upload */}
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
            Intended
          </div>
          {tile.intended && (
            <img
              src={tile.intended}
              width={256} height={256}
              style={{ imageRendering: 'pixelated', borderRadius: 8, border: '1px solid var(--border)' }}
            />
          )}
        </div>

        {/* Upload scan */}
        {!isDone && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, flex: 1, minWidth: 200 }}>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
              Upload Scan
            </div>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6 }}>
              Upload a grayscale PNG from the depth camera to use as the scanned result.
            </p>
            <input
              ref={fileRef}
              type="file"
              accept=".png,image/png"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <button
              className="primary"
              onClick={() => fileRef.current?.click()}
              disabled={loading}
              style={{ alignSelf: 'flex-start', minWidth: 160 }}
            >
              {loading ? 'Processing…' : 'Choose PNG file…'}
            </button>
          </div>
        )}
      </div>

      {/* Design Adaptation — shown when the design has been seam-corrected */}
      {!isDone && tile.regen_diff && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1 }}>
            Design Adaptation
          </div>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            <HeightmapImg src={tile.original_intended} label="Original" />
            <HeightmapImg src={tile.intended}          label="Adapted" />
            <HeightmapImg src={tile.regen_diff}        label="Change" />
          </div>
          <div style={{ display: 'flex', gap: 14, fontSize: 11, alignItems: 'center' }}>
            <span style={{ color: '#4fa8ff' }}>■ raised</span>
            <span style={{ color: 'var(--text-muted)' }}>■ unchanged</span>
            <span style={{ color: '#ff6b6b' }}>■ lowered</span>
          </div>
        </div>
      )}

      {/* Deviation comparison — shown after tile is carved */}
      {isDone && (
        <DeviationView tile={tile} />
      )}

      {/* Regenerate Design */}
      {hasUncarved && (
        <div style={{ paddingTop: 4 }}>
          <button
            onClick={onRegenerate}
            disabled={loading}
            style={{ width: '100%' }}
          >
            {loading ? 'Regenerating…' : 'Regenerate Design'}
          </button>
        </div>
      )}

      {/* 3D Surface */}
      <Surface3D surfaceData={surfaceData} />

      {/* Export */}
      <ExportPanel tileIdx={tile.idx} enabled={!!tile.intended} />
    </div>
  )
}