import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { MasterView } from './components/MasterView.jsx'
import { PromptInput } from './components/PromptInput.jsx'
import { TileWorkflow } from './components/TileWorkflow.jsx'

const EMPTY_STATE = {
  initialized: false,
  current_tile: 0,
  completed: [],
  master: null,
  tiles: [],
}

export default function App() {
  const [appState, setAppState] = useState(EMPTY_STATE)
  const [selectedTile, setSelectedTile] = useState(0)
  const [surface3d, setSurface3d] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Load state once on mount (in case backend already has session)
  useEffect(() => {
    api.getState()
      .then(s => { setAppState(s); if (s.initialized) setSelectedTile(s.current_tile ?? 0) })
      .catch(() => {})
  }, [])

  const withLoading = useCallback(async (fn) => {
    setLoading(true)
    setError(null)
    try {
      const newState = await fn()
      setAppState(newState)
      // Default selection: current_tile or 0
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

  async function handleGenerate(prompt, steps) {
    setSurface3d(null)
    await withLoading(() => api.generate(prompt, steps))
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

  const currentTile = appState.tiles[selectedTile] ?? null
  const allDone = appState.initialized && appState.completed.length === 9

  return (
    <div style={{ minHeight: '100vh', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* ── Header ── */}
      <header style={{ display: 'flex', alignItems: 'center', gap: 16, borderBottom: '1px solid var(--border)', paddingBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, letterSpacing: -0.5 }}>Clay Relief Pipeline</h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>3 × 3 tile carving simulation</p>
        </div>
        {appState.initialized && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {appState.completed.length}/9 tiles carved
            </span>
            {allDone && (
              <span style={{ fontSize: 12, color: 'var(--green)', fontWeight: 600 }}>
                All done!
              </span>
            )}
            <button
              className="danger"
              onClick={() => { api.reset().then(s => { setAppState(s); setSurface3d(null); setSelectedTile(0) }) }}
            >
              Reset
            </button>
          </div>
        )}
      </header>

      {/* ── Prompt input ── */}
      <section className="card">
        <PromptInput onGenerate={handleGenerate} loading={loading} />
      </section>

      {/* ── Error banner ── */}
      {error && (
        <div style={{
          background: 'rgba(255,107,107,0.12)',
          border: '1px solid rgba(255,107,107,0.35)',
          color: 'var(--red)',
          borderRadius: 8,
          padding: '10px 16px',
          fontSize: 13,
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

      {/* ── Empty state ── */}
      {!appState.initialized && !loading && (
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          gap: 12, color: 'var(--text-muted)', paddingTop: 40,
        }}>
          <div style={{ fontSize: 48 }}>◻◻◻</div>
          <p>Enter a prompt above and click Generate to start the pipeline.</p>
        </div>
      )}
    </div>
  )
}
