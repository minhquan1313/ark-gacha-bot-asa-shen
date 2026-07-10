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


class TemplateLogger(logging.Logger):
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


with open("source/join_sim/source/logs/logs.txt", "w") as file:
    file.close()

logging_level = logging.DEBUG

logging.setLoggerClass(TemplateLogger)
setattr(logging.Logger, "template", TemplateLogger.template)  # noqa: B010
logger = cast(TemplateLogger, logging.getLogger("reconnect"))
logging.basicConfig(
    filename="source/join_sim/source/logs/logs.txt",
    level=logging_level,
    format="%(asctime)s - %(levelname)s - %(funcName)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger.setLevel(logging_level)
