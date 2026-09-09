import time

import source.ASA.config
from source.ASA.player import player_inventory, player_state, tribelog
from source.ASA.strucutres import teleporter
from source.gacha_bot import render
from source.logs import gachalogs as logs
from source.utility import (
    ark_input,
    local_player,
    template,
    utils,
    utils_simple,
    variables,
    windows,
)


def is_clear_search_death_screen():
    return template.check_template_no_bounds("search_death_screen", 0.7)


def is_open_respawn():
    # if teleporter is open then we are not in the bed spawn screen
    return (
        template.check_template("beds_title_respawn", 0.7) and not teleporter.is_open()
    )


def is_open():
    # bed title is found in both death and fast travel screens and server transfer spawn screen
    return (
        (
            template.check_template("beds_title", 0.7)
            or template.check_template("beds_title_respawn", 0.7)
        )
        and not teleporter.is_open()
    )  # if teleporter is open then we are not in the bed spawn screen


def is_dead():
    return template.check_template("death_regions", 0.7)


def close():
    attempts = 0
    while is_open():
        attempts += 1
        logs.logger.debug(
            f"trying to close the bed {attempts} / {source.ASA.config.teleporter_close_attempts}"
        )
        windows.click(
            variables.get_pixel_loc("back_button_tp_x"),
            variables.get_pixel_loc("back_button_tp_y"),
        )
        if not template.template_await_false(is_open, 2):
            return time.sleep(0.3)

        if attempts >= source.ASA.config.teleporter_close_attempts:
            logs.logger.error(
                f"unable to close the bed after {source.ASA.config.teleporter_close_attempts} attempts"
            )
            break


def spawn_in(bed_name: str):
    """
    When it's done, player should be ready to perform next action
    Careful, this one also auto trigger IMPLANT EAT/SUICIDE
    """

    dl = utils_simple.get_default_clock()
    while not is_open() and not dl():
        player_inventory.implant_eat()

        if is_open():
            break

        player_state.check_disconnected()
        time.sleep(1)

    if is_open():
        while True:
            # Make sure we are still in the bed screen, not from the teleporter screen
            # Because ARK is very lagging and will display the bed title first then update to the teleporter title
            if not is_open():
                # Close teleport screen
                player_state.check_state()
                return

            player_state.check_disconnected()

            state = "death screen" if is_dead() else "fast travel screen"
            logs.logger.debug(f"char is in the {state}")

            search_bar_x = variables.get_pixel_loc(
                "search_bar_bed_dead_x" if is_dead() else "search_bar_bed_alive_x"
            )
            windows.click(
                search_bar_x, variables.get_pixel_loc("search_bar_bed_y")
            )  # search bar y axis is the same for both death/alive

            utils.ctrl_a()  # CTRL A removes all previous data in the search bar
            utils.write(bed_name)

            time.sleep(0.2)
            windows.click(
                variables.get_pixel_loc("first_bed_slot_x"),
                variables.get_pixel_loc("first_bed_slot_y"),
            )
            if (
                template.template_await_true(template.check_teleporter_orange, 3)
                and not is_clear_search_death_screen()
            ):
                break

        if not template.template_await_true(
            template.check_teleporter_orange, 3
        ):  # waiting for the bed to appear as ready to spawn in
            logs.logger.error(
                "the bed char tried spawning on is not in the ready state or cant be found exiting out of bed screen now"
            )
            close()
            return  # no need to continue with this therefore we should just leave func

        windows.click(
            variables.get_pixel_loc("spawn_button_x"),
            variables.get_pixel_loc("spawn_button_y"),
        )
        time.sleep(0.2)

        # Click random on the screen to make sure it will spawn player or skip trailers.

        locs = ((1000, 300), (1400, 800))
        for loc in locs:
            ark_input.move_to(*loc, duration=0.5)
            ark_input.right_click(*loc)
            ark_input.press("space")
            time.sleep(0.2)

        t = 2 if not player_state.uploaded else 15
        dl = utils_simple.get_default_clock(deadline=t)
        while not dl():
            if template.template_await_true(template.white_flash, 0.5):
                logs.logger.debug(
                    f"white flash detected waiting for up too {t} seconds"
                )
                template.template_await_false(template.white_flash, t)
                break
            else:
                tribelog.open(1)
                if tribelog.is_open():
                    break

            # tribelog.open(1)
            # if tribelog.is_open():
            #     break
        dl = utils_simple.get_default_clock(deadline=10)
        while not tribelog.is_open():
            if dl():
                break
            # animation spawn in is about 7 seconds
            tribelog.open()

        time.sleep(3)

        tribelog.open()
        tribelog.close()


def fast_travel(bed_name: str):

    if not player_state.human.on_bed:
        # need to go to render bed if on tp
        if player_state.human.on_tp:
            logs.logger.debug(
                "char is on a teleporter going to render bed to fast travel"
            )
            render.fast_travel_to_render()
            time.sleep(0.2)
            utils.zero_center()
            utils.turn_down(15)
    else:
        time.sleep(0.2)
        utils.turn_down(80)
    time.sleep(0.2)
    utils.press_key(local_player.get_input_settings("Use"))

    # some reason takes ages to open up the fast travel screen
    template.template_await_true(is_open, 2)
    time.sleep(0.2)
    if is_open():
        state = "death screen" if is_dead() else "fast travel screen"
        logs.logger.debug(f"char is in the {state}")
        search_bar_x = variables.get_pixel_loc(
            "search_bar_bed_dead_x" if is_dead() else "search_bar_bed_alive_x"
        )
        windows.click(
            search_bar_x, variables.get_pixel_loc("search_bar_bed_y")
        )  # search bar y axis is the same for both death/alive
        utils.ctrl_a()  # CTRL A removes all previous data in the search bar
        utils.write(bed_name)
        time.sleep(0.2)
        windows.click(
            variables.get_pixel_loc("first_bed_slot_x"),
            variables.get_pixel_loc("first_bed_slot_y"),
        )

        if not template.template_await_true(
            template.check_teleporter_orange, 3
        ):  # waiting for the bed to appear as ready to spawn in
            logs.logger.error(
                "the bed char tried spawning on is not in the ready state or cant be found exiting out of bed screen now"
            )
            close()
            return  # no need to continue with this therefore we should just leave func

        windows.click(
            variables.get_pixel_loc("spawn_button_x"),
            variables.get_pixel_loc("spawn_button_y"),
        )

        if template.template_await_true(template.white_flash, 2):
            logs.logger.debug("white flash detected waiting for up too 5 seconds")
            template.template_await_false(template.white_flash, 5)

        player_state.human.is_on_bed()
        time.sleep(2)  # spawn in animation is shorter than spawning in

        tribelog.open()
        tribelog.close()
