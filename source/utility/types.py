from typing import Literal, TypeAlias, TypedDict


class ObjectAim(TypedDict):
    yaw: float
    pitch: float


# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=


class DediStorageState(TypedDict):
    location: ObjectAim
    crouched: bool


class DediStorageContainer(TypedDict):
    items: list[DediStorageState]


class VaultStorageState(DediStorageState):
    items: list[str]


class VaultStorageContainer(TypedDict):
    items: list[VaultStorageState]


class GrinderStorageState(DediStorageState):
    active: bool


class DepositRouteBase(TypedDict):
    teleport: str
    check_on_every_dedi: int
    dedi: DediStorageContainer


class CrystalDepositRoute(DepositRouteBase):
    vault: VaultStorageContainer


class GrindableDepositRoute(DepositRouteBase):
    grinder: GrinderStorageState


class DepositConfig(TypedDict):
    depositCrystalData: list[CrystalDepositRoute]
    depositGrindableData: list[GrindableDepositRoute]


# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=


class RoiRegion(TypedDict):
    start_x: int
    start_y: int
    width: int
    height: int


RoiRegionKey: TypeAlias = Literal[
    #
    "bed_radical",
    "beds_title",
    "beds_title_respawn",
    "console",
    "crop_plot",
    "crop_plot_prompt",
    "crystal_in_hotbar",
    "death_regions",
    "dedi",
    "vault",
    "grinder",
    "grinder_grind_button",
    "tek_trough",
    "exit_resume",
    "inventory",
    "inventory_player_drop",
    "inventory_player_transfer_all",
    "seed_inv",
    "slot_capped",
    "teleporter_title",
    "tribelog_check",
    "waiting_inv",
    "teleporter_icon",
    "teleporter_icon_pressed",
    "first_slot",
    "player_stats",
    "show_buff",
    "item_snow_owl_pellet",
    "item_fertilizer",
    "item_fertilizer_fece",
    "orange",
    "transfer_orange",
    "chem_bench",
    "indi_forge",
    "access_inv",
    "search",
    "search_death_screen",
    "search_player_inv",
    "search_object_inv",
    "server_list_trans_loaded",
    "server_trans_uploaded",
    "transfer_join_button",
    "transfer_not_ready_popup",
    "transmitter_server_excess",
    "transmitter_server_fail_connection",
    "transmitter_server_fail_attempting",
    "transmitter_inv",
    "transmitter_server_menu",
    "transmitter_server_search",
    "steam_launch_option",
    "steam_cloud_sync_conflic",
    "structure_turn_on",
    "trans_inv_ready",
    "dedi_deposit_ready",
    "dedi_deposit_clear",
    "capture_item_player_second_slot",
]
RoiRegionReconKey: TypeAlias = Literal[
    #
    "accept",
    "escape",
    "escape_obscured",
    "join_last_session",
    "join_game",
    "join_game_3_gen1",
    "join_game_4_gen1",
    "join_game_5_gen1",
    "join_button",
    "multiplayer",
    "server_full",
    "server_full_2",
    "red_fail",
    "mod_join",
    "req_mods",
    "join_text",
    "loading_screen",
    "searching",
    "no_session",
    "connection_timeout",
    "search",
    "download",
    "beds_title",
    "tribelog_check",
    "network_failure",
    "is_logging",
    "server_list_loaded",
    "term_and_conditions",
]

# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
