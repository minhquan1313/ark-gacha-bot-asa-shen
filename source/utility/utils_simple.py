import time
from typing import Literal, cast

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


def clock_tracker():
    """Function that return float value in SECOND time"""
    start = time.time()

    def diff():
        """Return elapsed time in second"""
        return time.time() - start

    return diff


class TimedOutCounter:
    """Track whether a configurable timeout duration has elapsed."""

    def __init__(self, limit_seconds: float = 3):
        self.limit_seconds = limit_seconds
        self.reset()

    def __call__(self):
        """Return True when the timeout duration has elapsed."""
        return time.monotonic() >= self._timeout

    def reset(self):
        """Restart the timeout countdown using the current duration."""
        self._timeout = time.monotonic() + self.limit_seconds


def timed_out_counter(limit_seconds: float = 3):
    """Create a resettable timeout checker."""
    return TimedOutCounter(limit_seconds)


def get_default_clock(
    deadline: float = config.timeout_deadline,
    multiplier: float = 1,
):
    """Create the default timeout checker."""
    return timed_out_counter(deadline * multiplier)


def get_default_timeout_value():
    return config.timeout_deadline
