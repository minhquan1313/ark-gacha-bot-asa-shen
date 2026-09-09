"""Remember daily update attempts independently of user settings."""

import json
import os
from datetime import date, datetime
from pathlib import Path

from source.launcher.utils.update_service import REPOSITORY_ROOT

CACHE_PATH = REPOSITORY_ROOT / ".update_check.json"


class UpdateSchedule:
    def __init__(self, path: Path = CACHE_PATH):
        """Load the last local check date, treating invalid caches as absent."""
        self.path = path
        self.last_date = None
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            stamp = datetime.fromisoformat(document["timestamp"])
            saved_date = date.fromisoformat(document["date"])
            if stamp.date() == saved_date:
                self.last_date = saved_date
        except (OSError, ValueError, TypeError, KeyError):
            pass

    def is_due(self, now: datetime):
        """Allow one attempt when the local calendar date changes."""
        return self.last_date != now.date()

    def record_attempt(self, now: datetime):
        """Remember an attempt even if persisting its atomic cache fails."""
        self.last_date = now.date()
        temporary = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        try:
            temporary.write_text(
                json.dumps(
                    {
                        "date": self.last_date.isoformat(),
                        "timestamp": now.isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
