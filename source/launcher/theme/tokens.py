from source.launcher.constants import (
    BREAKPOINT_NARROW_WIDTH,
    COLORS,
    FONT_SIZES,
    HELPER_HEIGHT,
    HELPER_WIDTH,
    MINIMAL_HELPER_RUNNING_WIDTH,
    PHONE_MINIMUM_SIZE,
    TITLE_BAR_HEIGHT,
)

THEME_TOKENS = {
    "colors": COLORS,
    "fontSizes": FONT_SIZES,
    "sizes": {
        "breakpointNarrowWidth": BREAKPOINT_NARROW_WIDTH,
        "titleBarHeight": TITLE_BAR_HEIGHT,
        "helperWidth": HELPER_WIDTH,
        "helperHeight": HELPER_HEIGHT,
        "minimalHelperRunningWidth": MINIMAL_HELPER_RUNNING_WIDTH,
        "minimumWidth": PHONE_MINIMUM_SIZE[0],
        "minimumHeight": PHONE_MINIMUM_SIZE[1],
    },
}
