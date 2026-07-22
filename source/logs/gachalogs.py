import logging
from types import TracebackType
from typing import Mapping, cast

from source.launcher.config.constants import GACHA_LOG_FILE

""" FOR TEMPLATE DEBUGGING """
TEMPLATE_LEVEL = 5
logging.addLevelName(TEMPLATE_LEVEL, "TEMPLATE")

ExcInfoType = (
    bool
    | BaseException
    | tuple[type[BaseException], BaseException, TracebackType | None]
    | None
)


class LoggerExtended(logging.Logger):
    def template(
        self,
        msg: object,
        *args: object,
        exc_info: ExcInfoType = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Mapping[str, object] | None = None,
    ):
        if self.isEnabledFor(TEMPLATE_LEVEL):
            self._log(
                TEMPLATE_LEVEL,
                msg,
                args,
                exc_info=exc_info,
                extra=extra,
                stack_info=stack_info,
                stacklevel=stacklevel,
            )


logging.Logger.template = LoggerExtended.template  # type: ignore

file_name = GACHA_LOG_FILE
_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(funcName)s - %(message)s",
    datefmt="%H:%M:%S",
)
_logger_file = logging.FileHandler(
    file_name,
    encoding="utf-8",
)
_logger_file.setFormatter(_formatter)
_logger_file.setLevel(logging.DEBUG)

logger = cast(LoggerExtended, logging.getLogger("Gacha"))
logger.setLevel(logging.DEBUG)
logger.addHandler(_logger_file)

logger.propagate = False


def enable_log():
    logger.disabled = False


def disable_log():
    logger.disabled = True


def clear_log():
    with open(file_name, "w") as file:
        file.close()


def _clean_up_on_start():
    with open(file_name, "rb") as file:
        line_count = sum(
            chunk.count(b"\n") for chunk in iter(lambda: file.read(1024 * 1024), b"")
        )

    if line_count > 100_000:
        clear_log()


_clean_up_on_start()
