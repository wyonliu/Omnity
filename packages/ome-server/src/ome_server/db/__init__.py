"""Enterprise PostgreSQL + RLS multi-tenant database layer.

When DATABASE_URL is set, ome-server uses PostgreSQL with Row-Level Security
for zero-trust tenant isolation. Without it, falls back to per-user SQLite.

Architecture:
    Request → JWT → middleware SET LOCAL app.current_tenant = <tenant_uuid>
                          ↓
              PgMemoryStore (drop-in for Mindos MemoryStore)
                          ↓
              PostgreSQL + RLS + pgvector + tsvector + pg_trgm
"""

from ome_server.db.engine import get_pool, close_pool, tenant_connection, ensure_schema

__all__ = ["get_pool", "close_pool", "tenant_connection", "ensure_schema"]
