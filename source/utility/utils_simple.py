import math
import subprocess
import sys
import time
import weakref
from typing import Literal, TypeAlias, cast

import settings
from settings import APP_ID
from source.ASA import config

"""
FUNCTION FOR EASIER LIFE
"""


def grid_loc_gen(
    *,
    col: int | None = None,
    row: int | None = None,
    direction: Literal["x", "y"] = "x",
):
    """Create a function that returns a grid position for an item index."""

    if col is None and row is None:
        raise ValueError("Either col or row must be provided")

    if col is not None and col <= 0:
        raise ValueError("col must be greater than 0")

    if row is not None and row <= 0:
        raise ValueError("row must be greater than 0")

    if direction not in {"x", "y"}:
        raise ValueError("direction must be either 'x' or 'y'")

    max_items = col * row if col is not None and row is not None else None

    def gen(index: int = 0):
        """
        Return the column and row for an item index.

        Args:
            index: Zero-based item index.

        Returns:
            tuple[int, int]: A tuple containing ``(column, row)``.

        Example:
            ```python
            loc_gen = grid_loc_gen(row=5)
            for i in range(5):
                col, row = loc_gen(i) # <--- Here
                ...
            ```
        """

        if index < 0:
            raise IndexError("index must not be negative")

        if max_items is not None and index >= max_items:
            return cast(tuple[int, int], (-1, -1))

        if col is not None and row is None:
            current_row, current_col = divmod(index, col)
            return current_col, current_row

        if row is not None and col is None:
            current_col, current_row = divmod(index, row)
            return current_col, current_row

        if col is None or row is None:
            raise ValueError("Both col and row are required for two-direction grids")

        if direction == "x":
            current_row, current_col = divmod(index, col)
        else:
            current_col, current_row = divmod(index, row)

        return current_col, current_row

    return gen


_live_clocks: weakref.WeakSet["TimedOutCounter"] = weakref.WeakSet()


def reset_all_clocks():
    """Restart every live clock with its full configured duration."""
    for clock in list(_live_clocks):
        clock.reset()


def adjust_clocks_after_pause(paused_at: float, resumed_at: float):
    """Exclude paused time since each live clock's latest start or reset."""
    for clock in list(_live_clocks):
        paused_seconds = max(0.0, resumed_at - max(paused_at, clock._started))
        clock._started += paused_seconds
        clock._timeout += paused_seconds


class TimedOutCounter:
    """Track whether a configurable timeout duration has elapsed."""

    _timeout = 0
    _started = 0
    limit_seconds = 0

    def __init__(self, limit_seconds: float = 3.0):
        self.limit_seconds = limit_seconds
        self.reset()
        _live_clocks.add(self)

    def __call__(self):
        """Return True when the timeout duration has elapsed."""
        return time.monotonic() >= self._timeout

    def reset(self):
        """Restart the timeout countdown using the current duration."""
        self._started = time.monotonic()
        self._timeout = self._started + self.limit_seconds

    def force_timed_out(self):
        self._timeout = time.monotonic() - 1

    def eslapsed(self):
        return time.monotonic() - self._started

    def remain(self):
        return self._timeout - time.monotonic()

    def eslapsed_str(self, normalized=False):
        seconds = math.ceil(self.eslapsed())
        return self.to_string(normalized=normalized, num=seconds)

    def remain_str(self, normalized=False):
        seconds = math.ceil(self.remain())
        return self.to_string(normalized=normalized, num=seconds)

    def to_string(self, num: int | None = None, normalized=False):
        seconds = math.ceil(self.limit_seconds if not isinstance(num, int) else num)
        if normalized and seconds > 60:
            m, s = divmod(seconds, 60)
            if s > 0:
                return f"{m}m:{s}s"
            else:
                return f"{m}m"

        return f"{seconds}s"


def get_default_clock(
    deadline: float = config.timeout_deadline,
    multiplier: float = 1,
):
    """Create the default timeout checker."""
    return TimedOutCounter(deadline * multiplier)


def get_default_timeout_value():
    return config.timeout_deadline


def start_subprocess(cmd: list[str], *args, **kwargs):
    """Start a child process while retaining its command and adding its app id."""
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
        )
    return subprocess.Popen(
        [*cmd, "--app-id", APP_ID],
        *args,
        **kwargs,
    )


TBase: TypeAlias = Literal["fast", "complicated", "single_player"]
BASE_DELAY: dict[TBase, float] = {
    "fast": 0.1,
    "complicated": 0.3,
    "single_player": 0.1,
}


def sleep(type: TBase = "fast"):
    base = BASE_DELAY.get(type, 0.1)
    delay_add = (settings.ping / 1000) * 1.2
    delay = base + delay_add
    time.sleep(delay)
