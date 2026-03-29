import { useState } from 'react'

const SUSPECTS = [
  { id: 'mayor_chen', name: 'Mayor Chen', cn: '陈镇长' },
  { id: 'baker_li', name: 'Baker Li', cn: '面包师小李' },
  { id: 'gardener_wang', name: 'Old Wang', cn: '园丁老王' },
  { id: 'merchant_zhao', name: 'Merchant Zhao', cn: '商人老赵' },
  { id: 'fisher_zhang', name: 'Fisher Zhang', cn: '钓鱼老张' },
  { id: 'artist_liu', name: 'Artist Liu', cn: '画家小刘' },
  { id: 'scholar_wu', name: 'Scholar Wu', cn: '学者老吴' },
  { id: 'runner_qian', name: 'Runner Qian', cn: '跑步小钱' },
  { id: 'musician_sun', name: 'Musician Sun', cn: '乐师小孙' },
  { id: 'chef_zhou', name: 'Chef Zhou', cn: '厨师老周' },
]

interface Props {
  onClose: () => void
}

export function AccusePanel({ onClose }: Props) {
  const [selected, setSelected] = useState<string | null>(null)
  const [result, setResult] = useState<{ correct: boolean; message: string } | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleAccuse = async () => {
    if (!selected || submitting) return
    setSubmitting(true)
    try {
      const resp = await fetch('/api/town/accuse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ suspect_id: selected }),
      })
      if (resp.ok) {
        setResult(await resp.json())
      } else {
        setResult({ correct: false, message: 'Server error. Try again.' })
      }
    } catch {
      setResult({ correct: false, message: 'Could not reach server.' })
    }
    setSubmitting(false)
  }

  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: 'rgba(10,10,22,0.95)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'system-ui', zIndex: 110,
    }} onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        background: '#12132a', border: '1px solid rgba(200,169,110,0.3)',
        borderRadius: 16, padding: 24, maxWidth: 400, width: '90%',
      }}>
        {result ? (
          <div style={{ textAlign: 'center' }}>
            <div style={{
              fontSize: 48, marginBottom: 16,
            }}>
              {result.correct ? '🎉' : '❌'}
            </div>
            <h2 style={{
              color: result.correct ? '#55CC77' : '#FF6655',
              fontSize: 20, fontWeight: 600, margin: '0 0 12px',
            }}>
              {result.correct ? 'Case Solved!' : 'Wrong Suspect'}
            </h2>
            <p style={{ color: '#ccc', fontSize: 14, lineHeight: 1.6 }}>
              {result.message}
            </p>
            <button onClick={onClose} style={{
              marginTop: 16, padding: '10px 32px', borderRadius: 10,
              background: '#c8a96e', border: 'none', cursor: 'pointer',
              color: '#0a0a16', fontWeight: 600, fontSize: 14,
            }}>
              {result.correct ? 'Celebrate!' : 'Keep Investigating'}
            </button>
          </div>
        ) : (
          <>
            <h2 style={{ color: '#FF6655', fontSize: 18, fontWeight: 600, margin: '0 0 8px' }}>
              Accuse a Suspect
            </h2>
            <p style={{ color: '#999', fontSize: 13, margin: '0 0 16px' }}>
              Who stole the Star of OmeTown? Choose carefully — this is your accusation.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {SUSPECTS.map(s => (
                <button key={s.id} onClick={() => setSelected(s.id)} style={{
                  padding: '10px 14px', borderRadius: 8,
                  background: selected === s.id ? 'rgba(200,169,110,0.15)' : 'rgba(255,255,255,0.03)',
                  border: selected === s.id ? '1px solid #c8a96e' : '1px solid rgba(255,255,255,0.06)',
                  cursor: 'pointer', textAlign: 'left',
                  display: 'flex', alignItems: 'center', gap: 10,
                }}>
                  <span style={{ color: '#ccc', fontSize: 14 }}>{s.name}</span>
                  <span style={{ color: '#666', fontSize: 12 }}>{s.cn}</span>
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button onClick={onClose} style={{
                flex: 1, padding: '10px 0', borderRadius: 10,
                background: 'rgba(255,255,255,0.05)', border: 'none',
                color: '#888', cursor: 'pointer', fontSize: 14,
              }}>
                Cancel
              </button>
              <button onClick={handleAccuse} disabled={!selected || submitting} style={{
                flex: 1, padding: '10px 0', borderRadius: 10,
                background: selected ? '#FF6655' : 'rgba(255,255,255,0.05)',
                border: 'none', cursor: selected ? 'pointer' : 'default',
                color: selected ? '#fff' : '#555', fontWeight: 600, fontSize: 14,
              }}>
                {submitting ? 'Accusing...' : 'Accuse!'}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
