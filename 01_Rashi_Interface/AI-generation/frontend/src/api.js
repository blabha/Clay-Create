async function req(path, options = {}) {
  const res = await fetch(path, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  getState: () => req('/api/state'),

  generate: (imageFile, cols, rows) => {
    const form = new FormData()
    form.append('file', imageFile)
    form.append('cols', cols)
    form.append('rows', rows)
    return req('/api/generate', { method: 'POST', body: form })
  },

  uploadScan: (idx, file) => {
    const form = new FormData()
    form.append('file', file)
    return req(`/api/tile/${idx}/upload-scan`, { method: 'POST', body: form })
  },

  drawScan: (idx, imageData) =>
    req(`/api/tile/${idx}/draw`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_data: imageData }),
    }),

  getSurface3d: (idx, res = 64) =>
    req(`/api/tile/${idx}/surface3d?res=${res}`),

  regenerateTile: (idx) => req(`/api/tile/${idx}/regenerate`, { method: 'POST' }),
  regenerateAll: () => req('/api/regenerate-all', { method: 'POST' }),

  saveTarget: (idx) => req(`/api/tile/${idx}/save-target`, { method: 'POST' }),

  reset: () => req('/api/reset', { method: 'POST' }),

  exportPngUrl: (idx) => `/api/export/png/${idx}`,
  exportObjUrl: (idx) => `/api/export/obj/${idx}`,
}
