"""Connection pool + tenant context manager for PostgreSQL + RLS.

Usage:
    # At startup
    pool = get_pool("postgresql://user:pass@host/db")
    await ensure_schema(pool)

    # Per request (in FastAPI dependency)
    with tenant_connection(pool, tenant_uuid) as conn:
        conn.execute("SELECT * FROM memories")  # only sees this tenant's rows
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

log = logging.getLogger("ome_server.db")

_pool: Optional[ConnectionPool] = None


def get_pool(dsn: Optional[str] = None, min_size: int = 2, max_size: int = 20) -> ConnectionPool:
    """Get or create the global connection pool.

    Args:
        dsn: PostgreSQL connection string. Defaults to DATABASE_URL env var.
        min_size: Minimum connections to keep warm.
        max_size: Maximum concurrent connections.
    """
    global _pool
    if _pool is not None:
        return _pool

    dsn = dsn or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL not set. Either set the env var or pass dsn= to get_pool()."
        )

    _pool = ConnectionPool(
        conninfo=dsn,
        min_size=min_size,
        max_size=max_size,
        kwargs={"row_factory": dict_row, "autocommit": False},
        open=True,
    )
    log.info("PostgreSQL pool created: min=%d max=%d", min_size, max_size)
    return _pool


def close_pool() -> None:
    """Close the global pool (call on app shutdown)."""
    global _pool
    if _pool:
        _pool.close()
        _pool = None
        log.info("PostgreSQL pool closed")


@contextmanager
def tenant_connection(pool: ConnectionPool, tenant_id: str):
    """Yield a connection with RLS tenant context set.

    Sets `app.current_tenant` via SET LOCAL (transaction-scoped),
    so RLS policies automatically filter to this tenant's rows.

    Usage:
        with tenant_connection(pool, "550e8400-...") as conn:
            rows = conn.execute("SELECT * FROM memories").fetchall()
    """
    with pool.connection() as conn:
        with conn.transaction():
            conn.execute(
                "SET LOCAL app.current_tenant = %s", (tenant_id,)
            )
            yield conn


@contextmanager
def admin_connection(pool: ConnectionPool):
    """Yield a connection WITHOUT RLS tenant context — for schema ops and tenant management.

    WARNING: No RLS filtering. Use only for:
    - Schema migrations
    - Creating/looking up tenants
    - Cross-tenant admin operations
    """
    with pool.connection() as conn:
        with conn.transaction():
            # Reset tenant to empty so RLS returns nothing for data tables
            conn.execute("SET LOCAL app.current_tenant = ''")
            yield conn


def ensure_schema(pool: ConnectionPool) -> None:
    """Apply the schema DDL idempotently (all CREATE IF NOT EXISTS).

    Safe to call on every startup. For production, use Alembic migrations instead.
    """
    schema_path = Path(__file__).parent / "schema.sql"
    ddl = schema_path.read_text()

    with pool.connection() as conn:
        with conn.transaction():
            conn.execute(ddl)
    log.info("Schema applied successfully")


def get_or_create_tenant(
    pool: ConnectionPool,
    external_id: str,
    name: str = "",
    kind: str = "user",
    password_hash: Optional[str] = None,
) -> str:
    """Look up tenant by external_id, or create if not exists. Returns tenant UUID."""
    with pool.connection() as conn:
        with conn.transaction():
            row = conn.execute(
                "SELECT id FROM tenants WHERE external_id = %s",
                (external_id,),
            ).fetchone()
            if row:
                return str(row["id"])

            row = conn.execute(
                "INSERT INTO tenants (external_id, name, kind, password_hash) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (external_id, name or external_id, kind, password_hash),
            ).fetchone()
            log.info("Created tenant: external_id=%s kind=%s uuid=%s", external_id, kind, row["id"])
            return str(row["id"])


def get_tenant_by_external_id(pool: ConnectionPool, external_id: str) -> Optional[dict]:
    """Look up tenant by external_id. Returns dict or None."""
    with pool.connection() as conn:
        return conn.execute(
            "SELECT * FROM tenants WHERE external_id = %s",
            (external_id,),
        ).fetchone()


def migrate_tenant(
    pool: ConnectionPool,
    from_external_id: str,
    to_external_id: str,
    new_name: str = "",
    new_password_hash: Optional[str] = None,
) -> str:
    """Migrate an anonymous tenant to a registered user. Returns tenant UUID.

    Updates the tenant record in place (same UUID, same data). This is
    the key advantage of single-DB multi-tenant: migration is a metadata update,
    not a data copy.
    """
    with pool.connection() as conn:
        with conn.transaction():
            row = conn.execute(
                "UPDATE tenants SET "
                "  external_id = %s, "
                "  name = coalesce(nullif(%s, ''), name), "
                "  kind = 'user', "
                "  password_hash = %s, "
                "  migrated_from = %s "
                "WHERE external_id = %s "
                "RETURNING id",
                (to_external_id, new_name, new_password_hash, from_external_id, from_external_id),
            ).fetchone()
            if not row:
                raise ValueError(f"Tenant '{from_external_id}' not found")
            log.info("Migrated tenant: %s → %s (uuid=%s)", from_external_id, to_external_id, row["id"])
            return str(row["id"])
