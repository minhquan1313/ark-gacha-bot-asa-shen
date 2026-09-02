from typing import Literal, NotRequired, TypeAlias, TypedDict


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

TransferStage: TypeAlias = Literal["destination", "resource"]

TransferStartMode: TypeAlias = Literal["default", "destinate"]


class TransferSettings(TypedDict):
    ping: int
    transfer_start_mode: TransferStartMode
    resource_station_yaw: float
    destination_station_yaw: float
    resource_server: str
    destination_server: str
    structure_load_delay: int
    steam_restart_interval: int
    ark_window_ready_timeout: int
    ark_launch_attempts: int


class TransferDediRoute(TypedDict):
    teleport: str
    transmitter_teleport: str
    items: list[DediStorageState]


class TransferDedisConfig(TypedDict):
    resource: TransferDediRoute
    destination: TransferDediRoute


class TransferPlayer(TypedDict):
    bed_name: str
    steam_account: str


class TransferPlayersConfig(TypedDict):
    players: list[TransferPlayer]


class TransferSteamUiCoords(TypedDict):
    window_title: str
    restart_delay: int


class TransferUiCoords(TypedDict):
    steam: TransferSteamUiCoords


class SteamAccountState(TypedDict):
    account_name: str
    most_recent: bool
    timestamp: int | float


class TransferRuntimeConfig(TypedDict):
    settings: TransferSettings
    dedis: TransferDedisConfig
    ui_coords: TransferUiCoords
    players: TransferPlayersConfig
    steam_accounts: NotRequired[list[SteamAccountState]]
    start_account: NotRequired[int]


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
    "inventory_drop",
    "dedi_deposit_clear",
    "capture_item_player_second_slot",
    "fishing_press_prompt",
    "fishing_failed",
    "fishing_success",
    "fishing_press_q",
    "fishing_press_w",
    "fishing_press_e",
    "fishing_press_a",
    "fishing_press_s",
    "fishing_press_d",
    "fishing_press_z",
    "fishing_press_x",
    "fishing_press_c",
    "teleporter_write_your_text",
]
RoiRegionReconKey: TypeAlias = Literal[
    #
    "accept",
    "escape",
    "escape_obscured",
    "join_last_session",
    "join_game",
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
    "join_game_3_gen1",
    "join_game_4_gen1",
    "join_game_5_gen1",
    "req_mods_loading",
    "pause_menu",
]

# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
