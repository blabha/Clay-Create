import { useCallback, useEffect, useRef, useState } from 'react'

const CANVAS_SIZE = 320   // display size; internal is 256×256

export function DrawingCanvas({ tileImage, onSubmit, loading }) {
  const canvasRef = useRef(null)
  const painting = useRef(false)
  // Use refs for brush state to avoid stale closures in mouse handlers
  const brush = useRef({ size: 22, mode: 'raise', opacity: 0.35 })
  const [brushState, setBrushState] = useState({ size: 22, mode: 'raise', opacity: 0.35 })

  // Sync ref and React state
  function updateBrush(patch) {
    brush.current = { ...brush.current, ...patch }
    setBrushState(s => ({ ...s, ...patch }))
  }

  // Load tile image onto canvas when it changes
  useEffect(() => {
    if (!tileImage || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const img = new Image()
    img.onload = () => ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    img.src = tileImage
  }, [tileImage])

  const getCanvasXY = useCallback((e) => {
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const sx = canvas.width / rect.width
    const sy = canvas.height / rect.height
    return [
      (e.clientX - rect.left) * sx,
      (e.clientY - rect.top) * sy,
    ]
  }, [])

  const drawAt = useCallback((e) => {
    if (!painting.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const [x, y] = getCanvasXY(e)
    ctx.save()
    ctx.globalAlpha = brush.current.opacity
    ctx.fillStyle = brush.current.mode === 'raise' ? '#ffffff' : '#000000'
    ctx.beginPath()
    ctx.arc(x, y, brush.current.size, 0, Math.PI * 2)
    ctx.fill()
    ctx.restore()
  }, [getCanvasXY])

  const handleMouseDown = useCallback((e) => {
    painting.current = true
    drawAt(e)
  }, [drawAt])

  const handleMouseUp = useCallback(() => { painting.current = false }, [])

  function handleSubmit() {
    const dataUrl = canvasRef.current.toDataURL('image/png')
    onSubmit(dataUrl)
  }

  function handleReset() {
    if (!tileImage || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const img = new Image()
    img.onload = () => ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    img.src = tileImage
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <canvas
        ref={canvasRef}
        width={256}
        height={256}
        style={{
          width: CANVAS_SIZE,
          height: CANVAS_SIZE,
          border: '2px solid var(--border)',
          borderRadius: 6,
          cursor: 'crosshair',
          imageRendering: 'pixelated',
          background: '#000',
          touchAction: 'none',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={drawAt}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      />

      {/* Controls */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={() => updateBrush({ mode: 'raise' })}
            style={brushState.mode === 'raise' ? { background: 'var(--accent)', color: '#FAF8F5', borderColor: 'var(--accent)' } : {}}
          >
            ↑ Raise
          </button>
          <button
            onClick={() => updateBrush({ mode: 'lower' })}
            style={brushState.mode === 'lower' ? { background: 'var(--red)', color: '#FAF8F5', borderColor: 'var(--red)' } : {}}
          >
            ↓ Lower
          </button>
          <button onClick={handleReset} style={{ marginLeft: 'auto' }}>Reset</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: 8, alignItems: 'center' }}>
          <label>Size {brushState.size}</label>
          <input type="range" min={5} max={60} value={brushState.size}
            onChange={e => updateBrush({ size: Number(e.target.value) })} />
          <label>Opacity {Math.round(brushState.opacity * 100)}%</label>
          <input type="range" min={5} max={100} value={Math.round(brushState.opacity * 100)}
            onChange={e => updateBrush({ opacity: Number(e.target.value) / 100 })} />
        </div>

        <button className="primary" onClick={handleSubmit} disabled={loading}>
          {loading ? 'Processing…' : 'Submit as Scanned Result'}
        </button>
      </div>
    </div>
  )
}
