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

// Character personalities — used as fallback when ome-server is unreachable
const PERSONALITIES: Record<string, {
  greeting: string
  traits: string
  responses: string[]
}> = {
  mayor_chen: {
    greeting: "Ah, welcome! Terrible business about the Star... I'm sure we'll get to the bottom of it.",
    traits: 'authoritative, nervous, well-spoken',
    responses: [
      "I was asleep by 10 PM, of course. I'm the Mayor — I keep a strict schedule.",
      "Have you spoken to the night guard? He was supposed to be watching the museum...",
      "I suggest you look into outsiders. OmeTown is a safe place — our people wouldn't do this.",
      "The museum's security really should have been better. I'll see to it personally.",
      "Let's not jump to conclusions. We need to investigate this calmly and methodically.",
    ],
  },
  baker_li: {
    greeting: "Good morning! Come in, the bread is fresh! Oh, you're here about the theft? 🍞",
    traits: 'warm, observant, gossipy',
    responses: [
      "I was up at 2:30 AM making dough when I saw someone pass by — tall figure in a dark coat, heading south.",
      "They were carrying something wrapped in cloth, walking fast. Not the usual nighttime crowd.",
      "The figure walked with... authority? Not like a thief sneaking around. More like someone who owned the place.",
      "I couldn't see the face, but they were tall. About the Mayor's height, actually...",
      "I bake every night — I know who walks around at that hour. This person was unusual.",
    ],
  },
  gardener_wang: {
    greeting: "...morning. Found something in the mud today.",
    traits: 'quiet, observant, precise',
    responses: [
      "Boot prints. Size 11. Diamond tread pattern. Fresh — from last night.",
      "They lead from the museum area, through the park, toward the south dock.",
      "Expensive boots. Not work boots. The kind a government official might wear.",
      "The Mayor wears similar boots. I've noticed them when he walks through the garden.",
      "The prints were deep. Whoever made them was carrying something heavy.",
    ],
  },
  merchant_zhao: {
    greeting: "Looking for information? Everything has a price, friend. 💰",
    traits: 'shrewd, cautious, connected',
    responses: [
      "I might know something... but what's in it for me? Information is currency.",
      "Alright, since you asked nicely — someone approached me last week about selling a 'rare antiquity.'",
      "The inquiry came through a prepaid phone. Untraceable. But my contacts say the person had inside knowledge.",
      "Whoever it was knew the exact value of the Star. That narrows it down to very few people.",
      "Government connections. That's all I'll say. Draw your own conclusions.",
    ],
  },
  fisher_zhang: {
    greeting: "Shh... sit down. The fish are biting, and I have a story for you. 🐟",
    traits: 'philosophical, patient, observant',
    responses: [
      "The river sees everything, friend. Just like the fisherman who sits beside it.",
      "At dawn... an unmarked boat appeared at the south dock. Wasn't there the night before.",
      "There was a locked metal box on it. Small but heavy. The boat was gone by 7 AM.",
      "The dock master's log was tampered with. Someone didn't want that boat recorded.",
      "The water carries away many secrets... but some float back to the surface.",
    ],
  },
  artist_liu: {
    greeting: "Oh! You startled me. I was just sketching the scene from last night... 🎨",
    traits: 'perceptive, emotional, dramatic',
    responses: [
      "I was in the town square yesterday evening, sketching. The light was perfect...",
      "That's when I saw Mayor Chen. Pacing near the museum. Checking his phone. Again and again.",
      "His hands were trembling — I could see it even from across the square. The lamplight caught his expression.",
      "It was around 10 PM. He looked... agitated. Desperate, even. Not his usual composed self.",
      "He claims he went to bed early. But I saw him with my own eyes. Artists don't miss these things.",
    ],
  },
  scholar_wu: {
    greeting: "Welcome. I've been researching the Star's history. The facts are... illuminating. 📚",
    traits: 'analytical, thorough, slightly pompous',
    responses: [
      "The Star of OmeTown is worth at least 2 million on the black market. A powerful motive.",
      "Only three people have the museum master key: the curator, the night guard, and Mayor Chen.",
      "The curator is on vacation abroad. The guard was drugged — found unconscious at his post.",
      "That leaves one person with a key. I'll let you do the mathematics.",
      "I've also heard rumors — unconfirmed — that the Mayor has significant gambling debts.",
    ],
  },
  runner_qian: {
    greeting: "Hey! *catches breath* — oh, you want to talk about last night? I saw something. 🏃",
    traits: 'energetic, direct, no-nonsense',
    responses: [
      "I run at 2 AM — night training. I know who's usually out at that hour. This person wasn't a regular.",
      "Tall man, dark coat, cutting through the park heading south. Moving fast.",
      "He was actively avoiding streetlights. Ducking into shadows. That's not normal walking behavior.",
      "I'm a fitness coach — I read body language. This person was carrying something under the coat.",
      "Definitely heading toward the south dock. I would have followed but I had intervals to finish.",
    ],
  },
  musician_sun: {
    greeting: "🎵 Listen... I was playing on my balcony last night when I heard something unusual.",
    traits: 'sharp-eared, dreamy, precise',
    responses: [
      "At 1:45 AM. The museum direction. A sound like glass breaking — but not a crash.",
      "It was controlled. Careful. Like someone who knew exactly which piece to remove.",
      "Then silence. Complete silence for about five minutes. Whoever it was, they were methodical.",
      "Then footsteps. Faint but steady, heading south. The rhythm was unhurried — confident.",
      "I can tell you this: it wasn't a smash-and-grab. This was planned by someone who knew what they were doing.",
    ],
  },
  chef_zhou: {
    greeting: "Welcome to my kitchen! Oh — about the theft? I have something important. 🍳",
    traits: 'detail-oriented, honest, passionate',
    responses: [
      "Mayor Chen was here last night. In my restaurant. Until 1:15 AM. I have the receipt.",
      "He was extremely nervous. Barely touched his food. Kept checking his phone under the table.",
      "He paid cash. That's unusual — he always uses his card. Like he didn't want a record.",
      "He told everyone he was asleep by 10 PM. That's a lie. I served him wine at midnight.",
      "I keep every receipt. Timestamp, table number, everything. 1:15 AM, Table 3, Mayor Chen.",
    ],
  },
}

export function ChatPanel({ ome, onClose }: Props) {
  const personality = PERSONALITIES[ome.id] || PERSONALITIES['my_ome']
  const [messages, setMessages] = useState<Message[]>([
    { role: 'ome', text: personality.greeting },
  ])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const responseIdx = useRef(0)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    if (!input.trim() || typing) return
    const userMsg = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: userMsg }])
    setTyping(true)

    // Strategy: try SSE stream → non-stream API → local fallback
    let replied = false

    // 1) Try SSE streaming
    try {
      const resp = await fetch('/api/town/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ npc_id: ome.id, message: userMsg }),
        signal: AbortSignal.timeout(10000),
      })
      if (resp.ok && resp.body) {
        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let omeText = ''
        setMessages(prev => [...prev, { role: 'ome', text: '' }])
        while (true) {
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
              } catch { /* skip malformed SSE line */ }
            }
          }
        }
        if (omeText.length > 0) replied = true
      }
    } catch { /* SSE failed, try non-stream */ }

    // 2) Try non-streaming API (real Ome brain, just no streaming)
    if (!replied) {
      try {
        const resp = await fetch('/api/town/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ npc_id: ome.id, message: userMsg }),
          signal: AbortSignal.timeout(15000),
        })
        if (resp.ok) {
          const data = await resp.json()
          const reply = data.reply || data.response || ''
          if (reply) {
            // Typing animation for non-stream response
            setMessages(prev => [...prev, { role: 'ome', text: '' }])
            let displayed = ''
            for (let i = 0; i < reply.length; i++) {
              await new Promise(r => setTimeout(r, 15 + Math.random() * 20))
              displayed += reply[i]
              const text = displayed
              setMessages(prev => {
                const updated = [...prev]
                updated[updated.length - 1] = { role: 'ome', text }
                return updated
              })
            }
            replied = true
          }
        }
      } catch { /* server down, use fallback */ }
    }

    // 3) Last resort: local personality response
    if (!replied) {
      const idx = responseIdx.current % personality.responses.length
      responseIdx.current++
      const response = personality.responses[idx]
      setMessages(prev => [...prev, { role: 'ome', text: '' }])
      let displayed = ''
      for (let i = 0; i < response.length; i++) {
        await new Promise(r => setTimeout(r, 20 + Math.random() * 30))
        displayed += response[i]
        const text = displayed
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'ome', text }
          return updated
        })
      }
    }
    setTyping(false)
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
        <div style={{
          width: 8, height: 8, borderRadius: '50%', marginRight: 8,
          background: '#55CC77', boxShadow: '0 0 6px #55CC77',
        }} />
        <div style={{ color: '#c8a96e', fontWeight: 600, fontSize: 14 }}>{ome.name}</div>
        <div style={{ marginLeft: 8, color: '#666', fontSize: 12 }}>
          {personality.traits}
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
              {m.role === 'ome' && typing && i === messages.length - 1 && (
                <span style={{ opacity: 0.5 }}>▊</span>
              )}
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
          disabled={typing}
          style={{
            flex: 1, padding: '10px 14px', borderRadius: 20,
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
            color: '#e0e0e0', fontSize: 13, outline: 'none',
            fontFamily: 'system-ui',
            opacity: typing ? 0.6 : 1,
          }}
        />
        <button onClick={send} disabled={typing} style={{
          padding: '8px 20px', borderRadius: 20,
          background: typing ? '#333' : '#c8a96e', border: 'none',
          color: '#0a0a16', fontWeight: 600, cursor: typing ? 'default' : 'pointer',
          fontSize: 13,
        }}>
          {typing ? '...' : 'Send'}
        </button>
      </div>
    </div>
  )
}
