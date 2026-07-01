from source.launcher.pages.common import (
    ASSETS,
    QIcon,
    QSize,
)


class BasePagesMixin:
    def _icon_button(
        self, icon_key, tooltip="", variant="secondary", width=36, icon_size=32
    ):
        button = self._button("", variant)
        button.setObjectName("HelperIconButton")
        button.setIcon(QIcon(ASSETS[icon_key]))
        button.setIconSize(QSize(icon_size, icon_size))
        button.setMinimumWidth(width)
        # button.setFixedWidth(width)
        if tooltip:
            button.setToolTip(tooltip)
        return button
