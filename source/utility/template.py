import json
import time
from contextlib import contextmanager
from typing import TypeAlias

import cv2
import numpy as np
from cv2.typing import MatLike

from source.logs import gachalogs as logs
from source.utility import screen
from source.utility.types import RoiRegion, RoiRegionKey

roi_regions: dict[RoiRegionKey, RoiRegion] = {
    "bed_radical": {"start_x": 840, "start_y": 258, "width": 188, "height": 188},
    "beds_title": {"start_x": 75, "start_y": 75, "width": 555, "height": 135},
    "beds_title_respawn": {"start_x": 75, "start_y": 75, "width": 555, "height": 135},
    "console": {"start_x": 0, "start_y": 1050, "width": 38, "height": 30},
    "crop_plot": {"start_x": 825, "start_y": 187, "width": 233, "height": 113},
    "crop_plot_prompt": {"start_x": 300, "start_y": 0, "width": 1400, "height": 1080},
    "crystal_in_hotbar": {
        "start_x": 562,
        "start_y": 937,
        "width": 795,
        "height": 188,
    },
    "death_regions": {"start_x": 75, "start_y": 75, "width": 525, "height": 150},
    "dedi": {"start_x": 825, "start_y": 183, "width": 267, "height": 53},
    "vault": {"start_x": 825, "start_y": 183, "width": 267, "height": 113},
    "grinder": {"start_x": 825, "start_y": 183, "width": 267, "height": 53},
    "grinder_grind_button": {
        "start_x": 730,
        "start_y": 730,
        "width": 450,
        "height": 200,
    },
    "tek_trough": {"start_x": 877, "start_y": 195, "width": 161, "height": 30},
    "exit_resume": {"start_x": 412, "start_y": 337, "width": 1253, "height": 660},
    "inventory": {"start_x": 150, "start_y": 93, "width": 270, "height": 113},
    "inventory_drop": {
        "start_x": 1455,
        "start_y": 170,
        "width": 60,
        "height": 60,
    },
    "inventory_player_drop": {
        "start_x": 430,
        "start_y": 170,
        "width": 60,
        "height": 60,
    },
    "inventory_player_transfer_all": {
        "start_x": 300,
        "start_y": 120,
        "width": 300,
        "height": 150,
    },
    "seed_inv": {"start_x": 412, "start_y": 337, "width": 1253, "height": 660},
    "slot_capped": {"start_x": 1680, "start_y": 985, "width": 113, "height": 75},
    "teleporter_title": {"start_x": 150, "start_y": 101, "width": 304, "height": 139},
    "teleporter_write_your_text": {
        "start_x": 760,
        "start_y": 260,
        "width": 400,
        "height": 300,
    },
    "tribelog_check": {"start_x": 500, "start_y": 26, "width": 800, "height": 113},
    "waiting_inv": {"start_x": 1500, "start_y": 75, "width": 375, "height": 188},
    "teleporter_icon": {"start_x": 600, "start_y": 150, "width": 1268, "height": 825},
    "teleporter_icon_pressed": {
        "start_x": 600,
        "start_y": 150,
        "width": 1268,
        "height": 825,
    },
    "first_slot": {"start_x": 165, "start_y": 228, "width": 98, "height": 98},
    "player_stats": {"start_x": 840, "start_y": 180, "width": 225, "height": 675},
    "show_buff": {"start_x": 900, "start_y": 862, "width": 150, "height": 38},
    "item_snow_owl_pellet": {
        "start_x": 150,
        "start_y": 112,
        "width": 600,
        "height": 600,
    },
    "item_fertilizer": {"start_x": 150, "start_y": 112, "width": 600, "height": 600},
    "item_fertilizer_fece": {
        "start_x": 150,
        "start_y": 112,
        "width": 600,
        "height": 600,
    },
    "orange": {"start_x": 540, "start_y": 200, "width": 1, "height": 1},
    "transfer_orange": {"start_x": 220, "start_y": 320, "width": 1, "height": 1},
    "chem_bench": {"start_x": 825, "start_y": 183, "width": 267, "height": 53},
    "indi_forge": {"start_x": 825, "start_y": 183, "width": 267, "height": 53},
    "access_inv": {"start_x": 412, "start_y": 337, "width": 1253, "height": 660},
    "search": {"start_x": 337, "start_y": 952, "width": 90, "height": 30},
    "search_death_screen": {"start_x": 50, "start_y": 900, "width": 343, "height": 132},
    "search_player_inv": {"start_x": 62, "start_y": 62, "width": 430, "height": 246},
    "search_object_inv": {"start_x": 1100, "start_y": 62, "width": 430, "height": 246},
    "server_list_trans_loaded": {
        "start_x": 140,
        "start_y": 280,
        "width": 70,
        "height": 160,
    },
    "server_trans_uploaded": {"start_x": 765, "start_y": 0, "width": 382, "height": 60},
    "transfer_join_button": {
        "start_x": 1504,
        "start_y": 857,
        "width": 270,
        "height": 68,
    },
    "transfer_not_ready_popup": {
        "start_x": 730,
        "start_y": 300,
        "width": 560,
        "height": 200,
    },
    "transmitter_server_excess": {
        "start_x": 340,
        "start_y": 0,
        "width": 1200,
        "height": 60,
    },
    "transmitter_server_fail_connection": {
        "start_x": 674,
        "start_y": 247,
        "width": 579,
        "height": 536,
    },
    "transmitter_server_fail_attempting": {
        "start_x": 674,
        "start_y": 247,
        "width": 579,
        "height": 536,
    },
    "transmitter_inv": {
        "start_x": 970,
        "start_y": 110,
        "width": 200,
        "height": 70,
    },
    "transmitter_server_menu": {
        "start_x": 200,
        "start_y": 210,
        "width": 350,
        "height": 100,
    },
    "transmitter_server_search": {
        "start_x": 1390,
        "start_y": 160,
        "width": 220,
        "height": 50,
    },
    "steam_launch_option": {
        "start_x": 702,
        "start_y": 300,
        "width": 500,
        "height": 500,
    },
    "steam_cloud_sync_conflic": {
        "start_x": 620,
        "start_y": 350,
        "width": 680,
        "height": 360,
    },
    "structure_turn_on": {
        "start_x": 755,
        "start_y": 658,
        "width": 420,
        "height": 264,
    },
    "trans_inv_ready": {
        "start_x": 1455,
        "start_y": 20,
        "width": 395,
        "height": 220,
    },
    "dedi_deposit_ready": {
        "start_x": 880,
        "start_y": 850,
        "width": 120,
        "height": 55,
    },
    "dedi_deposit_clear": {
        "start_x": 735,
        "start_y": 780,
        "width": 450,
        "height": 150,
    },
    "capture_item_player_second_slot": {
        "start_x": 270,
        "start_y": 240,
        "width": 87,
        "height": 87,
    },
}

# Playground https://pseudopencv.site/utilities/hsvcolormask/
TBound: TypeAlias = tuple[int, int, int]
BoundCouple: TypeAlias = tuple[TBound, TBound]

default_bounds: BoundCouple = (0, 30, 200), (255, 255, 255)
default_no_bounds: BoundCouple = (0, 0, 0), (255, 255, 255)

# Use this for fully white element UI
white_bounds: BoundCouple = ((0, 0, 200), (255, 10, 255))
# Use this when element is cyan color, check fishing_success.png for the cyan color reference
blue_bounds: BoundCouple = (90, 30, 200), (100, 255, 255)


# Use this to overwrite the bounds of opencv2.
# Playground https://pseudopencv.site/utilities/hsvcolormask/
template_l_bounds_overwrite: dict[RoiRegionKey, tuple[int, int, int]] = {
    # saturation to 0 so the white underline will still be tracked
    "beds_title_respawn": (0, 0, 200),
    "inventory_player_drop": (90, 30, 130),
    "inventory_drop": (90, 30, 130),
    "inventory_player_transfer_all": (90, 30, 130),
    "server_trans_uploaded": (40, 30, 180),
    "item_snow_owl_pellet": (0, 30, 0),
    "item_fertilizer": (0, 30, 0),
    "item_fertilizer_fece": (0, 30, 0),
    "transmitter_inv": (0, 0, 200),
    "crop_plot_prompt": white_bounds[0],
}
template_u_bounds_overwrite: dict[RoiRegionKey, tuple[int, int, int]] = {
    "server_trans_uploaded": (70, 255, 255),
    "item_snow_owl_pellet": (60, 255, 255),
    "item_fertilizer": (60, 255, 255),
    "item_fertilizer_fece": (60, 255, 255),
    "crop_plot_prompt": white_bounds[1],
}


# Use this to overwrite what template image will be used to compare.
# This help reduce duplicate template images, but they serve only 1 template but different location
template_image_overwrite: dict[RoiRegionKey, RoiRegionKey] = {
    #
    "search_object_inv": "search_player_inv",
    "search_death_screen": "search",
    "inventory_drop": "inventory_player_drop",
}

IS_DEBUG = False
DEBUG_ITEM = None
DEBUG_GRAY = False
DEBUG_BEEP = False


def register_roi(
    items: dict[RoiRegionKey, RoiRegion],
    l_bound: TBound = default_bounds[0],
    u_bound: TBound = default_bounds[1],
):
    global template_l_bounds_overwrite
    global template_u_bounds_overwrite

    roi_regions.update(items)

    for key in items:
        template_l_bounds_overwrite.update({key: l_bound})
        template_u_bounds_overwrite.update({key: u_bound})


_roi_overwrite = None


@contextmanager
def temporary_overwrite_regions(
    roi: RoiRegion | None = None,
    item: RoiRegionKey | None = None,
):
    """
    Leaving item to None to overwrite all
    """

    global _roi_overwrite

    original_region = None

    if item and roi:
        original_region = roi_regions[item].copy()

        roi_regions[item] = roi

    if roi is not None:
        _roi_overwrite = roi
    try:
        yield
    finally:
        if item and original_region:
            roi_regions[item] = original_region
        _roi_overwrite = None


def get_region_roi(region: RoiRegion):
    return screen.get_screen_roi(
        region["start_x"], region["start_y"], region["width"], region["height"]
    )


def template_await_true(func, sleep_amount: float, *args):
    count = 0
    while not bool(func(*args)):
        if count >= sleep_amount * 20:
            break
        time.sleep(0.05)
        count += 1
    return bool(func(*args))


def template_await_false(func, sleep_amount: float, *args):
    count = 0
    while bool(func(*args)):
        if count >= sleep_amount * 20:
            break
        time.sleep(0.05)
        count += 1
    return bool(func(*args))


def _masked_gray_capture(
    item: RoiRegionKey,
    roi: MatLike,
    lower_boundary=None,
    upper_boundary=None,
):
    lower_boundary = np.array(
        template_l_bounds_overwrite.get(item, default_bounds[0])
        if lower_boundary is None
        else lower_boundary
    )
    upper_boundary = np.array(
        template_u_bounds_overwrite.get(item, default_bounds[1])
        if upper_boundary is None
        else upper_boundary
    )
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask=mask)
    return cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)


def capture_for_compare(item: RoiRegionKey):
    """Capture a masked grayscale ROI for later image-diff comparison.

    Example:
    ```python
    before = capture_compare_region("item_fertilizer")
    ```
    """

    region = roi_regions[item] if _roi_overwrite is None else _roi_overwrite
    return _masked_gray_capture(
        item,
        get_region_roi(region),
        default_no_bounds[0],
        default_no_bounds[1],
    )


def compare_captures(
    before: np.ndarray,
    after: np.ndarray,
):
    """Return a normalized image-diff score or threshold comparison.

    Bigger score = more different. Score < 0.02 = not much changed

    Example:
    ```python
    score = compare_captures(before, after)
    changed = compare_captures(before, after, 0.05)
    ```
    """

    if before.shape != after.shape:
        raise ValueError("Capture images must have the same shape.")
    diff = cv2.absdiff(before, after)
    score = float(np.mean(diff) / 255.0)
    return score


def capture_compare_changed(item: RoiRegionKey, before: MatLike, threshold=0.02):
    """Capture an item ROI and report whether it still in a threshold.

    Example:
    ```python
    changed = capture_compare_changed("item_fertilizer", before)
    -> True if changed

    changed = capture_compare_changed("item_fertilizer", before, 0.05)
    -> True if the % changing is more than 0.05
    ```
    """

    after = capture_for_compare(item)
    score = compare_captures(before, after)
    logs.logger.template(f"{item} diff score:{score} threshold:{threshold}")
    return compare_captures(before, after) > threshold


def reset_debug_folder():
    from pathlib import Path

    debug_folder = Path.cwd() / "debug_template"

    if not debug_folder.exists():
        return

    for file_path in debug_folder.iterdir():
        if file_path.is_file():
            file_path.unlink()


_preloads: dict[RoiRegionKey, MatLike] = {}


def templates_preload(items: list[RoiRegionKey]):
    global _preloads
    for item in items:
        l_bound = template_l_bounds_overwrite.get(item, default_bounds[0])
        u_bound = template_u_bounds_overwrite.get(item, default_bounds[1])

        # Playground https://pseudopencv.site/utilities/hsvcolormask/
        lower_boundary = np.array(l_bound)
        upper_boundary = np.array(u_bound)

        image_path = template_image_overwrite.get(item, item)
        image = cv2.imread(f"assets/icons1080/{image_path}.png")
        if image is None:
            raise FileNotFoundError(
                f"Image assets/icons1080/{image_path}.png not found"
            )
        image = _masked_gray_capture(item, image, lower_boundary, upper_boundary)
        _preloads[item] = image


def check_templates(base: RoiRegionKey, items: list[RoiRegionKey], threshold: float):
    l_bound = template_l_bounds_overwrite.get(base, default_bounds[0])
    u_bound = template_u_bounds_overwrite.get(base, default_bounds[1])
    lower_boundary = np.array(l_bound)
    upper_boundary = np.array(u_bound)

    region = roi_regions[base] if _roi_overwrite is None else _roi_overwrite
    roi = get_region_roi(region)
    gray_roi = _masked_gray_capture(base, roi, lower_boundary, upper_boundary)

    for item in items:
        if item in _preloads:
            image = _preloads[item]
        else:
            l_bound = template_l_bounds_overwrite.get(item, default_bounds[0])
            u_bound = template_u_bounds_overwrite.get(item, default_bounds[1])

            # Playground https://pseudopencv.site/utilities/hsvcolormask/
            lower_boundary = np.array(l_bound)
            upper_boundary = np.array(u_bound)

            image_path = template_image_overwrite.get(item, item)
            image = cv2.imread(f"assets/icons1080/{image_path}.png")
            if image is None:
                raise FileNotFoundError(
                    f"Image assets/icons1080/{image_path}.png not found"
                )
            image = _masked_gray_capture(item, image, lower_boundary, upper_boundary)
        res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        # DEBUG
        if IS_DEBUG and (
            DEBUG_ITEM is None
            or item == DEBUG_ITEM
            or (isinstance(DEBUG_ITEM, list) and item in DEBUG_ITEM)
        ):
            import winsound
            from pathlib import Path

            score = f"{max_val:.3f}"

            debug_roi = gray_roi.copy() if DEBUG_GRAY else roi.copy()
            cv2.rectangle(
                debug_roi,
                (max_loc[0], max_loc[1]),
                (max_loc[0] + image.shape[1], max_loc[1] + image.shape[0]),
                (0, 0, 255),
                2,
            )

            root_path = Path.cwd()
            dir_folder = root_path / "debug_template"
            dir_folder.mkdir(parents=True, exist_ok=True)

            template_path = dir_folder / f"{item}_template.png"
            roi_path = dir_folder / f"{item}_{score}_roi.png"

            if not template_path.exists():
                cv2.imwrite(str(template_path), image)
            if not roi_path.exists():
                cv2.imwrite(str(roi_path), debug_roi)

            if DEBUG_BEEP:
                if max_val > threshold:
                    winsound.Beep(frequency=1000, duration=50)
                else:
                    winsound.Beep(400, 200)

        if max_val > threshold:
            return item

    return None


def check_template(item: RoiRegionKey, threshold: float):
    global default_bounds
    region = roi_regions[item] if _roi_overwrite is None else _roi_overwrite
    roi = get_region_roi(region)

    l_bound = template_l_bounds_overwrite.get(item, default_bounds[0])
    u_bound = template_u_bounds_overwrite.get(item, default_bounds[1])

    # Playground https://pseudopencv.site/utilities/hsvcolormask/
    lower_boundary = np.array(l_bound)
    upper_boundary = np.array(u_bound)

    gray_roi = _masked_gray_capture(item, roi, lower_boundary, upper_boundary)

    image_path = template_image_overwrite.get(item, item)
    image = cv2.imread(f"assets/icons1080/{image_path}.png")
    if image is None:
        raise FileNotFoundError(f"Image assets/icons1080/{image_path}.png not found")

    image = _masked_gray_capture(item, image, lower_boundary, upper_boundary)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    # DEBUG
    if IS_DEBUG and (
        DEBUG_ITEM is None
        or item == DEBUG_ITEM
        or (isinstance(DEBUG_ITEM, list) and item in DEBUG_ITEM)
    ):
        import winsound
        from pathlib import Path

        score = f"{max_val:.3f}"

        debug_roi = gray_roi.copy() if DEBUG_GRAY else roi.copy()
        cv2.rectangle(
            debug_roi,
            (max_loc[0], max_loc[1]),
            (max_loc[0] + image.shape[1], max_loc[1] + image.shape[0]),
            (0, 0, 255),
            2,
        )

        root_path = Path.cwd()
        dir_folder = root_path / "debug_template"
        dir_folder.mkdir(parents=True, exist_ok=True)

        template_path = dir_folder / f"{item}_template.png"
        roi_path = dir_folder / f"{item}_{score}_roi.png"

        if not template_path.exists():
            cv2.imwrite(str(template_path), image)

        if not roi_path.exists():
            cv2.imwrite(str(roi_path), debug_roi)

        if DEBUG_BEEP:
            if max_val > threshold:
                winsound.Beep(1000, 100)
            else:
                winsound.Beep(400, 200)

    if max_val > threshold:
        logs.logger.template(f"{item} found:{max_val}")

        template_h, template_w = image.shape[:2]
        center_x = int(region["start_x"] + max_loc[0] + template_w // 2)
        center_y = int(region["start_y"] + max_loc[1] + template_h // 2)
        return center_x, center_y
    logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return False


def check_template_no_bounds(item: RoiRegionKey, threshold: float):
    region = roi_regions[item] if _roi_overwrite is None else _roi_overwrite
    roi = get_region_roi(region)

    # Playground https://pseudopencv.site/utilities/hsvcolormask/
    lower_boundary = np.array(default_no_bounds[0])
    upper_boundary = np.array(default_no_bounds[1])

    gray_roi = _masked_gray_capture(item, roi, lower_boundary, upper_boundary)

    image_path = template_image_overwrite.get(item, item)
    image = cv2.imread(f"assets/icons1080/{image_path}.png")
    if image is None:
        raise RuntimeError(f"Image assets/icons1080/{image_path}.png not found")
    image = _masked_gray_capture(item, image, lower_boundary, upper_boundary)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    # DEBUG
    if IS_DEBUG and (DEBUG_ITEM is None or item == DEBUG_ITEM or item in DEBUG_ITEM):
        import winsound
        from pathlib import Path

        score = f"{max_val:.3f}"

        debug_roi = gray_roi.copy() if DEBUG_GRAY else roi.copy()
        cv2.rectangle(
            debug_roi,
            (max_loc[0], max_loc[1]),
            (max_loc[0] + image.shape[1], max_loc[1] + image.shape[0]),
            (0, 0, 255),
            2,
        )

        root_path = Path.cwd()
        dir_folder = root_path / "debug_template"
        dir_folder.mkdir(parents=True, exist_ok=True)

        template_path = dir_folder / f"{item}_template.png"
        roi_path = dir_folder / f"{item}_{score}_roi.png"

        if not template_path.exists():
            cv2.imwrite(str(template_path), image)
        if not roi_path.exists():
            cv2.imwrite(str(roi_path), debug_roi)

        if DEBUG_BEEP:
            if max_val > threshold:
                winsound.Beep(1000, 50)
            else:
                winsound.Beep(400, 200)

    if max_val > threshold:
        logs.logger.template(f"{item} found:{max_val}")

        template_h, template_w = image.shape[:2]
        center_x = int(region["start_x"] + max_loc[0] + template_w // 2)
        center_y = int(region["start_y"] + max_loc[1] + template_h // 2)
        return center_x, center_y
    logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return False


# def return_location(
#     item: str, threshold: float
# ):  # assumes that the check for the item on the screen has already been done
#     region = roi_regions[item]
#     roi = get_region_roi(region)

#     lower_boundary = np.array([0, 0, 0])
#     upper_boundary = np.array([255, 255, 255])

#     hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
#     mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
#     masked_template = cv2.bitwise_and(roi, roi, mask=mask)
#     gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

#     image = cv2.imread(f"assets/icons1080/{item}.png")
#     hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
#     mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
#     masked_template = cv2.bitwise_and(image, image, mask=mask)
#     image = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

#     res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
#     min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

#     if max_val > threshold:
#         logs.logger.template(f"{item} found:{max_val} at:{max_loc}")
#         return max_loc
#     logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
#     return 0


# def teleport_icon(threshold: float) -> bool:
#     region = roi_regions["teleporter_icon"]
#     roi = get_region_roi(region)

#     lower_boundary = np.array([0, 0, 150])
#     upper_boundary = np.array([255, 255, 255])

#     hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
#     mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
#     masked_template = cv2.bitwise_and(roi, roi, mask=mask)
#     gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

#     image = cv2.imread("assets/icons1080/teleporter_icon.png")
#     hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
#     mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
#     masked_template = cv2.bitwise_and(image, image, mask=mask)
#     image = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

#     res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
#     min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

#     if max_val > threshold:
#         logs.logger.template(f"teleporter_icon found:{max_val}")
#         return True
#     logs.logger.template(f"teleporter_icon not found:{max_val} threshold:{threshold}")
#     return False


# def inventory_first_slot(item: str, threshold: float) -> bool:
#     region = roi_regions["first_slot"]
#     roi = get_region_roi(region)

#     lower_boundary = np.array([0, 0, 0])
#     upper_boundary = np.array([255, 255, 255])

#     hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
#     mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
#     masked_template = cv2.bitwise_and(roi, roi, mask=mask)
#     gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

#     image = cv2.imread(f"assets/icons1080/{item}.png")
#     hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
#     mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
#     masked_template = cv2.bitwise_and(image, image, mask=mask)
#     image = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

#     res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
#     min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

#     if max_val > threshold:
#         logs.logger.template(f"{item} found:{max_val}")
#         return True
#     logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
#     return False


def check_buffs(buff, threshold):
    region = roi_regions["player_stats"]
    roi = get_region_roi(region)

    lower_boundary = np.array([0, 0, 180])
    upper_boundary = np.array([255, 255, 255])

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"assets/icons1080/{buff}.png")
    if image is None:
        raise FileNotFoundError(
            f"Template image not found: assets/icons1080/{buff}.png"
        )

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    image = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val > threshold:
        logs.logger.template(f"{buff} found:{max_val}")
        return True
    logs.logger.template(f"{buff} not found:{max_val} threshold:{threshold}")
    return False


def check_teleporter_orange():
    region = roi_regions["orange"]
    roi = get_region_roi(region)

    lower_boundary = np.array([10, 211, 50])
    upper_boundary = np.array([15, 255, 100])

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    pixel_hsv = hsv[0, 0]
    logs.logger.template(
        f"check orange {np.all(pixel_hsv >= lower_boundary) and np.all(pixel_hsv <= upper_boundary)}"
    )
    return bool(
        np.all(pixel_hsv >= lower_boundary) and np.all(pixel_hsv <= upper_boundary)
    )


def check_transfer_server_orange():
    region = roi_regions["transfer_orange"]
    roi = get_region_roi(region)

    lower_boundary = np.array([10, 211, 50])
    upper_boundary = np.array([15, 255, 100])

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    pixel_hsv = hsv[0, 0]
    logs.logger.template(
        f"check orange {np.all(pixel_hsv >= lower_boundary) and np.all(pixel_hsv <= upper_boundary)}"
    )
    return np.all(pixel_hsv >= lower_boundary) and np.all(pixel_hsv <= upper_boundary)


def white_flash():
    roi = screen.get_screen_roi(500, 500, 100, 100)
    total_pixels = roi.size
    num_255_pixels = np.count_nonzero(roi == 255)
    percentage_255 = (num_255_pixels / total_pixels) * 100
    logs.logger.template(f"white flash {percentage_255 >= 80}")
    return percentage_255 >= 80


def get_file():
    file_path = "json_files/console.json"
    try:
        with open(file_path, "r") as file:
            data = file.read().strip()
            if not data:
                return []
            return json.loads(data)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def get_bounds():
    bounds = get_file()
    return bounds


def set_bounds(lower_bound: int, upper_bound: int):
    file_path = "json_files/console.json"
    new_bounds = [{"upper_bound": upper_bound, "lower_bound": lower_bound}]

    with open(file_path, "w") as file:
        json.dump(new_bounds, file, indent=4)


bounds = get_bounds()
upper_console_bound = bounds[0]["upper_bound"]
lower_console_bound = bounds[0]["lower_bound"]


def console_strip_bottom():
    return screen.get_screen_roi(0, 1059, 1920, 2)


def console_strip_middle():
    return screen.get_screen_roi(0, 795, 1920, 2)


def console_strip_check(roi):
    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray_mask = (gray_roi >= lower_console_bound) & (gray_roi <= upper_console_bound)
    num_gray_pixels = np.count_nonzero(gray_mask)

    total_pixels = gray_roi.size
    percentage_gray = (num_gray_pixels / total_pixels) * 100
    logs.logger.template(f"percentage gray {percentage_gray}")
    return percentage_gray >= 80


def check_both_strips():
    roi1 = console_strip_bottom()
    roi2 = console_strip_middle()
    return console_strip_check(roi1) or console_strip_check(roi2)


if __name__ == "__main__":
    time.sleep(2)
    # change_console_mask()
    time.sleep(0.5)
    pass
