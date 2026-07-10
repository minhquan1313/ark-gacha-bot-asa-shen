import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from source.launcher.ark_game_setup import ARK_STEAM_ID, find_running_steam_dir


@dataclass(frozen=True)
class SteamAccount:
    steam_id: str
    account_name: str
    most_recent: bool
    timestamp: int
    allow_auto_login: str


def loginusers_path(steam_dir: Path | None = None):
    """Return the loginusers.vdf path for the running Steam installation."""
    root = Path(steam_dir) if steam_dir is not None else find_running_steam_dir()
    return root / "config" / "loginusers.vdf"


def load_loginusers(path: Path | None = None):
    """Load loginusers.vdf and return its raw text plus parsed account records."""
    vdf_path = Path(path) if path is not None else loginusers_path()
    text = vdf_path.read_text(encoding="utf-8", errors="replace")
    return text, parse_loginusers(text)


def load_steam_accounts(path: Path | None = None):
    """Return parsed Steam accounts sorted for helper display."""
    _text, accounts = load_loginusers(path)
    return [account_to_dict(account) for account in sorted_steam_accounts(accounts)]


def parse_loginusers(vdf_text: str):
    """Parse Steam loginusers.vdf account blocks used by the transfer helper."""
    accounts: list[SteamAccount] = []
    for steam_id, block, _start, _end in _iter_account_blocks(vdf_text):
        account_name = _block_value(block, "AccountName")
        if not account_name:
            continue
        accounts.append(
            SteamAccount(
                steam_id=steam_id,
                account_name=account_name,
                most_recent=_block_value(block, "MostRecent") == "1",
                timestamp=_int_or_zero(_block_value(block, "Timestamp")),
                allow_auto_login=_block_value(block, "AllowAutoLogin"),
            )
        )
    return accounts


def sorted_steam_accounts(accounts: list[SteamAccount]):
    """Sort accounts by most-recent status, then by newest timestamp."""
    return sorted(
        accounts, key=lambda account: (not account.most_recent, -account.timestamp)
    )


def most_recent_account_name(
    accounts: list[dict[str, object]] | list[SteamAccount],
):
    """Return the AccountName marked MostRecent, or an empty string."""
    for account in accounts:
        if isinstance(account, SteamAccount):
            if account.most_recent:
                return account.account_name
            continue
        if account.get("most_recent"):
            return str(account.get("account_name", ""))
    return ""


def account_to_dict(account: SteamAccount):
    return {
        "steam_id": account.steam_id,
        "account_name": account.account_name,
        "most_recent": account.most_recent,
        "timestamp": account.timestamp,
        "allow_auto_login": account.allow_auto_login,
    }


def update_allow_auto_login(vdf_text: str, account_name: str):
    """Set AllowAutoLogin to 1 only inside the selected AccountName block."""
    for _steam_id, block, start, end in _iter_account_blocks(vdf_text):
        if _block_value(block, "AccountName") != account_name:
            continue
        updated_block = _set_block_value(block, "AllowAutoLogin", "1")
        return vdf_text[:start] + updated_block + vdf_text[end:]
    raise ValueError(f"Steam account was not found in loginusers.vdf: {account_name}")


def select_auto_login_account(account_name: str, path: Path | None = None):
    """Persist Steam auto-login settings for the requested account."""
    vdf_path = Path(path) if path is not None else loginusers_path()
    text = vdf_path.read_text(encoding="utf-8", errors="replace")
    vdf_path.write_text(update_allow_auto_login(text, account_name), encoding="utf-8")
    subprocess.run(
        [
            "reg",
            "add",
            r"HKCU\Software\Valve\Steam",
            "/v",
            "AutoLoginUser",
            "/t",
            "REG_SZ",
            "/d",
            account_name,
            "/f",
        ],
        check=False,
    )
    subprocess.run(
        [
            "reg",
            "add",
            r"HKCU\Software\Valve\Steam",
            "/v",
            "RememberPassword",
            "/t",
            "REG_DWORD",
            "/d",
            "1",
            "/f",
        ],
        check=False,
    )
    return vdf_path


def close_steam():
    """Force close Steam before relaunching with the selected auto-login user."""
    subprocess.run(["taskkill", "/F", "/IM", "steam.exe"], check=False)


def launch_steam():
    """Open the registered Steam client without resolving its executable path."""
    # subprocess.Popen(["cmd", "/c", "start", "", "steam://open/main"])
    subprocess.Popen(
        ["cmd", "/c", "start", "", f"steam://nav/games/details/{ARK_STEAM_ID}"]
    )


def _iter_account_blocks(vdf_text: str):
    for match in re.finditer(r'"(?P<steam_id>\d+)"\s*\{', vdf_text):
        block_start = match.end()
        block_end = _matching_brace(vdf_text, block_start - 1)
        if block_end is None:
            continue
        yield (
            match.group("steam_id"),
            vdf_text[block_start:block_end],
            block_start,
            block_end,
        )


def _matching_brace(text: str, opening_index: int):
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening_index, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _block_value(block: str, key: str):
    match = re.search(rf'"{re.escape(key)}"\s+"((?:\\.|[^"\\])*)"', block)
    if not match:
        return ""
    return match.group(1).replace(r"\\", "\\")


def _set_block_value(block: str, key: str, value: str):
    pattern = re.compile(rf'("{re.escape(key)}"\s+")((?:\\.|[^"\\])*)(")')
    if pattern.search(block):
        return pattern.sub(rf"\g<1>{value}\g<3>", block, count=1)
    insert = f'\n\t\t"{key}"\t\t"{value}"'
    return block.rstrip() + insert + block[len(block.rstrip()) :]


def _int_or_zero(value: str):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
