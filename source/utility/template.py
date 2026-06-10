import json
import time

import cv2
import numpy as np

from source.logs import gachalogs as logs
from source.utility import screen

roi_regions = {
    "bed_radical": {"start_x": 840, "start_y": 258, "width": 188, "height": 188},
    "beds_title": {"start_x": 75, "start_y": 75, "width": 555, "height": 135},
    "console": {"start_x": 0, "start_y": 1050, "width": 38, "height": 30},
    "crop_plot": {"start_x": 825, "start_y": 187, "width": 233, "height": 113},
    "crop_plot_prompt": {"start_x": 300, "start_y": 150, "width": 1400, "height": 800},
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
    "tek_trough": {"start_x": 877, "start_y": 195, "width": 161, "height": 30},
    "exit_resume": {"start_x": 412, "start_y": 337, "width": 1253, "height": 660},
    "inventory": {"start_x": 150, "start_y": 93, "width": 270, "height": 113},
    "ready_clicked_bed": {"start_x": 435, "start_y": 187, "width": 113, "height": 750},
    "seed_inv": {"start_x": 412, "start_y": 337, "width": 1253, "height": 660},
    "slot_capped": {"start_x": 1680, "start_y": 985, "width": 113, "height": 75},
    "teleporter_title": {"start_x": 150, "start_y": 101, "width": 304, "height": 139},
    "tribelog_check": {"start_x": 862, "start_y": 26, "width": 113, "height": 113},
    "waiting_inv": {"start_x": 1500, "start_y": 75, "width": 375, "height": 188},
    "bed_icon": {"start_x": 600, "start_y": 150, "width": 1268, "height": 825},
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
    "snow_owl_pellet": {"start_x": 150, "start_y": 112, "width": 450, "height": 450},
    "orange": {"start_x": 528, "start_y": 217, "width": 1, "height": 1},
    "chem_bench": {"start_x": 825, "start_y": 183, "width": 267, "height": 53},
    "indi_forge": {"start_x": 825, "start_y": 183, "width": 267, "height": 53},
    "access_inv": {"start_x": 412, "start_y": 337, "width": 1253, "height": 660},
    "turn_off": {"start_x": 900, "start_y": 870, "width": 150, "height": 30},
    "vault_full": {"start_x": 1065, "start_y": 525, "width": 113, "height": 30},
    "search": {"start_x": 337, "start_y": 952, "width": 90, "height": 30},
    "server_list_trans_loaded": {
        "start_x": 140,
        "start_y": 280,
        "width": 70,
        "height": 160,
    },
    "server_trans_success": {"start_x": 765, "start_y": 0, "width": 382, "height": 60},
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
}


def get_region_roi(region):
    return screen.get_screen_roi(
        region["start_x"], region["start_y"], region["width"], region["height"]
    )


def template_await_true(func, sleep_amount: float, *args) -> bool:
    count = 0
    while func(*args) == False:
        if count >= sleep_amount * 20:
            break
        time.sleep(0.05)
        count += 1
    return func(*args)


def template_await_false(func, sleep_amount: float, *args) -> bool:
    count = 0
    while func(*args) == True:
        if count >= sleep_amount * 20:
            break
        time.sleep(0.05)
        count += 1
    return func(*args)


def check_template(item: str, threshold: float) -> bool:
    region = roi_regions[item]
    roi = get_region_roi(region)

    lower_boundary = np.array([0, 30, 200])
    upper_boundary = np.array([255, 255, 255])

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"assets/icons1080/{item}.png")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    image = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    # if item == "crop_plot_prompt":
    #     print(f"Max value: {max_val}, Threshold: {threshold}")
    #     cv2.imshow("template", image)
    #     cv2.rectangle(
    #         roi,
    #         (max_loc[0], max_loc[1]),
    #         (max_loc[0] + image.shape[1], max_loc[1] + image.shape[0]),
    #         (0, 0, 255),
    #         2,
    #     )
    #     cv2.imshow("roi_with_rectangle", gray_roi)
    #     cv2.waitKey(0)
    #     cv2.destroyAllWindows()

    if max_val > threshold:
        logs.logger.template(f"{item} found:{max_val}")
        return True
    logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return False


def check_template_no_bounds(item: str, threshold: float) -> bool:
    region = roi_regions[item]
    roi = get_region_roi(region)

    lower_boundary = np.array([0, 0, 0])
    upper_boundary = np.array([255, 255, 255])

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"assets/icons1080/{item}.png")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    image = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    # if item == "crop_plot_prompt":
    #     print(f"Max value: {max_val}, Threshold: {threshold}")
    #     cv2.imshow("template", image)
    #     cv2.rectangle(
    #         roi,
    #         (max_loc[0], max_loc[1]),
    #         (max_loc[0] + image.shape[1], max_loc[1] + image.shape[0]),
    #         (0, 0, 255),
    #         2,
    #     )
    #     cv2.imshow("roi_with_rectangle", gray_roi)
    #     cv2.waitKey(0)
    #     cv2.destroyAllWindows()

    if max_val > threshold:
        logs.logger.template(f"{item} found:{max_val}")
        return True
    logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return False


def return_location(
    item: str, threshold: float
):  # assumes that the check for the item on the screen has already been done
    region = roi_regions[item]
    roi = get_region_roi(region)

    lower_boundary = np.array([0, 0, 0])
    upper_boundary = np.array([255, 255, 255])

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"assets/icons1080/{item}.png")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    image = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val > threshold:
        logs.logger.template(f"{item} found:{max_val} at:{max_loc}")
        return max_loc
    logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return 0


def teleport_icon(threshold: float) -> bool:
    region = roi_regions["teleporter_icon"]
    roi = get_region_roi(region)

    lower_boundary = np.array([0, 0, 150])
    upper_boundary = np.array([255, 255, 255])

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    image = cv2.imread("assets/icons1080/teleporter_icon.png")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    image = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val > threshold:
        logs.logger.template(f"teleporter_icon found:{max_val}")
        return True
    logs.logger.template(f"teleporter_icon not found:{max_val} threshold:{threshold}")
    return False


def inventory_first_slot(item: str, threshold: float) -> bool:
    region = roi_regions["first_slot"]
    roi = get_region_roi(region)

    lower_boundary = np.array([0, 0, 0])
    upper_boundary = np.array([255, 255, 255])

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"assets/icons1080/{item}.png")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    image = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val > threshold:
        logs.logger.template(f"{item} found:{max_val}")
        return True
    logs.logger.template(f"{item} not found:{max_val} threshold:{threshold}")
    return False


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
    except (json.JSONDecodeError, FileNotFoundError) as e:
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
