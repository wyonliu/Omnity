import { useState, useEffect, useCallback } from 'react'
import { TownCanvas } from './TownCanvas'
import { ChatPanel } from './ChatPanel'
import { DailyReport } from './DailyReport'
import type { CharacterData } from './iso'

/**
 * OmeTown — Main App Shell
 *
 * Layout:
 *   ┌────────────────────────────────┐
 *   │         Town Canvas            │
 *   │   (isometric PixiJS view)      │
 *   │                                │
 *   ├──────────────┬─────────────────┤
 *   │  Chat Panel  │  Daily Report   │
 *   └──────────────┴─────────────────┘
 */
export function App() {
  const [selectedOme, setSelectedOme] = useState<CharacterData | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [reportOpen, setReportOpen] = useState(false)

  // Open chat when clicking on an Ome character
  const handleOmeClick = useCallback((ome: CharacterData) => {
    setSelectedOme(ome)
    setChatOpen(true)
  }, [])

  // Check for daily report on mount
  useEffect(() => {
    // TODO: Fetch from ome-server /api/daily-report
    // If there's a new report since last visit, show it
  }, [])

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      overflow: 'hidden',
      background: '#0a0a16',
      display: 'flex',
      flexDirection: 'column',
    }}>
      {/* Main isometric view */}
      <div style={{ flex: 1, position: 'relative' }}>
        <TownCanvas onOmeClick={handleOmeClick} />

        {/* Overlay: Town name + time */}
        <div style={{
          position: 'absolute', top: 16, left: 16,
          color: '#c8a96e', fontSize: 14, fontFamily: 'system-ui',
          textShadow: '0 1px 4px rgba(0,0,0,0.8)',
        }}>
          <div style={{ fontSize: 20, fontWeight: 600 }}>OmeTown</div>
          <div style={{ opacity: 0.6, fontSize: 12, marginTop: 2 }}>
            {new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })}
          </div>
        </div>

        {/* Daily report button */}
        <button
          onClick={() => setReportOpen(true)}
          style={{
            position: 'absolute', top: 16, right: 16,
            background: 'rgba(200,169,110,0.15)', border: '1px solid rgba(200,169,110,0.3)',
            color: '#c8a96e', padding: '8px 16px', borderRadius: 20,
            cursor: 'pointer', fontSize: 13, fontFamily: 'system-ui',
          }}
        >
          Today's Report
        </button>
      </div>

      {/* Chat panel (slide up from bottom) */}
      {chatOpen && selectedOme && (
        <ChatPanel
          ome={selectedOme}
          onClose={() => setChatOpen(false)}
        />
      )}

      {/* Daily report overlay */}
      {reportOpen && (
        <DailyReport onClose={() => setReportOpen(false)} />
      )}
    </div>
  )
}
