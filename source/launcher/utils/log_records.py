"""Offset-addressed log records and cancellable, incremental file readers."""

import queue
import re
import threading
import time
from dataclasses import dataclass
from os import stat_result
from pathlib import Path
from typing import BinaryIO

from PySide6.QtCore import QObject, QTimer, Signal

PAGE_SIZE = 2000
BLOCK_SIZE = 65536
FILE_HEADER = re.compile(r"^(?:\[(?:DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|TEMPLATE)\]\s*)?(\d{2}:\d{2}:\d{2}(?:[.,]\d+)?) - ([A-Z]+) - (.*?) - (.*)$", re.S)
PREFIX = re.compile(r"^\[([A-Z _]+)\]\s*(.*)$", re.S)
PROTOCOL = ("[QUEUE_STATE]", "__RUNNER_STATE__", "__RUNNER_READY__")


@dataclass(frozen=True)
class LogRecord:
    """An immutable record whose identity survives filtering and file pagination."""

    identity: tuple
    order: tuple
    timestamp: str
    level: str
    source: str
    message: str
    raw: str

    def matches(self, query: str, level: str = "ALL", errors_only: bool = False):
        """Apply literal search and semantic severity predicates."""
        return (
            (level == "ALL" or self.level == level)
            and (not errors_only or self.level in {"ERROR", "CRITICAL"})
            and query.casefold() in f"{self.timestamp} {self.level} {self.source} {self.message}".casefold()
        )


def parse_record(raw: str, identity: tuple, order: tuple, received: str = ""):
    """Parse file or launcher formats without inferring severity from message words."""
    text = raw.rstrip("\r\n")
    match = FILE_HEADER.match(text)
    if match:
        stamp, level, source, message = match.groups()
    else:
        match = PREFIX.match(text)
        level, message = match.groups() if match else ("INFO", text)
        stamp, source = received or "\u2014", "\u2014"
    level = {"WARNING": "WARN"}.get(level, level)
    return LogRecord(identity, order, stamp, level, source, message, text)


def file_identity(stat: stat_result):
    """Identify replacement files independently of their changing modification time."""
    return stat.st_dev, stat.st_ino


def reverse_lines(handle: BinaryIO, end: int, cancel: threading.Event):
    """Read UTF-8 lines backward in bounded binary blocks, retaining byte offsets."""
    position, remainder = end, b""
    while position and not cancel.is_set():
        start = max(0, position - BLOCK_SIZE)
        handle.seek(start)
        data = handle.read(position - start) + remainder
        pieces = data.split(b"\n")
        remainder = pieces[0]
        offset = start + len(data)
        for line in reversed(pieces[1:]):
            offset -= len(line)
            if line:
                yield offset, line.rstrip(b"\r").decode("utf-8", errors="replace")
            offset -= 1
        position = start
    if remainder and not cancel.is_set():
        yield 0, remainder.rstrip(b"\r").decode("utf-8", errors="replace")


def reverse_records(handle: BinaryIO, end: int, generation: int, cancel: threading.Event):
    """Group traceback continuations with their header while scanning newest first."""
    pending = []
    first = 0
    for offset, line in reverse_lines(handle, end, cancel):
        if line.startswith(PROTOCOL):
            continue
        pending.append(line)
        first = offset
        if FILE_HEADER.match(line) or PREFIX.match(line) or (not line[:1].isspace() and not line.startswith("Traceback") and not re.match(r"\w*(?:Error|Exception):", line)):
            raw = "\n".join(reversed(pending))
            yield parse_record(raw, ("file", generation, offset), (offset, 0))
            pending.clear()
    if pending:
        yield parse_record("\n".join(reversed(pending)), ("file", generation, first), (first, 0))


def read_page(path: Path, end: int, generation: int, cancel: threading.Event, count: int = PAGE_SIZE):
    """Read one history page without scanning the entire file."""
    records = []
    with path.open("rb") as handle:
        for record in reverse_records(handle, end, generation, cancel):
            records.append(record)
            if len(records) >= count:
                break
    return list(reversed(records)), records[-1].order[0] if records else 0


class LogFileStore(QObject):
    """Run disk I/O off-thread; publish results on the GUI thread in small batches."""

    changed = Signal(object, str)
    status = Signal(str)
    initial = Signal(object)
    reset = Signal()
    search_batch = Signal(object, bool)

    def __init__(self, path: str, parent: QObject):
        """Create independent file/history and whole-file-search cancellation domains."""
        super().__init__(parent)
        self.path = Path(path)
        self.generation = 0
        self.search_id = 0
        self.cancel = threading.Event()
        self.search_cancel = threading.Event()
        self.results = queue.Queue(maxsize=12)
        self.busy = False
        self.closed = False
        self.ready = False
        self.identity: tuple[int, int] | None = None
        self.end = 0
        self.oldest = 0
        self.checkpoint = b""
        self.tail_start = 0
        self.drain = QTimer(self)
        self.drain.setInterval(50)
        self.drain.timeout.connect(self._drain)
        self.drain.start()
        self.poll = QTimer(self)
        self.poll.setInterval(1000)
        self.poll.timeout.connect(self.refresh)

    def _publish(self, message: tuple, cancel: threading.Event):
        """Bound queued results so a fast disk cannot flood the GUI event loop."""
        while not cancel.is_set():
            try:
                self.results.put(message, timeout=0.05)
                return
            except queue.Full:
                continue

    def start(self):
        """Begin initial loading once and monitor future file changes."""
        if not self.poll.isActive() and not self.closed:
            self.poll.start()
            self.refresh()

    def reload(self):
        """Invalidate stale reads before loading the current file generation."""
        self.cancel.set()
        self.cancel = threading.Event()
        self.cancel_search()
        self.generation += 1
        self.ready = False
        self.busy = False
        self.identity = None
        self.end = self.oldest = self.tail_start = 0
        self.checkpoint = b""
        self.reset.emit()
        self.start()
        self.refresh()

    def stop(self):
        """Stop timers and make all workers abandon pending results."""
        self.closed = True
        self.cancel.set()
        self.search_cancel.set()
        self.poll.stop()
        self.drain.stop()

    def _valid_snapshot(self, identity: tuple[int, int], end: int, checkpoint: bytes):
        """Reject replacement or rewritten history before publishing offset-based rows."""
        stat = self.path.stat()
        if file_identity(stat) != identity or stat.st_size < end:
            return False
        with self.path.open("rb") as handle:
            handle.seek(max(0, end - len(checkpoint)))
            return handle.read(len(checkpoint)) == checkpoint

    def refresh(self):
        """Check append, replacement, and truncation in a background reader."""
        if self.busy or self.closed:
            return
        self.busy = True
        generation, cancel = self.generation, self.cancel
        identity, end, checkpoint, ready, tail_start = self.identity, self.end, self.checkpoint, self.ready, self.tail_start

        def work():
            """Snapshot the file and reread the final record to join continuations."""
            try:
                stat = self.path.stat()
                current = file_identity(stat)
                size = stat.st_size
                with self.path.open("rb") as handle:
                    handle.seek(max(0, end - len(checkpoint)))
                    valid = handle.read(len(checkpoint)) == checkpoint
                    if ready and (current != identity or size < end or not valid):
                        self._publish((generation, "rotate", None), cancel)
                        return
                    handle.seek(max(0, size - 64))
                    check = handle.read(min(64, size))
                if not ready:
                    records, oldest = read_page(self.path, size, generation, cancel)
                    if self._valid_snapshot(current, size, check):
                        self._publish((generation, "initial", (records, oldest, current, size, check)), cancel)
                    else:
                        self._publish((generation, "rotate", None), cancel)
                elif size > end:
                    # Read only newly appended bytes plus the last incomplete/multiline record.
                    with self.path.open("rb") as handle:
                        records = []
                        for record in reverse_records(handle, size, generation, cancel):
                            if record.order[0] < tail_start:
                                break
                            records.append(record)
                    if not self._valid_snapshot(current, size, check):
                        self._publish((generation, "rotate", None), cancel)
                        return
                    records.reverse()
                    for start in range(0, len(records), 200):
                        self._publish((generation, "append", (records[start : start + 200], current, size, check, start + 200 >= len(records))), cancel)
                    if not records:
                        self._publish((generation, "idle", None), cancel)
                else:
                    self._publish((generation, "idle", None), cancel)
            except OSError as exc:
                self._publish((generation, "error", str(exc)), cancel)

        threading.Thread(target=work, daemon=True, name="logs-file-reader").start()

    def older(self):
        """Fetch one older page; callers preserve the visible row while inserting it."""
        if self.busy or not self.ready or self.closed or not self.oldest:
            return
        identity, snapshot_end, checkpoint = self.identity, self.end, self.checkpoint
        if identity is None:
            return
        self.busy = True
        generation, cancel, end = self.generation, self.cancel, self.oldest
        self.status.emit("Loading older records...")

        def work():
            """Read the preceding page under the current cancellation generation."""
            try:
                result = read_page(self.path, end, generation, cancel)
                if self._valid_snapshot(identity, snapshot_end, checkpoint):
                    self._publish((generation, "older", result), cancel)
                else:
                    self._publish((generation, "rotate", None), cancel)
            except OSError as exc:
                self._publish((generation, "error", str(exc)), cancel)

        threading.Thread(target=work, daemon=True, name="logs-history").start()

    def cancel_search(self):
        """Invalidate any queued batches from a previous search query."""
        self.search_cancel.set()
        self.search_id += 1
        self.search_cancel = threading.Event()

    def search(self, query: str, level: str, errors_only: bool):
        """Stream whole-file matches from newest to oldest without blocking Qt."""
        self.cancel_search()
        if not query or not self.ready:
            return
        generation, search_id, cancel, end = self.generation, self.search_id, self.search_cancel, self.end
        identity, checkpoint = self.identity, self.checkpoint
        if identity is None:
            return
        self.status.emit("Searching file...")

        def work():
            """Deliver individual early matches and bounded batches with backpressure."""
            batch, last = [], time.monotonic()
            try:
                with self.path.open("rb") as handle:
                    for record in reverse_records(handle, end, generation, cancel):
                        if cancel.is_set():
                            return
                        if record.matches(query, level, errors_only):
                            batch.append(record)
                        if len(batch) >= 200 or (batch and time.monotonic() - last >= 0.05):
                            if not self._valid_snapshot(identity, end, checkpoint):
                                self._publish((generation, "rotate", None), cancel)
                                return
                            self._publish((generation, "search", (search_id, batch, False)), cancel)
                            batch, last = [], time.monotonic()
                    if self._valid_snapshot(identity, end, checkpoint):
                        self._publish((generation, "search", (search_id, batch, True)), cancel)
                    else:
                        self._publish((generation, "rotate", None), cancel)
            except OSError as exc:
                self._publish((generation, "search_error", (search_id, str(exc))), cancel)

        threading.Thread(target=work, daemon=True, name="logs-search").start()

    def _drain(self):
        """Apply bounded worker messages on the GUI thread, rejecting stale work."""
        for _ in range(2):
            try:
                generation, kind, data = self.results.get_nowait()
            except queue.Empty:
                return
            if generation != self.generation or self.closed:
                continue
            if kind == "search":
                search_id, records, done = data
                if search_id == self.search_id:
                    self.search_batch.emit(records, done)
                continue
            if kind == "search_error":
                if data[0] == self.search_id:
                    self.status.emit("Search failed: " + data[1] + " — edit search to retry")
                continue
            self.busy = kind == "append" and not data[-1]
            if kind == "rotate":
                self.reload()
            elif kind == "error":
                self.status.emit("Log file unavailable: " + data + " — retrying")
            elif kind in {"initial", "append"}:
                if kind == "initial":
                    records, self.oldest, self.identity, self.end, self.checkpoint = data
                else:
                    records, self.identity, self.end, self.checkpoint, _final = data
                self.ready = True
                if records:
                    self.tail_start = records[-1].order[0]
                self.changed.emit(records, kind)
                if kind == "initial":
                    self.initial.emit([record.raw for record in records])
                self.status.emit("")
            elif kind == "older":
                records, self.oldest = data
                self.changed.emit(records, kind)
                self.status.emit("" if self.oldest else "Beginning of log file")
