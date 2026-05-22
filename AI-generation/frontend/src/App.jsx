import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { ImageUpload } from './components/ImageUpload.jsx'
import { MasterView } from './components/MasterView.jsx'
import { TileWorkflow } from './components/TileWorkflow.jsx'
import { WallSetup } from './components/WallSetup.jsx'

const EMPTY_STATE = {
  initialized: false,
  cols: 3,
  rows: 3,
  current_tile: 0,
  completed: [],
  master: null,
  tiles: [],
}

export default function App() {
  const [appState, setAppState] = useState(EMPTY_STATE)
  const [wallConfig, setWallConfig] = useState(null)   // { cols, rows, widthCm, heightCm }
  const [selectedTile, setSelectedTile] = useState(0)
  const [surface3d, setSurface3d] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Restore any existing backend session on mount
  useEffect(() => {
    api.getState().then(s => {
      setAppState(s)
      if (s.initialized) {
        setWallConfig({ cols: s.cols, rows: s.rows, widthCm: s.cols * 15, heightCm: s.rows * 15 })
        setSelectedTile(s.current_tile ?? 0)
      }
    }).catch(() => {})
  }, [])

  const withLoading = useCallback(async (fn) => {
    setLoading(true)
    setError(null)
    try {
      const newState = await fn()
      setAppState(newState)
      if (newState.initialized) {
        setSelectedTile(t => newState.completed.includes(t) ? t : (newState.current_tile ?? t))
      }
      return newState
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  async function handleGenerate(imageFile) {
    setSurface3d(null)
    await withLoading(() => api.generate(imageFile, wallConfig.cols, wallConfig.rows))
    setSelectedTile(0)
  }

  async function handleDrawSubmit(idx, dataUrl) {
    await withLoading(() => api.drawScan(idx, dataUrl))
    handleLoadSurface(idx)
  }

  async function handleUploadScan(idx, file) {
    await withLoading(() => api.uploadScan(idx, file))
    handleLoadSurface(idx)
  }

  async function handleRegenerate(idx) {
    await withLoading(() => api.regenerateTile(idx))
  }

  async function handleRegenerateAll() {
    await withLoading(() => api.regenerateAll())
  }

  async function handleLoadSurface(idx) {
    try {
      const data = await api.getSurface3d(idx)
      setSurface3d(data)
    } catch (_) {}
  }

  function handleSelectTile(idx) {
    setSelectedTile(idx)
    handleLoadSurface(idx)
  }

  function handleReset() {
    api.reset().then(s => {
      setAppState(s)
      setSurface3d(null)
      setSelectedTile(0)
      setWallConfig(null)
    })
  }

  const cols = appState.initialized ? appState.cols : (wallConfig?.cols ?? 3)
  const rows = appState.initialized ? appState.rows : (wallConfig?.rows ?? 3)
  const nTiles = appState.tiles.length
  const currentTile = appState.tiles[selectedTile] ?? null
  const allDone = appState.initialized && appState.completed.length === nTiles
  const hasUncarved = appState.initialized && appState.completed.length < nTiles

  return (
    <div style={{ minHeight: '100vh', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Header ── */}
      <header style={{ display: 'flex', alignItems: 'center', gap: 16, borderBottom: '1px solid var(--border)', paddingBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, letterSpacing: -0.5 }}>Clay Relief Pipeline</h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {appState.initialized
              ? `${cols} × ${rows} grid — ${cols * 15} × ${rows * 15} cm wall`
              : '15 cm × 15 cm × 3 cm clay blocks'}
          </p>
        </div>
        {(wallConfig || appState.initialized) && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
            {appState.initialized && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {appState.completed.length}/{nTiles} tiles carved
              </span>
            )}
            {allDone && (
              <span style={{ fontSize: 12, color: 'var(--green)', fontWeight: 600 }}>All done!</span>
            )}
            <button className="danger" onClick={handleReset}>Reset</button>
          </div>
        )}
      </header>

      {/* ── Step 1: Wall setup ── */}
      {!wallConfig && !appState.initialized && (
        <section className="card">
          <WallSetup onConfirm={setWallConfig} />
        </section>
      )}

      {/* ── Step 2: Image upload ── */}
      {wallConfig && !appState.initialized && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button
              style={{ fontSize: 12, padding: '4px 10px' }}
              onClick={() => setWallConfig(null)}
              disabled={loading}
            >
              ← Change layout
            </button>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              {wallConfig.cols} × {wallConfig.rows} grid ({wallConfig.cols * wallConfig.rows} blocks, {wallConfig.cols * 15} × {wallConfig.rows * 15} cm)
            </span>
          </div>
          <section className="card">
            <ImageUpload onGenerate={handleGenerate} loading={loading} />
          </section>
        </>
      )}

      {/* ── Error banner ── */}
      {error && (
        <div style={{
          background: 'rgba(255,107,107,0.12)',
          border: '1px solid rgba(255,107,107,0.35)',
          color: 'var(--red)',
          borderRadius: 8,
          padding: '10px 16px',
          fontSize: 13,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}>
          {error}
        </div>
      )}

      {/* ── Main work area ── */}
      {appState.initialized && (
        <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          {/* Left: master heightmap */}
          <div className="card" style={{ flexShrink: 0 }}>
            <MasterView
              master={appState.master}
              currentTile={appState.current_tile}
              completed={appState.completed}
              cols={cols}
              rows={rows}
              onSelectTile={handleSelectTile}
            />
          </div>

          {/* Right: tile workflow */}
          <div className="card" style={{ flex: 1, minWidth: 400 }}>
            {/* Tile selector strip */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
              {appState.tiles.map(t => {
                const isDone = appState.completed.includes(t.idx)
                const isActive = t.idx === appState.current_tile
                const isSelected = t.idx === selectedTile
                return (
                  <button
                    key={t.idx}
                    onClick={() => handleSelectTile(t.idx)}
                    style={{
                      width: 36, height: 36, padding: 0,
                      background: isSelected
                        ? 'var(--accent)'
                        : isDone ? 'rgba(61,220,132,0.18)' : isActive ? 'rgba(240,192,64,0.12)' : 'var(--surface2)',
                      color: isSelected ? '#111' : isDone ? 'var(--green)' : 'var(--text)',
                      fontWeight: isSelected || isDone ? 700 : 400,
                      border: `2px solid ${isSelected ? 'var(--accent)' : isActive ? 'var(--accent)' : isDone ? 'var(--green)' : 'var(--border)'}`,
                    }}
                  >
                    {t.idx + 1}
                  </button>
                )
              })}
            </div>

            {hasUncarved && (
              <div style={{ marginBottom: 8 }}>
                <button
                  className="primary"
                  onClick={handleRegenerateAll}
                  disabled={loading}
                  style={{ width: '100%' }}
                  title="Re-run harmonic interpolation for all uncarved tiles using scanned neighbours"
                >
                  {loading ? 'Regenerating…' : 'Regenerate Design'}
                </button>
              </div>
            )}

            <TileWorkflow
              tile={currentTile}
              surfaceData={surface3d}
              onDrawSubmit={handleDrawSubmit}
              onUploadScan={handleUploadScan}
              onLoadSurface={handleLoadSurface}
              loading={loading}
            />
          </div>
        </div>
      )}

      {/* ── Loading state ── */}
      {loading && !appState.initialized && (
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          gap: 12, color: 'var(--text-muted)', paddingTop: 40,
        }}>
          <div style={{ fontSize: 48 }}>◻◻◻</div>
          <p>Processing image… this may take a moment on first run (MiDaS loading).</p>
        </div>
      )}
    </div>
  )
}