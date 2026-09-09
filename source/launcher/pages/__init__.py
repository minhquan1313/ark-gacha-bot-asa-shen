from source.launcher.pages.base import BasePagesMixin
from source.launcher.pages.common import _counted_title, _deposit_route_child_count
from source.launcher.pages.craft import CraftPagesMixin
from source.launcher.pages.dedi import DediPagesMixin
from source.launcher.pages.gacha import GachaPagesMixin
from source.launcher.pages.helpers import HelperPagesMixin
from source.launcher.pages.home import HomePagesMixin
from source.launcher.pages.logs_tools import LogsToolsPagesMixin
from source.launcher.pages.pego import PegoPagesMixin
from source.launcher.pages.settings import SettingsPagesMixin


class LauncherPagesMixin(
    BasePagesMixin,
    HomePagesMixin,
    SettingsPagesMixin,
    DediPagesMixin,
    CraftPagesMixin,
    GachaPagesMixin,
    PegoPagesMixin,
    HelperPagesMixin,
    LogsToolsPagesMixin,
):
    pass


__all__ = [
    "LauncherPagesMixin",
    "_counted_title",
    "_deposit_route_child_count",
]
