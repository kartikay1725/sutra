import logging
import threading
import time

from app.db.session import SessionLocal
from app.services.session_reaper_service import SessionReaperService

logger = logging.getLogger(__name__)

class SessionReaperWorker:
    """
    Background worker that periodically runs the SessionReaperService
    to revoke idle and expired agent sessions.
    """
    
    def __init__(self, interval_seconds: int = 30):
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread = None
        self.reaper_service = SessionReaperService()

    def start(self):
        if self._thread is not None:
            return
        logger.info("Starting Session Reaper Worker...")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        if self._thread is None:
            return
        logger.info("Stopping Session Reaper Worker...")
        self._stop_event.set()
        self._thread.join(timeout=5)
        self._thread = None

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._run_once()
            except Exception as exc:
                logger.error(f"Error in Session Reaper Worker: {exc}", exc_info=True)
            
            # Sleep in small increments to allow responsive stopping
            for _ in range(self.interval_seconds):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _run_once(self):
        with SessionLocal() as db:
            self.reaper_service.revoke_idle_sessions(db)
            self.reaper_service.revoke_expired_sessions(db)
