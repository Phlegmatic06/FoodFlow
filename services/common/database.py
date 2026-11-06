"""Database connection pool management and readiness checking for FoodFlow microservices."""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from typing import Generator, Optional

import psycopg
from psycopg import sql
from psycopg_pool import ConnectionPool

from services.common.config import mask_database_url
from services.common.models import DatabaseReadinessInfo

logger = logging.getLogger("foodflow.database")


class ServiceDatabaseManager:
    """Manages a connection pool for a specific microservice with role and schema enforcement."""

    _SENSITIVE_PATTERN = re.compile(r":([^@/]+)@")

    def __init__(
        self,
        service_name: str,
        expected_role: str,
        target_schema: str,
        probe_table: str,
        dsn: Optional[str] = None,
        min_size: int = 1,
        max_size: int = 10,
        timeout: float = 5.0,
    ) -> None:
        self.service_name = service_name
        self.expected_role = expected_role
        self.target_schema = target_schema
        self.probe_table = probe_table
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.timeout = timeout
        self._pool: Optional[ConnectionPool] = None

    @classmethod
    def mask_error_message(cls, message: str) -> str:
        """Sanitize error messages to ensure no passwords or credentials leak in status responses."""
        if not message:
            return ""
        return cls._SENSITIVE_PATTERN.sub(r":********@", str(message))

    def open(self) -> None:
        """Initialize and open the database connection pool."""
        if not self.dsn:
            logger.warning(
                "Cannot initialize connection pool for %s: database DSN is not configured",
                self.service_name,
            )
            return

        if self._pool is not None:
            return

        logger.info(
            "Initializing connection pool for %s (role: %s, schema: %s, target: %s)",
            self.service_name,
            self.expected_role,
            self.target_schema,
            mask_database_url(self.dsn),
        )

        try:
            self._pool = ConnectionPool(
                conninfo=self.dsn,
                min_size=self.min_size,
                max_size=self.max_size,
                timeout=self.timeout,
                open=False,
            )
            # Open workers in background without blocking server startup
            self._pool.open(wait=False)
        except Exception as e:
            masked_err = self.mask_error_message(str(e))
            logger.error(
                "Failed to initialize connection pool for %s: %s",
                self.service_name,
                masked_err,
            )
            self._pool = None

    def close(self) -> None:
        """Close all connections and terminate the pool gracefully."""
        if self._pool is not None:
            logger.info("Closing connection pool for %s", self.service_name)
            try:
                self._pool.close()
            except Exception as e:
                logger.warning("Error while closing pool for %s: %s", self.service_name, e)
            finally:
                self._pool = None

    @contextmanager
    def connection(self) -> Generator[psycopg.Connection, None, None]:
        """Context manager yielding an active database connection from the pool."""
        if self._pool is None:
            raise RuntimeError(
                f"Database connection pool for '{self.service_name}' is not initialized or configured"
            )
        with self._pool.connection(timeout=self.timeout) as conn:
            yield conn

    def check_readiness(self) -> DatabaseReadinessInfo:
        """Verify database connectivity, role credentials, and schema table accessibility."""
        if not self.dsn:
            return DatabaseReadinessInfo(
                connected=False,
                user=None,
                schema_name=self.target_schema,
                database=None,
                error="Database connection string is not configured",
            )

        if self._pool is None:
            return DatabaseReadinessInfo(
                connected=False,
                user=None,
                schema_name=self.target_schema,
                database=None,
                error="Connection pool is not initialized",
            )

        try:
            with self._pool.connection(timeout=self.timeout) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT current_user, current_database();")
                    row = cur.fetchone()
                    if not row:
                        return DatabaseReadinessInfo(
                            connected=False,
                            user=None,
                            schema_name=self.target_schema,
                            database=None,
                            error="Unable to retrieve current database user",
                        )

                    current_user, current_db = row[0], row[1]

                    # Strict security enforcement: administrative roles are forbidden for microservices
                    if current_user in ("foodflow_admin", "postgres"):
                        return DatabaseReadinessInfo(
                            connected=False,
                            user=current_user,
                            schema_name=self.target_schema,
                            database=current_db,
                            error=(
                                f"Security violation: Service '{self.service_name}' connected "
                                f"using forbidden administrative role '{current_user}'"
                            ),
                        )

                    # Role expectation verification
                    if self.expected_role and current_user != self.expected_role:
                        return DatabaseReadinessInfo(
                            connected=False,
                            user=current_user,
                            schema_name=self.target_schema,
                            database=current_db,
                            error=(
                                f"Role mismatch: Service '{self.service_name}' expected role "
                                f"'{self.expected_role}', but connected as '{current_user}'"
                            ),
                        )

                    # Verify accessibility of service-owned schema via probe query
                    probe_stmt = sql.SQL("SELECT 1 FROM {}.{} LIMIT 1;").format(
                        sql.Identifier(self.target_schema),
                        sql.Identifier(self.probe_table),
                    )
                    cur.execute(probe_stmt)
                    cur.fetchone()

                    return DatabaseReadinessInfo(
                        connected=True,
                        user=current_user,
                        schema_name=self.target_schema,
                        database=current_db,
                        error=None,
                    )
        except Exception as e:
            masked_err = self.mask_error_message(str(e))
            logger.warning(
                "Readiness probe failed for %s: %s",
                self.service_name,
                masked_err,
            )
            return DatabaseReadinessInfo(
                connected=False,
                user=None,
                schema_name=self.target_schema,
                database=None,
                error=masked_err,
            )

