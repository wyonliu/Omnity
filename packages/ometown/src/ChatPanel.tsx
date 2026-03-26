import { useState, useRef, useEffect } from 'react'
import type { CharacterData } from './iso'

interface Props {
  ome: CharacterData
  onClose: () => void
}

interface Message {
  role: 'user' | 'ome'
  text: string
}

/**
 * Chat Panel — slides up from bottom when clicking an Ome.
 * Connects to ome-server /chat/stream for SSE responses.
 */
export function ChatPanel({ ome, onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'ome', text: `Hi! I'm ${ome.name}. Walk closer anytime.` },
  ])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    if (!input.trim() || streaming) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: userMsg }])
    setStreaming(true)

    try {
      // SSE streaming from ome-server
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, ome_id: ome.id }),
      })

      if (!resp.ok) {
        // Fallback: non-streaming
        const data = await resp.json().catch(() => ({ reply: "I'm thinking..." }))
        setMessages(prev => [...prev, { role: 'ome', text: data.reply || '...' }])
        setStreaming(false)
        return
      }

      // Read SSE stream
      const reader = resp.body?.getReader()
      const decoder = new TextDecoder()
      let omeText = ''
      setMessages(prev => [...prev, { role: 'ome', text: '' }])

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value)
        for (const line of chunk.split('\n')) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') break
            try {
              const parsed = JSON.parse(data)
              if (parsed.token) {
                omeText += parsed.token
                setMessages(prev => {
                  const updated = [...prev]
                  updated[updated.length - 1] = { role: 'ome', text: omeText }
                  return updated
                })
              }
            } catch { /* skip malformed */ }
          }
        }
      }
    } catch {
      setMessages(prev => [...prev, {
        role: 'ome',
        text: `(${ome.name} is offline — connect ome-server to chat)`,
      }])
    }

    setStreaming(false)
  }

  return (
    <div style={{
      position: 'absolute', bottom: 0, left: 0, right: 0,
      background: 'rgba(18,19,42,0.95)', backdropFilter: 'blur(12px)',
      borderTop: '1px solid rgba(200,169,110,0.2)',
      maxHeight: '40vh', display: 'flex', flexDirection: 'column',
      fontFamily: 'system-ui',
    }}>
      {/* Header */}
      <div style={{
        padding: '10px 16px', display: 'flex', alignItems: 'center',
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}>
        <div style={{ color: '#c8a96e', fontWeight: 600, fontSize: 14 }}>{ome.name}</div>
        <div style={{ marginLeft: 8, color: '#666', fontSize: 12 }}>
          {ome.accessory ? ome.accessory.replace('_', ' ') : 'villager'}
        </div>
        <button onClick={onClose} style={{
          marginLeft: 'auto', background: 'none', border: 'none',
          color: '#666', cursor: 'pointer', fontSize: 18,
        }}>×</button>
      </div>

      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 16px' }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            padding: '6px 0',
            textAlign: m.role === 'user' ? 'right' : 'left',
          }}>
            <span style={{
              display: 'inline-block', maxWidth: '80%',
              padding: '8px 12px', borderRadius: 12,
              fontSize: 13, lineHeight: 1.5,
              background: m.role === 'user' ? 'rgba(200,169,110,0.15)' : 'rgba(255,255,255,0.05)',
              color: m.role === 'user' ? '#c8a96e' : '#ccc',
            }}>
              {m.text}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{ padding: '8px 16px', display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder={`Say something to ${ome.name}...`}
          style={{
            flex: 1, padding: '10px 14px', borderRadius: 20,
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
            color: '#e0e0e0', fontSize: 13, outline: 'none',
            fontFamily: 'system-ui',
          }}
        />
        <button onClick={send} disabled={streaming} style={{
          padding: '8px 20px', borderRadius: 20,
          background: streaming ? '#333' : '#c8a96e', border: 'none',
          color: '#0a0a16', fontWeight: 600, cursor: streaming ? 'default' : 'pointer',
          fontSize: 13,
        }}>
          {streaming ? '...' : 'Send'}
        </button>
      </div>
    </div>
  )
}
