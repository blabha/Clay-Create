import { useEffect, useRef, useState } from 'react'

export function CarverModal({ tileIdx, onConfirm, onCancel }) {
  const [name, setName] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  function handleKeyDown(e) {
    if (e.key === 'Enter' && name.trim()) onConfirm(name.trim())
    if (e.key === 'Escape') onCancel()
  }

  return (
    <div
      style={{
        position: 'fixed', inset: 0,
        background: 'rgba(42,24,16,0.32)',
        backdropFilter: 'blur(3px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onCancel() }}
    >
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 16,
        padding: '32px 36px',
        width: 380,
        boxShadow: '0 24px 64px rgba(42,24,16,0.20)',
        display: 'flex', flexDirection: 'column', gap: 20,
      }}>
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 2, marginBottom: 8 }}>
            Tile {tileIdx + 1}
          </div>
          <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--text)', lineHeight: 1.3 }}>
            Who is carving this tile?
          </h2>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <label htmlFor="carver-name">Carver name</label>
          <input
            ref={inputRef}
            id="carver-name"
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter name…"
            maxLength={32}
          />
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={{ padding: '8px 18px' }}>
            Cancel
          </button>
          <button
            className="primary"
            onClick={() => onConfirm(name.trim() || 'Anonymous')}
            style={{ padding: '8px 22px' }}
          >
            Start Carving
          </button>
        </div>
      </div>
    </div>
  )
}