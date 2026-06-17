import { useEffect, useRef } from 'react'

export function Surface3D({ surfaceData }) {
  const divRef = useRef(null)

  useEffect(() => {
    if (!surfaceData?.z?.length || !divRef.current) return

    import('plotly.js-dist').then(Plotly => {
      const layout = {
        margin: { l: 0, r: 0, t: 10, b: 0 },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        scene: {
          aspectratio: { x: 1, y: 1, z: 0.20 },   // 30mm depth / 150mm width = 0.2
          camera: { eye: { x: 1.4, y: -1.4, z: 0.7 } },
          xaxis: { showticklabels: false, showgrid: false, zeroline: false, title: '' },
          yaxis: { showticklabels: false, showgrid: false, zeroline: false, title: '' },
          zaxis: { showticklabels: false, showgrid: false, zeroline: false, title: '' },
          bgcolor: 'rgba(0,0,0,0)',
        },
      }

      Plotly.react(
        divRef.current,
        [{
          type: 'surface',
          z: surfaceData.z,
          colorscale: 'Greys',
          reversescale: false,
          showscale: false,
          lighting: { ambient: 0.7, diffuse: 0.9, roughness: 0.4 },
          lightposition: { x: 1000, y: 1000, z: 2000 },
        }],
        layout,
        { responsive: true, displayModeBar: false },
      )
    })
  }, [surfaceData])

  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>
        3D Surface Preview
      </div>
      <div
        ref={divRef}
        style={{
          width: '100%',
          height: 280,
          background: 'var(--surface2)',
          borderRadius: 6,
          border: '1px solid var(--border)',
          overflow: 'hidden',
        }}
      />
    </div>
  )
}
