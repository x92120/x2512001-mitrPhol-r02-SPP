"""
Database Configuration Module
=============================
SQLAlchemy database connection setup for MySQL/MariaDB.
Supports runtime switching between CloudDB and RemoteDB.

Environment Variables:
- DB_USER: Database username
- DB_PASSWORD: Database password
- DB_HOST: Database host address (default active DB)
- DB_PORT: Database port (default: 3306)
- DB_NAME: Database name
- CLOUD_DB: Cloud database host
- REMOTE_DB: Remote database host
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

DB_USER = os.getenv("DB_USER", "mixingcontrol")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin100")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "xMixingControl")

# Database hosts
CLOUD_HOST = os.getenv("CLOUD_DB", "152.42.166.150")
REMOTE_HOST = os.getenv("REMOTE_DB", "192.168.121.11")

# Available database configurations
DB_CONFIGS = {
    "cloudDB": {
        "label": "Cloud DB",
        "host": CLOUD_HOST,
        "icon": "cloud",
    },
    "remoteDB": {
        "label": "Remote DB",
        "host": REMOTE_HOST,
        "icon": "dns",
    },
}

# Active database state (default to remoteDB)
_active_db_key = os.getenv("ACTIVE_DB", "cloudDB")


def _build_url(host: str) -> str:
    return f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{host}:{DB_PORT}/{DB_NAME}?connect_timeout=5"


def _create_engine_for(host: str):
    url = _build_url(host)
    return create_engine(url, pool_pre_ping=False, pool_recycle=3600)


# Initial engine and session
_active_host = DB_CONFIGS[_active_db_key]["host"]
engine = _create_engine_for(_active_host)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()


def get_active_db_key() -> str:
    """Return the key of the currently active database ('cloudDB' or 'remoteDB')."""
    return _active_db_key


def get_active_db_info() -> dict:
    """Return full info about the currently active database."""
    cfg = DB_CONFIGS[_active_db_key]
    return {
        "key": _active_db_key,
        "label": cfg["label"],
        "host": cfg["host"],
        "icon": cfg["icon"],
    }


def set_active_db(key: str) -> dict:
    """
    Switch the active database engine at runtime.
    key must be 'cloudDB' or 'remoteDB'.
    """
    global _active_db_key, engine, SessionLocal

    if key not in DB_CONFIGS:
        raise ValueError(f"Invalid DB key '{key}'. Must be one of: {list(DB_CONFIGS.keys())}")

    old_key = _active_db_key
    cfg = DB_CONFIGS[key]

    # Dispose old engine connections
    engine.dispose()

    # Rebuild engine and session
    engine = _create_engine_for(cfg["host"])
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    _active_db_key = key

    logger.info(f"Switched active database: {old_key} → {key} ({cfg['host']})")

    return {
        "previous": old_key,
        "current": key,
        "host": cfg["host"],
        "label": cfg["label"],
    }


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
