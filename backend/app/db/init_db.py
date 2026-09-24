"""Database schema initialization. Creates all registered SQLAlchemy models in the target database."""

import logging
from app.db.base import Base
from app.db.session import engine
# Ensure all models are imported so Base.metadata knows about them
import app.models  # noqa: F401

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Create all domain tables if they do not exist."""
    logger.info("Initializing database schema on %s...", engine.url)
    if engine.dialect.name == "postgresql":
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
