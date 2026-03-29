import { useState, useEffect, useCallback } from 'react'
import { TownCanvas } from './TownCanvas'
import { ChatPanel } from './ChatPanel'
import { ClueNotebook } from './ClueNotebook'
import { AccusePanel } from './AccusePanel'
import type { CharacterData } from './iso'

/**
 * OmeTown — 影子之谜 · Mystery of the Shadows
 *
 * A Westworld-style mystery investigation: talk to NPCs, gather clues,
 * find the thief who stole the Star of OmeTown.
 */
export function App() {
  const [selectedOme, setSelectedOme] = useState<CharacterData | null>(null)
  const [chatOpen, setChatOpen] = useState(false)
  const [cluesOpen, setCluesOpen] = useState(false)
  const [accuseOpen, setAccuseOpen] = useState(false)
  const [scenario, setScenario] = useState<{ name: string; brief: string } | null>(null)

  const handleOmeClick = useCallback((ome: CharacterData) => {
    setSelectedOme(ome)
    setChatOpen(true)
  }, [])

  // Fetch scenario info on mount
  useEffect(() => {
    fetch('/api/town/scenario', { signal: AbortSignal.timeout(3000) })
      .then(r => r.json())
      .then(d => setScenario(d))
      .catch(() => {
        setScenario({ name: '影子之谜 · Mystery of the Shadows', brief: 'The Star of OmeTown was stolen. Talk to the townspeople to find the thief.' })
      })
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

        {/* Overlay: Town name + scenario */}
        <div style={{
          position: 'absolute', top: 16, left: 16,
          color: '#c8a96e', fontSize: 14, fontFamily: 'system-ui',
          textShadow: '0 1px 4px rgba(0,0,0,0.8)',
          maxWidth: 280,
        }}>
          <div style={{ fontSize: 20, fontWeight: 600 }}>OmeTown</div>
          {scenario && (
            <div style={{ opacity: 0.8, fontSize: 12, marginTop: 4, lineHeight: 1.4 }}>
              {scenario.name}
            </div>
          )}
          <div style={{ opacity: 0.5, fontSize: 11, marginTop: 2 }}>
            Click on characters to investigate
          </div>
        </div>

        {/* Clue notebook button */}
        <button
          onClick={() => setCluesOpen(true)}
          style={{
            position: 'absolute', top: 16, right: 16,
            background: 'rgba(200,169,110,0.15)', border: '1px solid rgba(200,169,110,0.3)',
            color: '#c8a96e', padding: '8px 16px', borderRadius: 20,
            cursor: 'pointer', fontSize: 13, fontFamily: 'system-ui',
            display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          <span>📓</span> Clues
        </button>
      </div>

      {/* Chat panel (slide up from bottom) */}
      {chatOpen && selectedOme && (
        <ChatPanel
          ome={selectedOme}
          onClose={() => setChatOpen(false)}
        />
      )}

      {/* Clue notebook overlay */}
      {cluesOpen && (
        <ClueNotebook
          onClose={() => setCluesOpen(false)}
          onAccuse={() => { setCluesOpen(false); setAccuseOpen(true) }}
        />
      )}

      {/* Accusation overlay */}
      {accuseOpen && (
        <AccusePanel onClose={() => setAccuseOpen(false)} />
      )}
    </div>
  )
}
