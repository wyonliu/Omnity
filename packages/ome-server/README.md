# ome-server

**Ome App Backend — FastAPI server powering the Ome AI twin mobile app.**

Full-stack backend with JWT auth, anonymous onboarding, voice interaction, memory library, contacts, checklists, OmeTown simulation, and optional PostgreSQL multi-tenant support.

## Install

```bash
pip install -e ".[pg]"    # with PostgreSQL support
pip install -e .           # SQLite only (default)
```

## Quick Start

```bash
# 1. Set an LLM API key
export DEEPSEEK_API_KEY="sk-..."

# 2. Start the server
ome-server
# → http://localhost:8000

# 3. Register + chat
curl -X POST localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice", "password": "secret", "name": "Alice"}'

curl -X POST localhost:8000/api/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, who are you?"}'
```

## API Overview

### Core

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register user + create Ome |
| POST | `/api/auth/login` | Login, get JWT |
| POST | `/api/anon/session` | Zero-registration anonymous chat |
| POST | `/api/chat` | Chat with your Ome |
| POST | `/api/chat/stream` | SSE streaming chat |
| POST | `/api/mirror` | Mirror chat (talk to yourself) |
| GET | `/api/dashboard` | Life dashboard (bond, emotion, achievements) |
| GET | `/api/status` | Current state |
| GET | `/api/identity` | Identity card |

### Memory (F3 Memory Library)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/remember` | Teach your Ome something |
| POST | `/api/recall` | Search memories (supports `type_filter`) |
| POST | `/api/forget` | GDPR hard delete |
| POST | `/api/memories/browse` | Filtered browsing (type/source/query + pagination) |
| GET | `/api/memories/stats` | Health dashboard (total, decay, by_type) |
| GET | `/api/memories/types` | Distinct types with counts |
| POST | `/api/memories/export` | Full JSON export (backup) |
| POST | `/api/memories/import` | Bulk import |
| POST | `/api/memories/delete-batch` | Bulk delete by ID list |

### Smart Input (D2)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/smart-input` | Extract contacts/tasks/notes from natural text |

### Contacts (E1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/contacts` | List all contacts |
| POST | `/api/contacts` | Create contact |
| GET | `/api/contacts/search?q=` | Search by name/phone/email |
| GET | `/api/contacts/{id}` | Get contact |
| PUT | `/api/contacts/{id}` | Update contact |
| DELETE | `/api/contacts/{id}` | Delete contact |

### Voice (D1)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/voice/transcribe` | Audio → text (STT) |
| POST | `/api/voice/chat` | Audio → Ome reply (STT + chat) |
| POST | `/api/voice/synthesize` | Text → audio (TTS) |
| GET | `/api/voice/providers` | Check available STT/TTS providers |

STT backends: OpenAI Whisper, DeepSeek, whisper.cpp (local).
TTS backends: MiniMax Speech-01-HD, OpenAI TTS, edge-tts (free).

### Map & Checklist (C7)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/map` | Full map state (18×18 grid, NPCs, landmarks) |
| GET | `/api/map/npcs` | NPC positions and activities |
| POST | `/api/map/path` | A* pathfinding between grid points |
| GET | `/api/checklists` | List all checklists |
| POST | `/api/checklists` | Create checklist |
| GET | `/api/checklists/{id}` | Get checklist |
| DELETE | `/api/checklists/{id}` | Delete checklist |
| POST | `/api/checklists/{id}/tasks` | Add task |
| PUT | `/api/checklists/{id}/tasks/{tid}` | Update task |
| DELETE | `/api/checklists/{id}/tasks/{tid}` | Delete task |

### OmeTown Simulation

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/town/state` | Full town state |
| POST | `/api/town/chat` | Chat with NPC |
| POST | `/api/town/chat/stream` | SSE streaming NPC chat |
| POST | `/api/town/accuse` | Accuse a suspect |
| GET | `/api/town/scenario` | Scenario progress |
| GET | `/api/town/clues` | Discovered clues |

### Skills & Agents

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/skills` | List available skills |
| POST | `/api/skills/{name}` | Use a skill |
| GET | `/api/agents/directory` | List all public Omes |
| POST | `/api/agents/{id}/message` | Message another Ome |

## Database Backends

### SQLite (default)

Zero config. Each user gets a directory under `~/.ome-server/data/`. Set `OME_DATA_ROOT` to customize.

### PostgreSQL + RLS (enterprise)

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/ome"
ome-server
```

Features:
- **Row-Level Security** — zero-trust tenant isolation
- **pgvector HNSW** — production-scale vector search
- **tsvector + pg_trgm** — full-text + trigram search
- **Zero-copy migration** — anonymous → registered user is a metadata update

```bash
# Dev database with pgvector
docker compose -f docker-compose.pg.yml up -d
```

## Testing

```bash
pip install pytest httpx
python -m pytest tests/ -q
# 121 passed, 16 skipped (PG tests skip without DATABASE_URL)
```

## Part of Omnity

```
SOAP            spatial protocol for 3D environments
  Mindos        persistent multi-layer brain
    Ome           individual AI twin
      ome-server  <-- you are here
        Maxim       multi-agent society
          OmeTown     the integrated world
```

## License

[Apache-2.0](../../LICENSE)
