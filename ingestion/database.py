"""FoodFlow Ingestion Database Connectivity

Provides PostgreSQL 16 connection management using psycopg 3.
Enforces explicit transaction boundaries, parameterized execution,
context-managed sessions, schema verification, and connection health diagnostics.

Note on Database Roles:
Dataset ingestion modifies tables across both 'profile_nutrition' (USDA FDC)
and 'recipe_catalog' (Food.com and RecipeNLG). Ingestion must connect using
the administrative account ('foodflow_admin' or superuser 'postgres').
Application service roles are restricted to single schemas and must never
be used for cross-schema ingestion.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional, Tuple

from ingestion.config import get_database_url, mask_database_url
from ingestion.logging_config import get_logger


logger = get_logger("database")

REQUIRED_SCHEMAS = ("profile_nutrition", "recipe_catalog", "meal_planner")


class DatabaseConnectionError(Exception):
    """Raised when connecting to PostgreSQL fails or configuration is missing."""
    pass


class DependencyMissingError(DatabaseConnectionError):
    """Raised when psycopg 3 is not installed in the active Python environment."""
    pass


def _import_psycopg():
    """Lazily import psycopg 3, providing an actionable error message if missing."""
    try:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg, dict_row
    except ImportError as e:
        raise DependencyMissingError(
            "The 'psycopg' package is required for database connectivity but is not installed.\n"
            "Install ingestion dependencies via:\n"
            "    pip install -r ingestion/requirements.txt\n"
            "or:\n"
            "    pip install psycopg[binary]"
        ) from e


@contextmanager
def get_connection(
    database_url: Optional[str] = None,
    autocommit: bool = False,
) -> Generator[Any, None, None]:
    """Context manager yielding an active psycopg connection.
    
    Guarantees proper closing and rollback on unhandled exceptions.
    """
    url = database_url or get_database_url()
    if not url:
        raise DatabaseConnectionError(
            "Database connection URL is not configured.\n"
            "Set the DATABASE_URL or FOODFLOW_DATABASE_URL environment variable.\n"
            "Example: export DATABASE_URL='postgresql://foodflow_admin:CHANGE_ME@localhost:5432/foodflow_db'"
        )

    psycopg, _ = _import_psycopg()

    conn = None
    try:
        conn = psycopg.connect(url, autocommit=autocommit)
        yield conn
        if not autocommit and not conn.closed:
            conn.commit()
    except Exception as e:
        if conn and not conn.closed and not autocommit:
            try:
                conn.rollback()
            except Exception:
                pass
        if isinstance(e, (DatabaseConnectionError, DependencyMissingError)):
            raise
        masked = mask_database_url(url)
        raise DatabaseConnectionError(
            f"Failed to connect or execute against database [{masked}]: {e}"
        ) from e
    finally:
        if conn and not conn.closed:
            conn.close()


@dataclass
class DatabaseHealthStatus:
    is_connected: bool
    server_version: Optional[str] = None
    connected_user: Optional[str] = None
    database_name: Optional[str] = None
    schemas_found: Dict[str, bool] = None
    error_message: Optional[str] = None

    def all_schemas_present(self) -> bool:
        if not self.schemas_found:
            return False
        return all(self.schemas_found.values())


def check_health(database_url: Optional[str] = None) -> DatabaseHealthStatus:
    """Perform a read-only health check against PostgreSQL.
    
    Verifies connection, server version, session identity, and presence of all
    three required FoodFlow schemas without modifying database state.
    """
    url = database_url or get_database_url()
    if not url:
        return DatabaseHealthStatus(
            is_connected=False,
            error_message="DATABASE_URL is not set in environment.",
        )

    try:
        psycopg, _ = _import_psycopg()
    except DependencyMissingError as e:
        return DatabaseHealthStatus(
            is_connected=False,
            error_message=str(e),
        )

    try:
        with psycopg.connect(url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                # Query session metadata
                cur.execute(
                    "SELECT version(), current_user, current_database();"
                )
                row = cur.fetchone()
                version_str = row[0] if row else "Unknown"
                user_str = row[1] if row else "Unknown"
                db_str = row[2] if row else "Unknown"

                # Check schemas
                cur.execute(
                    """
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name IN ('profile_nutrition', 'recipe_catalog', 'meal_planner');
                    """
                )
                found = {r[0] for r in cur.fetchall()}
                schemas_status = {s: (s in found) for s in REQUIRED_SCHEMAS}

                return DatabaseHealthStatus(
                    is_connected=True,
                    server_version=version_str,
                    connected_user=user_str,
                    database_name=db_str,
                    schemas_found=schemas_status,
                )
    except Exception as e:
        return DatabaseHealthStatus(
            is_connected=False,
            error_message=f"Database connection error: {e}",
        )


def verify_schemas_exist(database_url: Optional[str] = None) -> Dict[str, bool]:
    """Verify that all three required FoodFlow schemas exist in the database."""
    health = check_health(database_url)
    if not health.is_connected or not health.schemas_found:
        raise DatabaseConnectionError(
            f"Cannot verify schemas: {health.error_message or 'Connection failed'}"
        )
    return health.schemas_found

