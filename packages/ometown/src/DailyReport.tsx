interface Props {
  onClose: () => void
}

/**
 * Daily Report — "What your Ome did while you were away"
 * The core "async surprise" feature (旅行青蛙 model).
 *
 * TODO: Fetch from ome-server /api/daily-report
 */
export function DailyReport({ onClose }: Props) {
  // Placeholder content
  const events = [
    { time: '08:30', text: 'Woke up and watered the garden' },
    { time: '10:15', text: 'Had coffee with Baker at the café' },
    { time: '12:00', text: 'Helped Merchant organize the shop' },
    { time: '14:30', text: 'Learned a new recipe from Baker' },
    { time: '16:00', text: 'Sat by the fountain and wrote in journal' },
    { time: '19:00', text: 'Had dinner with Gardener, talked about flowers' },
  ]

  return (
    <div style={{
      position: 'absolute', inset: 0,
      background: 'rgba(10,10,22,0.9)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'system-ui', zIndex: 100,
    }}
    onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: '#12132a', border: '1px solid rgba(200,169,110,0.2)',
          borderRadius: 16, padding: 24, maxWidth: 400, width: '90%',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ color: '#c8a96e', fontSize: 18, fontWeight: 600, margin: 0 }}>
            Today's Report
          </h2>
          <span style={{ marginLeft: 8, color: '#666', fontSize: 12 }}>
            {new Date().toLocaleDateString('zh-CN')}
          </span>
          <button onClick={onClose} style={{
            marginLeft: 'auto', background: 'none', border: 'none',
            color: '#666', cursor: 'pointer', fontSize: 18,
          }}>×</button>
        </div>

        <div style={{ color: '#888', fontSize: 13, marginBottom: 16 }}>
          While you were away, your Ome had a busy day:
        </div>

        {events.map((e, i) => (
          <div key={i} style={{
            padding: '8px 0',
            borderBottom: i < events.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
            display: 'flex', gap: 12,
          }}>
            <span style={{
              color: '#c8a96e', fontSize: 12, fontVariantNumeric: 'tabular-nums',
              minWidth: 40,
            }}>{e.time}</span>
            <span style={{ color: '#ccc', fontSize: 13 }}>{e.text}</span>
          </div>
        ))}

        <div style={{
          marginTop: 16, padding: '10px 14px',
          background: 'rgba(200,169,110,0.08)', borderRadius: 8,
          color: '#c8a96e', fontSize: 12,
        }}>
          Your Ome made 2 new friends today and learned 1 new skill!
        </div>
      </div>
    </div>
  )
}
