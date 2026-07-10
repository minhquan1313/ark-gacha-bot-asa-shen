import logging
from collections.abc import Mapping
from types import TracebackType
from typing import cast

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
        message: object,
        *args: object,
        exc_info: ExcInfoType = None,
        extra: Mapping[str, object] | None = None,
        stack_info: bool = False,
        stacklevel: int = 1,
    ):
        if self.isEnabledFor(TEMPLATE_LEVEL):
            self._log(
                TEMPLATE_LEVEL,
                message,
                args,
                exc_info=exc_info,
                extra=extra,
                stack_info=stack_info,
                stacklevel=stacklevel,
            )


# with open("source/logs/logs.txt", 'w') as file:
#     file.close()

logging.setLoggerClass(LoggerExtended)
setattr(logging.Logger, "template", LoggerExtended.template)  # noqa: B010
logging_level = logging.DEBUG

logger = cast(LoggerExtended, logging.getLogger("Gacha"))
logging.basicConfig(
    filename="source/logs/logs.txt",
    level=logging_level,
    format="%(asctime)s - %(levelname)s - %(funcName)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger.setLevel(logging_level)
