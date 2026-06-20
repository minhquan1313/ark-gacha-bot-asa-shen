import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from source.launcher.steam_accounts import (
    load_steam_accounts,
    parse_loginusers,
    select_auto_login_account,
    update_allow_auto_login,
)


SAMPLE_LOGINUSERS = '''"users"
{
    "111"
    {
        "AccountName"       "alpha"
        "MostRecent"        "0"
        "Timestamp"         "10"
        "AllowAutoLogin"    "0"
    }
    "222"
    {
        "AccountName"       "beta"
        "MostRecent"        "1"
        "Timestamp"         "20"
        "AllowAutoLogin"    "0"
    }
}
'''


class SteamAccountsTests(unittest.TestCase):
    def test_parse_loginusers_extracts_accounts(self):
        accounts = parse_loginusers(SAMPLE_LOGINUSERS)

        self.assertEqual([account.account_name for account in accounts], ["alpha", "beta"])
        self.assertFalse(accounts[0].most_recent)
        self.assertTrue(accounts[1].most_recent)
        self.assertEqual(accounts[1].timestamp, 20)

    def test_load_steam_accounts_sorts_most_recent_first(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "loginusers.vdf"
            path.write_text(SAMPLE_LOGINUSERS, encoding="utf-8")

            accounts = load_steam_accounts(path)

        self.assertEqual([account["account_name"] for account in accounts], ["beta", "alpha"])

    def test_update_allow_auto_login_only_touches_target_block(self):
        updated = update_allow_auto_login(SAMPLE_LOGINUSERS, "beta")

        self.assertIn('"AccountName"       "alpha"', updated)
        self.assertIn('"MostRecent"        "1"', updated)
        self.assertIn('"AllowAutoLogin"    "0"', updated.split('"222"')[0])
        self.assertIn('"AllowAutoLogin"    "1"', updated.split('"222"')[1])

    def test_select_auto_login_account_writes_vdf_and_registry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "loginusers.vdf"
            path.write_text(SAMPLE_LOGINUSERS, encoding="utf-8")

            with patch("source.launcher.steam_accounts.subprocess.run") as run:
                select_auto_login_account("beta", path)

            updated = path.read_text(encoding="utf-8")

        self.assertIn('"AllowAutoLogin"    "1"', updated.split('"222"')[1])
        self.assertEqual(run.call_count, 2)
        self.assertIn("AutoLoginUser", run.call_args_list[0].args[0])
        self.assertIn("RememberPassword", run.call_args_list[1].args[0])


if __name__ == "__main__":
    unittest.main()
