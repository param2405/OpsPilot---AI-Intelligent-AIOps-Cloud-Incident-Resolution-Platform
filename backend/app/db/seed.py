"""Command-line interface for reproducible database seeding.

Usage:
    python -m app.db.seed [--days 7] [--seed 42] [--step-minutes 5] [--clean]
"""

import argparse
import logging
import sys

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models.deployment import Deployment
from app.models.incident import Incident
from app.models.log import LogEntry
from app.models.metric import Metric
from app.models.service import Service
from app.services.synthetic_data_generator import SyntheticDataGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed")


def clean_db() -> None:
    """Purge all existing rows across observability tables."""
    db = SessionLocal()
    try:
        logger.info("Cleaning existing observability data...")
        db.query(Metric).delete()
        db.query(LogEntry).delete()
        db.query(Incident).delete()
        db.query(Deployment).delete()
        db.query(Service).delete()
        db.commit()
        logger.info("Existing observability data wiped cleanly.")
    except Exception as exc:
        db.rollback()
        logger.error("Failed to clean database: %s", exc)
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed OpsPilot AI observability data.")
    parser.add_argument("--days", type=int, default=7, help="Number of historical days to simulate (default: 7)")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed (default: 42)")
    parser.add_argument("--step-minutes", type=int, default=5, help="Telemetry time step in minutes (default: 5)")
    parser.add_argument("--clean", action="store_true", help="Wipe existing records before generating")
    args = parser.parse_args()

    # Step 1: Ensure tables exist
    init_db()

    # Step 2: Clean if requested
    if args.clean:
        clean_db()

    # Step 3: Run generator
    db = SessionLocal()
    try:
        logger.info(
            "Generating synthetic data (days=%d, seed=%d, step_minutes=%d)...",
            args.days,
            args.seed,
            args.step_minutes,
        )
        generator = SyntheticDataGenerator(db=db, seed=args.seed)
        stats = generator.generate(days=args.days, step_minutes=args.step_minutes)

        logger.info("==================================================")
        logger.info("  OpsPilot AI Synthetic Observability Data Created")
        logger.info("==================================================")
        logger.info("  Services:    %d", stats["services"])
        logger.info("  Deployments: %d", stats["deployments"])
        logger.info("  Incidents:   %d", stats["incidents"])
        logger.info("  Metrics:     %d", stats["metrics"])
        logger.info("  Logs:        %d", stats["logs"])
        logger.info("==================================================")
    except Exception as exc:
        db.rollback()
        logger.exception("Data generation failed: %s", exc)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
