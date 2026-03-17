"""
Database Configuration Module
=============================
SQLAlchemy database connection setup for MySQL/MariaDB.
Connects to the Remote DB (192.168.121.11).

Environment Variables:
- DB_USER: Database username
- DB_PASSWORD: Database password
- DB_HOST: Database host address
- DB_PORT: Database port (default: 3306)
- DB_NAME: Database name
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

# Database host — Remote DB only
DB_HOST = os.getenv("REMOTE_DB", "192.168.121.11")


def _build_url(host: str) -> str:
    return f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{host}:{DB_PORT}/{DB_NAME}?connect_timeout=5"


def _create_engine_for(host: str):
    url = _build_url(host)
    return create_engine(url, pool_pre_ping=False, pool_recycle=3600)


# Engine and session
engine = _create_engine_for(DB_HOST)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative models
Base = declarative_base()


def get_active_db_info() -> dict:
    """Return info about the active database."""
    return {
        "key": "remoteDB",
        "label": "Remote DB",
        "host": DB_HOST,
        "icon": "dns",
    }


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
