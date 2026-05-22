import { useRef, useState } from 'react'
import { DrawingCanvas } from './DrawingCanvas.jsx'
import { DeviationView } from './DeviationView.jsx'
import { ExportPanel } from './ExportPanel.jsx'
import { Surface3D } from './Surface3D.jsx'

export function TileWorkflow({ tile, surfaceData, onDrawSubmit, onUploadScan, onLoadSurface, loading }) {
  const [mode, setMode] = useState('draw')   // 'draw' | 'upload'
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 18, fontWeight: 700 }}>{tileLabel}</span>
        <span className={`tag ${isDone ? 'tag-done' : 'tag-active'}`}>
          {isDone ? 'carved' : 'in progress'}
        </span>
        {isDone && (
          <button style={{ marginLeft: 'auto', fontSize: 12 }} onClick={() => onLoadSurface(tile.idx)}>
            Refresh 3D
          </button>
        )}
      </div>

      {/* Main row: intended + work panel */}
      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        {/* Intended heightmap */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.8 }}>
            Intended
          </div>
          {tile.intended && (
            <img
              src={tile.intended}
              width={256}
              height={256}
              style={{ imageRendering: 'pixelated', borderRadius: 6, border: '1px solid var(--border)' }}
            />
          )}
        </div>

        {/* Scan input panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, flex: 1, minWidth: 340 }}>
          {/* Mode tabs */}
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={() => setMode('draw')}
              style={mode === 'draw' ? { background: 'var(--accent)', color: '#111' } : {}}
            >
              Paint Deviations
            </button>
            <button
              onClick={() => setMode('upload')}
              style={mode === 'upload' ? { background: 'var(--accent)', color: '#111' } : {}}
            >
              Upload Scan
            </button>
          </div>

          {mode === 'draw' && (
            <DrawingCanvas
              tileImage={tile.intended}
              onSubmit={(dataUrl) => onDrawSubmit(tile.idx, dataUrl)}
              loading={loading}
            />
          )}

          {mode === 'upload' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Upload a grayscale PNG (depth camera output) to use as the scanned result.
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
              >
                {loading ? 'Processing…' : 'Choose PNG file…'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Deviation comparison (shown after tile is processed) */}
      {isDone && (
        <div className="card">
          <DeviationView tile={tile} />
        </div>
      )}

      {/* 3D Surface */}
      <Surface3D surfaceData={surfaceData} />

      {/* Export */}
      <ExportPanel tileIdx={tile.idx} enabled={!!tile.intended} />
    </div>
  )
}
