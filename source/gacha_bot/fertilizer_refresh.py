def run_fertilizer_refresh(
    stop_event,
    status_callback=None,
    poll_interval=0.1,
    crop_plot_is_open=None,
    inventory_is_open=None,
    transfer_all_from=None,
    transfer_all_inventory=None,
):
    if crop_plot_is_open is None:
        from source.utility import template

        crop_plot_is_open = lambda: template.check_template("crop_plot", 0.7)
    if inventory_is_open is None or transfer_all_from is None:
        from source.ASA.strucutres import inventory

        inventory_is_open = inventory_is_open or inventory.is_open
        transfer_all_from = transfer_all_from or inventory.transfer_all_from
    if transfer_all_inventory is None:
        from source.ASA.player import player_inventory

        transfer_all_inventory = player_inventory.transfer_all_inventory

    def set_status(message):
        if status_callback is not None:
            status_callback(message)

    while not stop_event.is_set():
        set_status("Waiting for a crop plot inventory...")
        while not stop_event.is_set() and not crop_plot_is_open():
            stop_event.wait(poll_interval)
        if stop_event.is_set():
            break

        set_status("Refreshing fertilizer...")
        transfer_all_from()
        if stop_event.is_set():
            break
        transfer_all_inventory()

        set_status("Waiting for the inventory to close...")
        while not stop_event.is_set() and inventory_is_open():
            stop_event.wait(poll_interval)

    set_status("Stopped.")
