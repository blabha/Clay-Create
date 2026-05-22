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
  const [wallConfig, setWallConfig] = useState(null)
  const [selectedTile, setSelectedTile] = useState(0)
  const [surface3d, setSurface3d] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

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
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--bg)',
    }}>

      {/* ── Header ── */}
      <header style={{
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '0 28px',
        height: 60,
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface)',
        flexShrink: 0,
      }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <span style={{
            fontSize: 22,
            fontWeight: 700,
            letterSpacing: 2,
            textTransform: 'uppercase',
            color: 'var(--accent)',
          }}>
            Clay Create
          </span>
          {appState.initialized && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)', letterSpacing: 0.5 }}>
              {cols} × {rows} grid — {cols * 15} × {rows * 15} cm
            </span>
          )}
        </div>

        {/* Right side */}
        {(wallConfig || appState.initialized) && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 10, alignItems: 'center' }}>
            {appState.initialized && (
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {appState.completed.length}/{nTiles} carved
              </span>
            )}
            {allDone && (
              <span style={{ fontSize: 12, color: 'var(--green)', fontWeight: 600, letterSpacing: 0.3 }}>
                Complete
              </span>
            )}
            <button className="danger" onClick={handleReset} style={{ padding: '6px 14px', fontSize: 12 }}>
              Reset
            </button>
          </div>
        )}
      </header>

      {/* ── Body ── */}
      <main style={{ flex: 1, padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* Step 1: Wall setup */}
        {!wallConfig && !appState.initialized && (
          <div style={{ maxWidth: 560 }}>
            <div style={{ marginBottom: 20 }}>
              <p style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 2, marginBottom: 6 }}>
                Step 1
              </p>
              <h2 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text)' }}>Define your wall</h2>
            </div>
            <div className="card">
              <WallSetup onConfirm={setWallConfig} />
            </div>
          </div>
        )}

        {/* Step 2: Image upload */}
        {wallConfig && !appState.initialized && (
          <div style={{ maxWidth: 560 }}>
            <div style={{ marginBottom: 20, display: 'flex', alignItems: 'center', gap: 16 }}>
              <div>
                <p style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 2, marginBottom: 6 }}>
                  Step 2
                </p>
                <h2 style={{ fontSize: 22, fontWeight: 600, color: 'var(--text)' }}>Upload reference image</h2>
              </div>
              <button
                style={{ marginLeft: 'auto', fontSize: 12, padding: '6px 12px' }}
                onClick={() => setWallConfig(null)}
                disabled={loading}
              >
                ← Change layout
              </button>
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 12 }}>
              {wallConfig.cols} × {wallConfig.rows} grid — {wallConfig.cols * wallConfig.rows} blocks, {wallConfig.cols * 15} × {wallConfig.rows * 15} cm
            </p>
            <div className="card">
              <ImageUpload onGenerate={handleGenerate} loading={loading} />
            </div>
          </div>
        )}

        {/* Error banner */}
        {error && (
          <div style={{
            background: 'rgba(181,80,58,0.08)',
            border: '1px solid rgba(181,80,58,0.22)',
            color: 'var(--red)',
            borderRadius: 10,
            padding: '12px 16px',
            fontSize: 13,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
          }}>
            {error}
          </div>
        )}

        {/* Main work area */}
        {appState.initialized && (
          <div style={{ display: 'flex', gap: 20, alignItems: 'stretch', flex: 1 }}>

            {/* Left: master heightmap */}
            <div className="card" style={{ flexShrink: 0, alignSelf: 'flex-start' }}>
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
            <div className="card" style={{ flex: 1, minWidth: 420, display: 'flex', flexDirection: 'column', gap: 16 }}>

              {/* Tile selector strip */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
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
                          : isDone ? 'rgba(107,158,112,0.15)' : isActive ? 'rgba(184,112,80,0.10)' : 'var(--surface2)',
                        color: isSelected ? '#FAF8F5' : isDone ? 'var(--green)' : 'var(--text)',
                        fontWeight: isSelected || isDone ? 700 : 400,
                        border: `2px solid ${isSelected ? 'var(--accent)' : isActive ? 'var(--accent)' : isDone ? 'var(--green)' : 'var(--border)'}`,
                        borderRadius: 8,
                        fontSize: 13,
                      }}
                    >
                      {t.idx + 1}
                    </button>
                  )
                })}
              </div>

                  <TileWorkflow
                tile={currentTile}
                surfaceData={surface3d}
                onUploadScan={handleUploadScan}
                onLoadSurface={handleLoadSurface}
                onRegenerate={handleRegenerateAll}
                hasUncarved={hasUncarved}
                loading={loading}
              />
            </div>
          </div>
        )}

        {/* Loading — before initialization */}
        {loading && !appState.initialized && (
          <div style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center',
            gap: 14, color: 'var(--text-muted)', paddingTop: 60,
          }}>
            <div style={{
              width: 40, height: 40, borderRadius: '50%',
              border: '3px solid var(--border)',
              borderTopColor: 'var(--accent)',
              animation: 'spin 0.9s linear infinite',
            }} />
            <p style={{ fontSize: 13 }}>Processing image — MiDaS depth estimation in progress…</p>
          </div>
        )}
      </main>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  )
}