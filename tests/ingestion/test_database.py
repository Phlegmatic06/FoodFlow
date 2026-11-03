"""Unit tests for database connection error handling, schema checks, and diagnostics."""

import os
import unittest
from unittest.mock import patch

from ingestion.database import (
    DatabaseConnectionError,
    DependencyMissingError,
    check_health,
    get_connection,
    verify_schemas_exist,
)


class TestDatabaseConnection(unittest.TestCase):

    def test_missing_database_url_raises_connection_error(self):
        with patch.dict(os.environ, {}, clear=True):
            # Explicitly unset both variables
            os.environ.pop("DATABASE_URL", None)
            os.environ.pop("FOODFLOW_DATABASE_URL", None)

            health = check_health()
            self.assertFalse(health.is_connected)
            self.assertIn("DATABASE_URL is not set", health.error_message)

            with self.assertRaises(DatabaseConnectionError):
                with get_connection():
                    pass

    def test_verify_schemas_fails_when_disconnected(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            os.environ.pop("FOODFLOW_DATABASE_URL", None)

            with self.assertRaises(DatabaseConnectionError):
                verify_schemas_exist()

    def test_psycopg_missing_error_guidance(self):
        with patch("ingestion.database._import_psycopg") as mock_import:
            mock_import.side_effect = DependencyMissingError(
                "The 'psycopg' package is required but not installed."
            )
            with self.assertRaises(DependencyMissingError) as ctx:
                with get_connection("postgresql://user:pass@localhost:5432/db"):
                    pass
            self.assertIn("psycopg", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

