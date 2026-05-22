import { useCallback, useRef, useState } from 'react'

export function ImageUpload({ onGenerate, loading }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef(null)

  const handleFile = useCallback((f) => {
    if (!f || !f.type.startsWith('image/')) return
    if (preview) URL.revokeObjectURL(preview)
    setFile(f)
    setPreview(URL.createObjectURL(f))
  }, [preview])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }, [handleFile])

  function handleClear() {
    if (preview) URL.revokeObjectURL(preview)
    setFile(null)
    setPreview(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (file) onGenerate(file)
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', gap: 16, alignItems: 'stretch' }}>

        {/* Drop zone */}
        <div
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onClick={() => !loading && inputRef.current?.click()}
          style={{
            flex: 1,
            minHeight: 120,
            border: `2px dashed ${dragging ? 'var(--accent)' : file ? 'var(--green)' : 'var(--border)'}`,
            borderRadius: 10,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            cursor: loading ? 'not-allowed' : 'pointer',
            background: dragging ? 'rgba(240,192,64,0.06)' : 'var(--surface2)',
            transition: 'border-color 0.15s, background 0.15s',
            padding: '12px 16px',
          }}
        >
          {file ? (
            <>
              <span style={{ fontSize: 20, opacity: 0.6 }}>✓</span>
              <span style={{ fontSize: 13, color: 'var(--green)', fontWeight: 600, textAlign: 'center', wordBreak: 'break-all' }}>
                {file.name}
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Click to replace
              </span>
            </>
          ) : (
            <>
              <span style={{ fontSize: 28, opacity: 0.35, lineHeight: 1 }}>↑</span>
              <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                Drop image here or click to browse
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', opacity: 0.6 }}>
                JPG, PNG, WEBP — any image format
              </span>
            </>
          )}
        </div>

        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          style={{ display: 'none' }}
          onChange={(e) => handleFile(e.target.files[0])}
        />

        {/* Preview */}
        {preview && (
          <img
            src={preview}
            alt="preview"
            style={{
              width: 120,
              height: 120,
              objectFit: 'cover',
              borderRadius: 8,
              border: '1px solid var(--border)',
              flexShrink: 0,
              alignSelf: 'center',
            }}
          />
        )}
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <button
          type="submit"
          className="primary"
          disabled={loading || !file}
          style={{ flex: 1 }}
        >
          {loading ? 'Processing…' : 'Generate Heightmap'}
        </button>
        {file && !loading && (
          <button type="button" onClick={handleClear}>
            Clear
          </button>
        )}
      </div>

      {loading && (
        <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', margin: 0 }}>
          MiDaS depth estimation → CLAHE enhance → tiling…
        </p>
      )}
    </form>
  )
}
