from source.launcher.pages.common import (
    AutoJoinServerHelper,
    DepositRouteHelper,
    FertilizerRefreshHelper,
    PositionRenderHelper,
    ServerTransferHelper,
    SwitchSteamHelper,
    contextlib,
)


class HelperPagesMixin:
    def open_deposit_helper(self, route_kind, route_index):
        if not self._can_open_setup_helper():
            return
        self._ensure_deposit_config()
        existing = self.find_deposit_helper(route_kind, route_index)
        if existing is not None:
            existing.show()
            existing.raise_()
            existing.activateWindow()
            self.deposit_helper = existing
            return

        self.close_external_helpers()
        helper = DepositRouteHelper(self, route_kind, route_index)
        self.register_deposit_helper(helper)
        helper.show()
        helper.raise_()
        helper.activateWindow()
        self.deposit_helper = helper

    def open_position_render_helper(self):
        if not self._can_open_setup_helper():
            return
        helper = self.find_deposit_helper("position_render", None)
        if helper is not None:
            helper.show()
            helper.raise_()
            helper.activateWindow()
            self.deposit_helper = helper
            return

        self.close_external_helpers()
        helper = PositionRenderHelper(self)
        helper.route_kind = "position_render"
        helper.route_index = None
        self.register_deposit_helper(helper)
        helper.show()
        helper.raise_()
        helper.activateWindow()
        self.deposit_helper = helper

    def open_fertilizer_refresh_helper(self):
        if not self._can_open_setup_helper():
            return
        helper = self.find_deposit_helper("fertilizer_refresh", None)
        if helper is not None:
            helper.show()
            helper.raise_()
            helper.activateWindow()
            self.deposit_helper = helper
            return

        self.close_external_helpers()
        helper = FertilizerRefreshHelper(self)
        self.register_deposit_helper(helper)
        helper.show()
        helper.raise_()
        helper.activateWindow()
        self.deposit_helper = helper

    def open_auto_join_server_helper(self):
        if not self._can_open_setup_helper():
            return
        helper = self.find_deposit_helper("auto_join_server", None)
        if helper is not None:
            helper.show()
            helper.raise_()
            helper.activateWindow()
            self.deposit_helper = helper
            return

        self.close_external_helpers()
        helper = AutoJoinServerHelper(self)
        self.register_deposit_helper(helper)
        helper.show()
        helper.raise_()
        helper.activateWindow()
        self.deposit_helper = helper

    def open_server_transfer_helper(self):
        if not self._can_open_setup_helper():
            return
        helper = self.find_deposit_helper("server_transfer", None)
        if helper is not None:
            helper.show()
            helper.raise_()
            helper.activateWindow()
            self.deposit_helper = helper
            return

        self.close_external_helpers()
        helper = ServerTransferHelper(self)
        self.register_deposit_helper(helper)
        helper.show()
        helper.raise_()
        helper.activateWindow()
        self.deposit_helper = helper

    def open_switch_steam_helper(self) -> None:
        if not self._can_open_setup_helper():
            return
        helper = self.find_deposit_helper("switch_steam", None)
        if helper is not None:
            helper.show()
            helper.raise_()
            helper.activateWindow()
            self.deposit_helper = helper
            return

        self.close_external_helpers()
        helper = SwitchSteamHelper(self)
        self.register_deposit_helper(helper)
        helper.show()
        helper.raise_()
        helper.activateWindow()
        self.deposit_helper = helper

    def _can_open_setup_helper(self):
        if self.is_program_running() or getattr(self, "program_stopping", False):
            self.dialog(
                "Stop Program First",
                "Stop the running automation before opening a setup helper.",
                "warning",
            )
            return False
        return True

    def find_deposit_helper(self, route_kind, route_index):
        for helper in list(getattr(self, "external_helpers", [])):
            try:
                if (
                    helper.route_kind == route_kind
                    and helper.route_index == route_index
                ):
                    return helper
            except RuntimeError:
                self.forget_deposit_helper(helper)
        return None

    def register_deposit_helper(self, helper):
        if not hasattr(self, "external_helpers"):
            self.external_helpers = []
        if helper not in self.external_helpers:
            self.external_helpers.append(helper)
        helper.destroyed.connect(
            lambda _=None, tracked=helper: self.forget_deposit_helper(tracked)
        )

    def forget_deposit_helper(self, helper):
        helpers = getattr(self, "external_helpers", [])
        if helper in helpers:
            helpers.remove(helper)

    def close_external_helpers(self):
        for helper in list(getattr(self, "external_helpers", [])):
            with contextlib.suppress(RuntimeError):
                helper.close()
        self.external_helpers.clear()
