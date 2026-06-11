import time

import cv2
import numpy as np

from source.join_sim.source.logs import logger as logs
from source.utility import screen

location = {
    "accept": {"start_x": 915, "start_y": 718, "width": 75, "height": 23},
    "escape": {"start_x": 1747, "start_y": 82, "width": 45, "height": 38},
    "escape_obscured": {"start_x": 1747, "start_y": 82, "width": 45, "height": 38},
    "join_last_session": {"start_x": 851, "start_y": 937, "width": 225, "height": 38},
    "join_game": {"start_x": 300, "start_y": 750, "width": 525, "height": 45},
    "join_button": {"start_x": 1672, "start_y": 922, "width": 75, "height": 38},
    "multiplayer": {"start_x": 75, "start_y": 82, "width": 64, "height": 45},
    "server_full": {"start_x": 997, "start_y": 345, "width": 188, "height": 45},
    "red_fail": {"start_x": 922, "start_y": 363, "width": 188, "height": 45},
    "mod_join": {"start_x": 1691, "start_y": 918, "width": 75, "height": 45},
    "req_mods": {"start_x": 723, "start_y": 140, "width": 150, "height": 38},
    "join_text": {"start_x": 675, "start_y": 476, "width": 300, "height": 23},
    "loading_screen": {"start_x": 0, "start_y": 0, "width": 375, "height": 375},
    "searching": {"start_x": 870, "start_y": 476, "width": 90, "height": 30},
    "no_session": {"start_x": 945, "start_y": 476, "width": 113, "height": 30},
    "connection_timeout": {"start_x": 768, "start_y": 345, "width": 150, "height": 42},
    "search": {"start_x": 1575, "start_y": 183, "width": 75, "height": 30},
    "download": {"start_x": 431, "start_y": 915, "width": 150, "height": 19},
    "beds_title": {"start_x": 75, "start_y": 75, "width": 555, "height": 135},
    "tribelog_check": {"start_x": 862, "start_y": 26, "width": 113, "height": 113},
    "network_failure": {"start_x": 787, "start_y": 337, "width": 225, "height": 53},
    "is_logging": {"start_x": 65, "start_y": 75, "width": 180, "height": 60},
    "server_list_loaded": {
        "start_x": 90,
        "start_y": 300,
        "width": 40,
        "height": 180,
    },
    "term_and_conditions": {
        "start_x": 567,
        "start_y": 307,
        "width": 784,
        "height": 420,
    },
}


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
    v = func(*args)
    while v == True:
        v = func(*args)
        if count >= sleep_amount * 20:
            break
        time.sleep(0.05)
        count += 1
    return func(*args)


def get_region_roi(region):
    return screen.get_screen_roi(
        region["start_x"], region["start_y"], region["width"], region["height"]
    )


def check_template(item: str, threshold: float) -> bool:

    region = location[item]
    roi = get_region_roi(region)
    lower_boundary = np.array([0, 30, 200])
    upper_boundary = np.array([255, 255, 255])

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"source/join_sim/assets/icons1080/{item}.png")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    image = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    # if item == "is_logging":
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

    region = location[item]
    roi = get_region_roi(region)
    lower_boundary = np.array([0, 0, 0])
    upper_boundary = np.array([255, 255, 255])

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"source/join_sim/assets/icons1080/{item}.png")
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


def template_sleep(template: str, threshold: float, sleep_amount: float) -> bool:
    count = 0
    while check_template(template, threshold) == False:
        if count >= sleep_amount * 10:  #  seconds of sleep
            break
        time.sleep(0.1)
        count += 1
    return check_template(template, threshold)


def template_sleep_no_bounds(
    template: str, threshold: float, sleep_amount: float
) -> bool:
    count = 0
    while check_template_no_bounds(template, threshold) == False:
        if count >= sleep_amount * 10:  #  seconds of sleep
            break
        time.sleep(0.1)
        count += 1
    return check_template_no_bounds(template, threshold)


def window_still_open(
    template: str, threshold: float, sleep_amount: float
) -> bool:  # oposite of the function above mainly to check if inventory is still open
    count = 0
    while check_template(template, threshold) == True:
        if count >= sleep_amount * 10:  #  seconds of sleep
            break
        time.sleep(0.1)
        count += 1
    return check_template(template, threshold)


def window_still_open_no_bounds(
    template: str, threshold: float, sleep_amount: float
) -> bool:  # oposite of the function above mainly to check if inventory is still open
    count = 0
    while check_template_no_bounds(template, threshold) == True:
        if count >= sleep_amount * 10:  #  seconds of sleep
            break
        time.sleep(0.1)
        count += 1
    return check_template_no_bounds(template, threshold)


def template_find(
    item: str,
) -> tuple:

    region = location[item]
    roi = get_region_roi(region)

    lower_boundary = np.array([0, 0, 0])
    upper_boundary = np.array([255, 255, 255])

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(roi, roi, mask=mask)
    gray_roi = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    image = cv2.imread(f"source/join_sim/assets/icons1080/{item}.png")
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, lower_boundary, upper_boundary)
    masked_template = cv2.bitwise_and(image, image, mask=mask)
    image = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)

    res = cv2.matchTemplate(gray_roi, image, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    height = image.shape[0]
    width = image.shape[1]

    start_point = (region["start_x"] + max_loc[0], region["start_y"] + max_loc[1])
    mid_point = (start_point[0] + width // 2, start_point[1] + height // 2)

    return mid_point
