import time


def _template_await_true(stop_event, func, sleep_amount, *args):
    count = 0
    while not stop_event.is_set() and not func(*args):
        if count >= sleep_amount * 20:
            break
        stop_event.wait(0.05)
        count += 1
    return not stop_event.is_set() and func(*args)


def _template_await_false(stop_event, func, sleep_amount, *args):
    count = 0
    while not stop_event.is_set() and func(*args):
        if count >= sleep_amount * 20:
            break
        stop_event.wait(0.05)
        count += 1
    return stop_event.is_set() or func(*args)


def _open_crop_plot_inventory(stop_event):
    import settings
    import source.ASA.config
    from source.logs import gachalogs as logs
    from source.utility import template, utils

    attempts = 0
    while not stop_event.is_set() and not template.check_template("inventory", 0.7):
        attempts += 1
        logs.logger.debug(
            f"trying to open crop plot inventory {attempts} / "
            f"{source.ASA.config.inventory_open_attempts}"
        )
        utils.press_key("AccessInventory")
        if _template_await_true(
            stop_event, template.check_template, 2, "inventory", 0.7
        ):
            logs.logger.debug("crop plot inventory opened")
            if _template_await_true(
                stop_event, template.check_template, 1, "waiting_inv", 0.8
            ):
                start = time.time()
                logs.logger.debug(
                    "waiting for up too 10 seconds due to the reciving remote "
                    "inventory is present"
                )
                _template_await_false(
                    stop_event, template.check_template, 10, "waiting_inv", 0.8
                )
                logs.logger.debug(
                    f"{time.time() - start} seconds taken for the reciving remote "
                    "inventory to go away"
                )
                break
        if attempts >= source.ASA.config.inventory_open_attempts:
            logs.logger.error("unable to open up the crop plot inventory")
            break
    stop_event.wait(0.3 * settings.lag_offset)


def _close_crop_plot_inventory(stop_event):
    import settings
    import source.ASA.config
    from source.logs import gachalogs as logs
    from source.utility import template, variables, windows

    attempts = 0
    while not stop_event.is_set() and template.check_template("inventory", 0.7):
        attempts += 1
        logs.logger.debug(
            f"trying to close crop plot inventory {attempts} / "
            f"{source.ASA.config.inventory_close_attempts}"
        )
        windows.click(
            variables.get_pixel_loc("close_inv_x"),
            variables.get_pixel_loc("close_inv_y"),
        )
        _template_await_false(stop_event, template.check_template, 2, "inventory", 0.7)
        if attempts >= source.ASA.config.inventory_close_attempts:
            logs.logger.error(
                f"unable to close the crop plot inventory after {attempts} attempts"
            )
            break
    stop_event.wait(0.3 * settings.lag_offset)


def run_fertilizer_refresh(
    stop_event,
    status_callback=None,
    poll_interval=0.1,
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
        open_inventory = open_inventory or (
            lambda: _open_crop_plot_inventory(stop_event)
        )
        close_inventory = close_inventory or (
            lambda: _close_crop_plot_inventory(stop_event)
        )
        transfer_all_from = transfer_all_from or inventory.transfer_all_from
    if transfer_all_inventory is None:
        from source.ASA.player import player_inventory

        transfer_all_inventory = player_inventory.transfer_all_inventory

    def set_status(message):
        if status_callback is not None:
            status_callback(message)

    def wait_for_prompt_to_clear():
        set_status("Aim away from the crop plot to continue...")
        while not stop_event.is_set() and crop_plot_prompt_is_visible():
            stop_event.wait(poll_interval)

    while not stop_event.is_set():
        set_status("Aim at a crop plot to refresh fertilizer...")
        while not stop_event.is_set():
            if crop_plot_is_open():
                break
            if crop_plot_prompt_is_visible():
                set_status("Opening crop plot inventory...")
                open_inventory()
                if stop_event.is_set():
                    break
                if crop_plot_is_open():
                    break
                if inventory_is_open():
                    close_inventory()
                set_status("Crop plot did not open. Aim away and try again.")
                wait_for_prompt_to_clear()
                set_status("Aim at a crop plot to refresh fertilizer...")
                continue
            stop_event.wait(poll_interval)
        if stop_event.is_set():
            break

        set_status("Refreshing fertilizer...")
        transfer_all_from()
        if stop_event.is_set():
            break
        transfer_all_inventory()
        if stop_event.is_set():
            break

        set_status("Closing crop plot inventory...")
        close_inventory()
        if stop_event.is_set():
            break
        wait_for_prompt_to_clear()

    set_status("Stopped.")
