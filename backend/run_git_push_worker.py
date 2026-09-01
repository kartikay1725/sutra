from __future__ import annotations

import argparse
import logging
import signal
import sys
import json
import traceback
from datetime import datetime, timezone

from app.services.git_push_event_worker import GitPushEventWorker
from app.core.config import settings

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(log_record)

def setup_logging(json_logs: bool):
    logger = logging.getLogger("sutra.worker")
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ))
    logger.addHandler(handler)
    return logger

def main() -> None:
    parser = argparse.ArgumentParser(description="SUTRA Git Push Event Worker")
    parser.add_argument("--json-logs", action="store_true", help="Output logs in JSON format")
    parser.add_argument("--interval", type=float, help="Worker poll interval in seconds", default=settings.worker_interval_seconds)
    parser.add_argument("--batch-size", type=int, help="Number of events to process per batch", default=settings.worker_batch_size)
    parser.add_argument("--stale-timeout", type=int, help="Stale event timeout in seconds", default=settings.worker_stale_timeout_seconds)
    args = parser.parse_args()

    logger = setup_logging(args.json_logs)

    worker = GitPushEventWorker(
        interval_seconds=args.interval,
        batch_size=args.batch_size,
        stale_timeout_seconds=args.stale_timeout
    )

    def shutdown(signum, frame) -> None:
        logger.info(f"Received shutdown signal {signum}, waiting for current batch to finish...")
        worker.stop()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Starting SUTRA Git push event worker")

    try:
        worker.run_forever()
    except KeyboardInterrupt:
        logger.info("Worker interrupted")
        worker.stop()
    finally:
        logger.info("SUTRA Git push event worker exited")

if __name__ == "__main__":
    main()