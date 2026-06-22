import time
from collections.abc import Callable

import settings
from source.ASA import config as asa_config
from source.ASA.player import player_inventory
from source.ASA.strucutres import inventory
from source.logs import gachalogs as logs
from source.utility import template

POLL_INTERVAL = 0.02


def _open_crop_plot_inventory() -> None:
    attempts = 0
    while not template.check_template("inventory", 0.7):
        attempts += 1
        logs.logger.debug(
            f"trying to open crop plot inventory {attempts} / "
            f"{asa_config.inventory_open_attempts}"
        )
        inventory.open()
        if inventory.is_open():
            break
        if attempts >= asa_config.inventory_open_attempts:
            logs.logger.error("unable to open up the crop plot inventory")
            break
        time.sleep(0.3 * settings.lag_offset)


def _close_crop_plot_inventory() -> None:
    attempts = 0
    while template.check_template("inventory", 0.7):
        attempts += 1
        logs.logger.debug(
            f"trying to close crop plot inventory {attempts} / "
            f"{asa_config.inventory_close_attempts}"
        )
        inventory.close()
        if attempts >= asa_config.inventory_close_attempts:
            logs.logger.error(
                f"unable to close the crop plot inventory after {attempts} attempts"
            )
            break


def run_fertilizer_refresh(
    status_callback: Callable[[str], object] | None = None,
) -> None:
    def set_status(message: str) -> None:
        if status_callback is not None:
            status_callback(message)

    def wait_for_prompt_to_clear() -> None:
        set_status("Aim away from the crop plot to continue...")
        while template.check_template_no_bounds("crop_plot_prompt", 0.9):
            time.sleep(POLL_INTERVAL)

    while True:
        set_status("Aim at a crop plot to refresh fertilizer...")
        while True:
            if template.check_template("crop_plot", 0.7):
                break
            if template.check_template_no_bounds("crop_plot_prompt", 0.9):
                set_status("Opening crop plot inventory...")
                _open_crop_plot_inventory()
                if template.check_template("crop_plot", 0.7):
                    break
                if inventory.is_open():
                    _close_crop_plot_inventory()
                set_status("Crop plot did not open. Aim away and try again.")
                wait_for_prompt_to_clear()
                set_status("Aim at a crop plot to refresh fertilizer...")
                continue
            time.sleep(POLL_INTERVAL)

        set_status("Refreshing fertilizer...")
        inventory.transfer_all_from()
        player_inventory.transfer_all_inventory()

        set_status("Closing crop plot inventory...")
        _close_crop_plot_inventory()
        wait_for_prompt_to_clear()
