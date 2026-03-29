import { useState, useEffect } from 'react'

interface Clue {
  clue: string
  source: string
  description: string
}

interface ClueData {
  discovered: Clue[]
  total: number
  complete: boolean
}

interface Props {
  onClose: () => void
  onAccuse: () => void
}

export function ClueNotebook({ onClose, onAccuse }: Props) {
  const [data, setData] = useState<ClueData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/town/clues', { signal: AbortSignal.timeout(3000) })
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: 'rgba(10,10,22,0.92)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'system-ui', zIndex: 100,
    }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        background: '#12132a', border: '1px solid rgba(200,169,110,0.2)',
        borderRadius: 16, padding: 24, maxWidth: 440, width: '90%',
        maxHeight: '80vh', overflowY: 'auto',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ color: '#c8a96e', fontSize: 18, fontWeight: 600, margin: 0 }}>
            Clue Notebook
          </h2>
          <span style={{ marginLeft: 8, color: '#666', fontSize: 12 }}>
            {data ? `${data.discovered.length}/${data.total}` : '...'}
          </span>
          <button onClick={onClose} style={{
            marginLeft: 'auto', background: 'none', border: 'none',
            color: '#666', cursor: 'pointer', fontSize: 18,
          }}>×</button>
        </div>

        <div style={{ color: '#999', fontSize: 13, marginBottom: 16 }}>
          Talk to the townspeople to uncover clues about the theft of the Star of OmeTown.
        </div>

        {loading ? (
          <div style={{ color: '#666', textAlign: 'center', padding: 20 }}>Loading clues...</div>
        ) : data && data.discovered.length > 0 ? (
          data.discovered.map((clue, i) => (
            <div key={i} style={{
              padding: '10px 12px', marginBottom: 8,
              background: 'rgba(200,169,110,0.06)', borderRadius: 8,
              borderLeft: '3px solid #c8a96e',
            }}>
              <div style={{ color: '#c8a96e', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                From: {clue.source.replace(/_/g, ' ')}
              </div>
              <div style={{ color: '#ccc', fontSize: 13 }}>{clue.description}</div>
            </div>
          ))
        ) : (
          <div style={{ color: '#555', textAlign: 'center', padding: 20 }}>
            No clues discovered yet. Talk to the NPCs to investigate!
          </div>
        )}

        {/* Progress bar */}
        {data && (
          <div style={{ marginTop: 16 }}>
            <div style={{
              height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.06)',
              overflow: 'hidden',
            }}>
              <div style={{
                height: '100%', borderRadius: 2,
                background: 'linear-gradient(90deg, #c8a96e, #FFD700)',
                width: `${(data.discovered.length / data.total) * 100}%`,
                transition: 'width 0.3s ease',
              }} />
            </div>
            <div style={{ color: '#666', fontSize: 11, marginTop: 4, textAlign: 'center' }}>
              {data.discovered.length}/{data.total} clues discovered
            </div>
          </div>
        )}

        {/* Accuse button */}
        <button onClick={onAccuse} style={{
          marginTop: 16, width: '100%', padding: '12px 0',
          background: data && data.discovered.length >= 5
            ? 'linear-gradient(135deg, #c8a96e, #e6c670)' : 'rgba(255,255,255,0.05)',
          border: 'none', borderRadius: 10, cursor: 'pointer',
          color: data && data.discovered.length >= 5 ? '#0a0a16' : '#555',
          fontWeight: 600, fontSize: 14, fontFamily: 'system-ui',
        }}>
          {data && data.discovered.length >= 5 ? 'Accuse a Suspect' : 'Gather more clues to accuse...'}
        </button>
      </div>
    </div>
  )
}
