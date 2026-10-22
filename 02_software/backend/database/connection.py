
from database.database_manager import (
    DATABASE_DIR,
    MAX_DATABASE_SIZE_MB,
    MAX_DATABASE_SIZE_BYTES,
    get_connection,
    get_database_paths,
    initialize_database,
)


# Backward-compatible alias.
DATABASE_PATH = DATABASE_DIR


__all__ = [
    "DATABASE_DIR",
    "DATABASE_PATH",
    "MAX_DATABASE_SIZE_MB",
    "MAX_DATABASE_SIZE_BYTES",
    "get_connection",
    "get_database_paths",
    "initialize_database",
]
