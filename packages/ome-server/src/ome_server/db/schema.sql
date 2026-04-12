-- Ome Enterprise Schema v1: PostgreSQL + RLS + pgvector + tsvector
-- This file is the source of truth. Applied by engine.ensure_schema().

-- ═══════════════════════════════════════════════════════════════════
-- Extensions
-- ═══════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";       -- pgvector
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- trigram fuzzy search

-- ═══════════════════════════════════════════════════════════════════
-- Application role (connections from ome-server use this role)
-- The superuser/migration role creates tables; app_role has RLS.
-- ═══════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ome_app') THEN
        CREATE ROLE ome_app NOLOGIN;
    END IF;
END
$$;

-- ═══════════════════════════════════════════════════════════════════
-- Tenants
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id TEXT UNIQUE NOT NULL,          -- maps to user_id / session_id
    name        TEXT NOT NULL DEFAULT '',
    kind        TEXT NOT NULL DEFAULT 'user',  -- 'user' | 'anon' | 'npc'
    password_hash TEXT,                        -- bcrypt for users, NULL for anon/npc
    config      JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    migrated_from TEXT                         -- anon session_id if migrated
);

CREATE INDEX IF NOT EXISTS idx_tenants_kind ON tenants(kind);

-- ═══════════════════════════════════════════════════════════════════
-- Memories (replaces SQLite memories table)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS memories (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    type         TEXT NOT NULL,                -- fact | episode | preference | relation | skill | utterance
    content      TEXT NOT NULL,
    content_hash TEXT,                         -- MD5 prefix for fuzzy dedup
    source       TEXT DEFAULT '',
    confidence   REAL DEFAULT 1.0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    accessed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    access_count INTEGER DEFAULT 0,
    decay_weight REAL DEFAULT 1.0,
    embedding    vector(1536),                 -- pgvector (OpenAI ada-002 / text-embedding-3-small)
    meta         JSONB DEFAULT '{}',

    -- Full-text search column (auto-maintained by trigger)
    tsv          tsvector GENERATED ALWAYS AS (
                     setweight(to_tsvector('simple', coalesce(content, '')), 'A')
                 ) STORED
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_mem_tenant     ON memories(tenant_id);
CREATE INDEX IF NOT EXISTS idx_mem_type       ON memories(tenant_id, type);
CREATE INDEX IF NOT EXISTS idx_mem_created    ON memories(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_mem_hash       ON memories(tenant_id, content_hash);
CREATE INDEX IF NOT EXISTS idx_mem_fts        ON memories USING GIN(tsv);
CREATE INDEX IF NOT EXISTS idx_mem_trgm       ON memories USING GIN(content gin_trgm_ops);
-- pgvector HNSW index (better for high-recall ANN than ivfflat)
CREATE INDEX IF NOT EXISTS idx_mem_embedding  ON memories USING hnsw(embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ═══════════════════════════════════════════════════════════════════
-- Knowledge Graph
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS knowledge_graph (
    tenant_id  UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    subject    TEXT NOT NULL,
    predicate  TEXT NOT NULL,
    object     TEXT NOT NULL,
    source     TEXT DEFAULT '',
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, subject, predicate, object)
);

CREATE INDEX IF NOT EXISTS idx_kg_subject ON knowledge_graph(tenant_id, subject);

-- ═══════════════════════════════════════════════════════════════════
-- Personality History
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS personality_history (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id  UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    snapshot   JSONB,
    trigger    TEXT,
    diff       JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ph_tenant ON personality_history(tenant_id, created_at);

-- ═══════════════════════════════════════════════════════════════════
-- Soul State (key-value per tenant)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS soul_state (
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    key       TEXT NOT NULL,
    value     JSONB,                           -- JSONB instead of TEXT for queryability
    PRIMARY KEY (tenant_id, key)
);

-- ═══════════════════════════════════════════════════════════════════
-- Sync Journal
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS sync_journal (
    seq        BIGSERIAL PRIMARY KEY,
    tenant_id  UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_id   UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    device_id  TEXT NOT NULL DEFAULT 'server',
    op         TEXT NOT NULL,
    payload    JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    synced_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sync_tenant    ON sync_journal(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sync_unsynced  ON sync_journal(tenant_id, synced_at) WHERE synced_at IS NULL;

-- ═══════════════════════════════════════════════════════════════════
-- Row-Level Security — Zero-Trust Tenant Isolation
--
-- Every connection MUST SET LOCAL app.current_tenant = '<uuid>'
-- before any query. RLS policies enforce that each tenant can only
-- see/modify its own rows. Even application bugs cannot leak data.
-- ═══════════════════════════════════════════════════════════════════

ALTER TABLE memories             ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_graph      ENABLE ROW LEVEL SECURITY;
ALTER TABLE personality_history  ENABLE ROW LEVEL SECURITY;
ALTER TABLE soul_state           ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_journal         ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owners (defense in depth)
ALTER TABLE memories             FORCE ROW LEVEL SECURITY;
ALTER TABLE knowledge_graph      FORCE ROW LEVEL SECURITY;
ALTER TABLE personality_history  FORCE ROW LEVEL SECURITY;
ALTER TABLE soul_state           FORCE ROW LEVEL SECURITY;
ALTER TABLE sync_journal         FORCE ROW LEVEL SECURITY;

-- Policies: tenant_id must match app.current_tenant
-- Using a helper function for clean, indexable predicates

CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS UUID AS $$
    SELECT nullif(current_setting('app.current_tenant', true), '')::uuid;
$$ LANGUAGE sql STABLE PARALLEL SAFE;

-- Drop existing policies first (idempotent re-runs)
DO $$
DECLARE
    t TEXT;
BEGIN
    FOR t IN SELECT unnest(ARRAY['memories', 'knowledge_graph', 'personality_history', 'soul_state', 'sync_journal'])
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation ON %I', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I '
            'USING (tenant_id = current_tenant_id()) '
            'WITH CHECK (tenant_id = current_tenant_id())',
            t
        );
    END LOOP;
END $$;

-- Grant app role access to tables (but RLS restricts what they see)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ome_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ome_app;
