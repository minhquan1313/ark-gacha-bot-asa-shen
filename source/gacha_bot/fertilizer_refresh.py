import time


def _open_crop_plot_inventory():
    import settings
    import source.ASA.config
    from source.ASA.strucutres import inventory
    from source.logs import gachalogs as logs
    from source.utility import template

    attempts = 0
    while not template.check_template("inventory", 0.7):
        attempts += 1
        logs.logger.debug(
            f"trying to open crop plot inventory {attempts} / "
            f"{source.ASA.config.inventory_open_attempts}"
        )
        inventory.open()
        if inventory.is_open():
            break
        if attempts >= source.ASA.config.inventory_open_attempts:
            logs.logger.error("unable to open up the crop plot inventory")
            break
    time.sleep(0.3 * settings.lag_offset)


def _close_crop_plot_inventory():
    import settings
    import source.ASA.config
    from source.logs import gachalogs as logs
    from source.utility import template, variables, windows

    attempts = 0
    while template.check_template("inventory", 0.7):
        attempts += 1
        logs.logger.debug(
            f"trying to close crop plot inventory {attempts} / "
            f"{source.ASA.config.inventory_close_attempts}"
        )
        windows.click(
            variables.get_pixel_loc("close_inv_x"),
            variables.get_pixel_loc("close_inv_y"),
        )
        template.template_await_false(template.check_template, 2, "inventory", 0.7)
        if attempts >= source.ASA.config.inventory_close_attempts:
            logs.logger.error(
                f"unable to close the crop plot inventory after {attempts} attempts"
            )
            break
    time.sleep(0.3 * settings.lag_offset)


def run_fertilizer_refresh(
    status_callback=None,
    poll_interval=0.02,
    crop_plot_is_open=None,
    crop_plot_prompt_is_visible=None,
    inventory_is_open=None,
    open_inventory=None,
    close_inventory=None,
    transfer_all_from=None,
    transfer_all_inventory=None,
):
    if crop_plot_is_open is None or crop_plot_prompt_is_visible is None:
        from source.utility import template

        crop_plot_is_open = crop_plot_is_open or (
            lambda: template.check_template("crop_plot", 0.7)
        )
        crop_plot_prompt_is_visible = crop_plot_prompt_is_visible or (
            lambda: template.check_template_no_bounds("crop_plot_prompt", 0.9)
        )
    if (
        inventory_is_open is None
        or open_inventory is None
        or close_inventory is None
        or transfer_all_from is None
    ):
        from source.ASA.strucutres import inventory

        inventory_is_open = inventory_is_open or inventory.is_open
        open_inventory = open_inventory or _open_crop_plot_inventory
        close_inventory = close_inventory or _close_crop_plot_inventory
        transfer_all_from = transfer_all_from or inventory.transfer_all_from
    if transfer_all_inventory is None:
        from source.ASA.player import player_inventory

        transfer_all_inventory = player_inventory.transfer_all_inventory

    def set_status(message):
        if status_callback is not None:
            status_callback(message)

    def wait_for_prompt_to_clear():
        set_status("Aim away from the crop plot to continue...")
        while crop_plot_prompt_is_visible():
            time.sleep(poll_interval)

    while True:
        set_status("Aim at a crop plot to refresh fertilizer...")
        while True:
            if crop_plot_is_open():
                break
            if crop_plot_prompt_is_visible():
                set_status("Opening crop plot inventory...")
                open_inventory()
                if crop_plot_is_open():
                    break
                if inventory_is_open():
                    close_inventory()
                set_status("Crop plot did not open. Aim away and try again.")
                wait_for_prompt_to_clear()
                set_status("Aim at a crop plot to refresh fertilizer...")
                continue
            time.sleep(poll_interval)

        set_status("Refreshing fertilizer...")
        transfer_all_from()
        transfer_all_inventory()

        set_status("Closing crop plot inventory...")
        close_inventory()
        wait_for_prompt_to_clear()
