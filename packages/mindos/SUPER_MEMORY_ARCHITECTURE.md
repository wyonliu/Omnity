# Mindos Super Memory Architecture
# Infinite Memory + Multimodal + Sub-100ms Response
# 2026-03-29

---

## Executive Summary

Transform Mindos from a single-SQLite text-only memory system into a tiered, multimodal, sub-100ms super memory engine. Three capabilities:

1. **Infinite memory** -- no cap, efficient at millions of entries via tiered hot/warm/cold storage
2. **Multimodal** -- text, image, audio, video, spatial data in a unified embedding space
3. **Sub-100ms recall** -- HNSW ANN index + ONNX embeddings + parallel search + tiered caching

---

## Part I: Current Architecture -- 9 Bottlenecks

### Codebase (14 modules, ~2800 LOC)

| File | LOC | Responsibility |
|------|-----|---------------|
| `store.py` | 782 | SQLite storage, FTS5, vector search, sync journal, compression |
| `core.py` | 393 | Facade: hydrate/commit/recall/forget/reflect/export_ome |
| `config.py` | 312 | YAML config, ModelRouter (LLM dispatch) |
| `server.py` | 455 | HTTP API + dashboard + lockfile |
| `mcp_server.py` | 372 | MCP JSON-RPC stdio server |
| `sync.py` | 372 | Cross-device sync hub + client |
| `layers/l0_memory.py` | 76 | Hippocampus: recall + relevance scoring |
| `layers/l1_instinct.py` | 235 | Brainstem: hydrate assembly, emotion, routing |
| `layers/l2_cognition.py` | 165 | Cortex: LLM fact extraction + rule fallback |
| `layers/l3_decision.py` | 94 | Prefrontal: deep reasoning via LLM |
| `layers/l4_self.py` | 216 | Self: reflection, drift detection, personality writeback |
| `event_bus.py` | 99 | Pub-sub event dispatch |
| `scheduler.py` | 192 | Passive periodic maintenance tasks |
| `insight.py` | 273 | Pattern discovery, contradiction detection, digests |

### Bottleneck #1: In-Memory Vector Search O(n) Brute Force

```python
# store.py:327-343 -- current implementation
def search_vector(self, query_vec, top_k=10):
    ids = list(self._embeddings_cache.keys())
    mat = np.stack([self._embeddings_cache[i] for i in ids])
    scores = mat @ qn  # O(n * d) full matrix multiply
```

- 1M memories x 384-dim = 384M FLOPs per query
- At 10M vectors: 50-150ms, blows the 100ms budget
- `_load_embeddings()` at startup loads ALL embeddings into a Python dict

### Bottleneck #2: Startup Full-Load

```python
# store.py:640-646
rows = self._conn.execute("SELECT id, embedding FROM memories WHERE embedding IS NOT NULL").fetchall()
```

1M embeddings = 1.5GB BLOB reads, deserialized into individual numpy arrays. Startup: 10-30 seconds.

### Bottleneck #3: SQLite Single-Writer

Single connection with `check_same_thread=False`. WAL mode helps reads but writes serialize at 50-100 TPS.

### Bottleneck #4: FTS5 Rebuild is O(n)

`_rebuild_fts()` does DELETE + INSERT of the entire table. 1M records = 10+ second blocking operation.

CJK tokenizer is `unicode61` -- tokenizes Chinese by individual characters, not semantic units.

### Bottleneck #5: Consolidation O(n^2)

Pairwise Jaccard similarity on bigrams. 100K memories = 5 billion comparisons.

### Bottleneck #6: Relevance Formula -- No Semantic Signal

```python
# l0_memory.py:15-32
score = recency * importance * frequency * decay
```

- No semantic similarity factor (cosine sim not used in scoring)
- No emotional salience
- Fixed 30-day half-life: memories >6 months have score <0.001
- No context-awareness

### Bottleneck #7: Text-Only Memory Model

`content TEXT NOT NULL` -- no support for images, audio, video, spatial data.

### Bottleneck #8: Weak Embedding Model

`all-MiniLM-L6-v2`: 384-dim, English-centric, poor CJK performance. No GPU path, no batch encoding.

### Bottleneck #9: Sync Hub In-Memory

All events stored in a Python list. Linear dedup scan on each push.

---

## Part II: Super Memory Architecture

### Storage: 4-Tier Design

```
Tier 0  Working Memory     <1ms      Last 100 entries + FAISS FlatIP        <50MB RAM
Tier 1  Hot (hnswlib)      1-3ms     Last 6 months, up to 500K entries      ~800MB
Tier 2  Warm (Qdrant/PQ)   10-30ms   Up to 10M entries, PQ quantized        ~640MB
Tier 3  Cold Archive       50-200ms  Unlimited, sparse index + bloom filter  Disk/S3
```

- User never knows which tier a memory lives in
- Accessed cold memories auto-promote to warm after 2 accesses in 30 days

### Sub-100ms Latency Breakdown

| Stage | Budget | Mechanism |
|-------|--------|-----------|
| Query embedding | 5-15ms | BGE-M3 ONNX INT8 quantized |
| HNSW vector search | 1-3ms | hnswlib in-process, mmap index |
| FTS5 text search | 2-5ms | SQLite FTS5 (parallel with vector) |
| T2 search (if needed) | 10-30ms | Qdrant gRPC + PQ |
| Merge + re-rank | 1-2ms | Reciprocal Rank Fusion |
| Object hydration | 2-5ms | SQLite batch fetch by IDs |
| **Total** | **21-60ms** | |

Key optimizations:
1. **ONNX Runtime** for embedding (3-8ms vs 15-30ms PyTorch)
2. **Parallel search** via ThreadPoolExecutor (vector + text + graph concurrent)
3. **mmap index loading** (OS page cache manages hot/cold pages)
4. **Pre-computed embedding cache** (contiguous numpy array, not dict of arrays)
5. **Background index maintenance** (new memories searchable via FTS5 before HNSW update)
6. **PQ quantization** for warm tier (1024-dim -> 64 bytes, 10M entries = 640MB)

### Multimodal Pipeline

```
Input (any modality)
    |
    v
ModalityRouter
    |
    +---> TextPipeline:    tokenize -> embed(BGE-M3 1024d) -> store
    +---> ImagePipeline:   caption(LLaVA/Gemini) -> embed(CLIP 768d) -> blob_store + store
    +---> AudioPipeline:   transcribe(Whisper) -> embed(BGE-M3) -> blob_store + store
    +---> VideoPipeline:   keyframe_extract -> caption_each -> embed -> blob_store + store
    +---> SpatialPipeline: serialize(scene_graph) -> embed(text_desc) -> blob_store + store
    |
    v
UnifiedEmbeddingSpace (every memory has text embedding; images also get CLIP embedding)
```

Cross-modal retrieval: text query -> embed with both BGE-M3 + CLIP text encoder -> search both spaces -> Reciprocal Rank Fusion

#### Schema v2

```sql
CREATE TABLE memories_v2 (
    id                TEXT PRIMARY KEY,
    type              TEXT NOT NULL,       -- fact|episode|preference|relation|skill|perception
    modality          TEXT NOT NULL DEFAULT 'text',  -- text|image|audio|video|spatial|multimodal
    content           TEXT,                -- text content or caption
    content_hash      TEXT,
    blob_ref          TEXT,                -- content-addressed ref to blob store
    blob_size         INTEGER DEFAULT 0,
    mime_type         TEXT,
    source            TEXT,
    confidence        REAL DEFAULT 1.0,
    emotional_valence REAL DEFAULT 0.0,    -- -1.0 to +1.0
    emotional_arousal REAL DEFAULT 0.0,    -- 0.0 to 1.0
    created_at        REAL,
    accessed_at       REAL,
    access_count      INTEGER DEFAULT 0,
    decay_weight      REAL DEFAULT 1.0,
    tier              INTEGER DEFAULT 1,
    embedding_model   TEXT,
    embedding_dim     INTEGER,
    meta              TEXT
);

-- Multiple embeddings per memory (text + CLIP + future models)
CREATE TABLE embeddings (
    memory_id   TEXT NOT NULL,
    model       TEXT NOT NULL,    -- 'bge-m3', 'clip-vit', 'imagebind'
    dimension   INTEGER NOT NULL,
    vector      BLOB NOT NULL,
    created_at  REAL,
    PRIMARY KEY (memory_id, model),
    FOREIGN KEY (memory_id) REFERENCES memories_v2(id)
);
```

#### Blob Store

```
~/.mindos/blobs/
    ab/cd/abcd1234...5678.png        # content-addressed SHA-256
    ab/cd/abcd1234...5678.png.meta   # JSON: {mime_type, dimensions, duration}
```

### Relevance Scoring 2.0

```
final_score = (
    0.40 * semantic_similarity +           -- cosine sim from vector search (NEW)
    0.20 * recency_score +                 -- adaptive half-life by memory type
    0.15 * importance_score +              -- confidence * emotional_intensity (NEW)
    0.10 * contextual_relevance +          -- same platform/time/topic (NEW)
    0.10 * emotional_resonance +           -- mood-congruent recall (NEW)
    0.05 * frequency_score                 -- log(access_count + 2)
) * decay_weight
```

Adaptive half-life (replaces fixed 30 days):

| Memory Type | Half-Life |
|-------------|-----------|
| episode | 14 days |
| fact | 90 days |
| preference | 60 days |
| skill | 180 days |
| relation | 120 days |

Emotional intensity:
```python
importance = confidence * (1.0 + abs(valence) * arousal)
```

Mood-congruent recall (cognitive science: people recall memories matching current mood):
```python
emotional_resonance = (1.0 - abs(current_valence - mem.valence)) * mem.arousal
```

Phase 3 addition: Cross-encoder re-ranker (BGE-reranker-v2-m3 ONNX) on top-50 candidates for complex queries.

---

## Part III: Implementation Roadmap

### Phase 1: Quick Wins (1-2 weeks, zero breaking changes)

| Change | File | Impact |
|--------|------|--------|
| numpy brute-force -> hnswlib HNSW | `store.py` | Vector search: O(n) -> O(log n), <3ms |
| MiniLM -> BGE-M3 | `core.py` | CJK quality from poor to excellent |
| Add semantic_similarity to scoring | `l0_memory.py` | Retrieval relevance jumps |
| Add emotional columns | `store.py` schema | Foundation for emotional scoring |
| Batch embedding | `core.py` | Commit pipeline 5-10x faster |

Backward compatible: hnswlib is optional (fallback to numpy). Existing DBs auto-migrate.

### Phase 2: Infrastructure (2-4 weeks)

| Change | New Module | Impact |
|--------|-----------|--------|
| ONNX Runtime embedding | `mindos/embedding.py` | 3-8ms per embed (was 15-30ms) |
| Content-addressed blob store | `mindos/blob_store.py` | Multimodal data storage |
| Multimodal ingest pipelines | `mindos/ingest.py` | Image/audio/video/spatial support |
| Separate embeddings table | `store.py` migration | Multi-model embeddings per memory |
| Write batching | `store.py` | 10-50x write throughput under load |
| Tiered retrieval | `l0_memory.py` | T0 -> T1 -> T2 cascade |

### Phase 3: Full Scale (4-8 weeks)

| Change | New Module | Impact |
|--------|-----------|--------|
| CLIP cross-modal retrieval | `mindos/cross_modal.py` | Text-to-image search |
| Qdrant Tier 2 | `mindos/stores/qdrant_store.py` | 10M+ memories, PQ quantized |
| Cross-encoder re-ranker | `mindos/reranker.py` | Top-50 precision boost |
| Knowledge graph retrieval | `l0_memory.py` | Graph-path-enhanced recall |
| R-tree spatial index | `store.py` | "What do I remember about this room?" |
| Tier promotion/demotion | `mindos/tier_manager.py` | Automatic memory lifecycle |

---

## Part IV: Key Technical Decisions

### hnswlib vs FAISS vs Annoy

| Library | Recall@10 | Latency (1M) | Install | Decision |
|---------|-----------|-------------|---------|----------|
| **hnswlib** | 98% | 0.5ms | `pip install` | **Phase 1-2** |
| FAISS IVF-PQ | 93% | 0.3ms | Complex (MKL) | Phase 3 optional |
| Annoy | 90% | 2ms | `pip install` | Too low recall |

### BGE-M3 vs alternatives

| Model | Dims | CJK | CPU Latency | Size |
|-------|------|-----|-------------|------|
| **BGE-M3** | 1024 | Excellent | 8ms (ONNX) | 2.3GB |
| E5-large-v2 | 1024 | Good | 10ms | 1.3GB |
| MiniLM-L6 (current) | 384 | Poor | 3ms | 80MB |

### Why keep SQLite as source of truth

SQLite + hnswlib as external index file. Preserves Mindos's killer feature: everything is local files, zero-config, offline-capable, portable. Qdrant is an optional Tier 2 add-on, not a replacement.

### Dependencies (progressive, all optional)

```toml
[project.optional-dependencies]
vector = ["hnswlib>=0.8"]
fast-embed = ["onnxruntime>=1.16"]
multimodal = ["Pillow>=10.0", "open-clip-torch>=2.24"]
scale = ["qdrant-client>=1.7"]
all = ["hnswlib", "onnxruntime", "qdrant-client", "Pillow"]
```

System remains fully functional with zero optional deps (current behavior). Each capability unlocked by installing the relevant extra.

### Sync implications

- Memory content syncs via existing event log (unchanged)
- Embeddings regenerated locally (not synced -- devices may have different models)
- Blobs sync lazily on first access (content-addressed = trivial dedup)
- HNSW index rebuilt locally from synced data

---

## Part V: Configuration

```yaml
# ~/.mindos/config.yaml additions
embedding:
  model: bge-m3
  backend: onnx          # or: pytorch
  dimension: 1024
  batch_size: 32

vector_index:
  backend: hnswlib       # or: numpy (fallback)
  m: 16
  ef_construction: 200
  ef_search: 50

tiers:
  t1_max_age_days: 180
  t2_backend: qdrant     # or: duckdb, disabled
  t2_url: localhost:6333

relevance:
  w_semantic: 0.40
  w_recency: 0.20
  w_importance: 0.15
  w_frequency: 0.05
  w_context: 0.10
  w_emotional: 0.10

blob_store:
  path: blobs/
  max_blob_size_mb: 50
```

---

## Priority Files (by implementation impact)

1. **`store.py`** -- Schema v2 migration, embeddings table, hnswlib replacement, write batching
2. **`l0_memory.py`** -- Relevance 2.0 formula, tiered recall, parallel search
3. **`core.py`** -- ONNXEmbedder, commit_multimodal(), ingest() API
4. **`config.py`** -- New config sections
5. **`pyproject.toml`** -- Optional dependency groups
