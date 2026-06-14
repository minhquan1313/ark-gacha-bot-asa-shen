from PySide6.QtCore import Property, QObject, Signal, Slot

from source.gacha_bot.deposit_config import (
    default_crystal_route,
    default_dedi_item,
    default_grindable_route,
    default_vault_item,
    load_deposit_config,
    save_deposit_config,
)
from source.launcher.deposit_helper_capture import (
    capture_ccc_yaw_pitch,
    view_route_entry,
)
from source.launcher.vault_items_store import add_vault_item, load_vault_items


class DepositRouteHelperController(QObject):
    changed = Signal()
    dialogRequested = Signal(str, str, str)

    def __init__(self, launcher_controller, parent=None):
        super().__init__(parent)
        self.launcher_controller = launcher_controller
        self._config = load_deposit_config()
        self._route_kind = "crystal"
        self._route_index = 0
        self._status = "Ready."
        self._busy = False

    @Property(str, notify=changed)
    def title(self):
        return self._route_title()

    @Property(str, notify=changed)
    def routeKind(self):
        return self._route_kind

    @Property(int, notify=changed)
    def routeIndex(self):
        return self._route_index

    @Property(bool, notify=changed)
    def hasRoute(self):
        return self._route() is not None

    @Property(bool, notify=changed)
    def canRemoveRoute(self):
        return len(self._config.get(self._route_key(), [])) > 1

    @Property(str, notify=changed)
    def teleport(self):
        route = self._route()
        if route is None:
            return ""
        return str(route.get("teleport", ""))

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(bool, notify=changed)
    def busy(self):
        return self._busy

    @Property("QVariantList", notify=changed)
    def routes(self):
        rows = []
        for kind, key in (
            ("crystal", "depositCrystalData"),
            ("grindable", "depositGrindableData"),
        ):
            for index, route in enumerate(self._config.get(key, [])):
                rows.append(
                    {
                        "kind": kind,
                        "index": index,
                        "label": f"{kind.upper()} {index + 1}: {route.get('teleport') or 'NO TELEPORT'}",
                    }
                )
        return rows

    @Property("QVariantList", notify=changed)
    def rows(self):
        route = self._route()
        if route is None:
            return []
        rows = []
        if self._route_kind == "grindable":
            rows.append(self._row("grinder", 0, route.get("grinder", {})))
        for index, item in enumerate(route.get("dedi", {}).get("items", [])):
            rows.append(self._row("dedi", index, item))
        if self._route_kind == "crystal":
            for index, item in enumerate(route.get("vault", {}).get("items", [])):
                row = self._row("vault", index, item)
                row["items"] = ", ".join(item.get("items", []))
                row["itemValues"] = list(item.get("items", []))
                rows.append(row)
        return rows

    @Property("QVariantList", notify=changed)
    def vaultItems(self):
        try:
            return load_vault_items(self._config)
        except Exception:
            return []

    @Slot(str, int)
    def selectRoute(self, kind, index):
        kind = str(kind)
        if kind not in {"crystal", "grindable"}:
            self._set_status("Unknown deposit route type.")
            return
        key = self._route_key_for(kind)
        routes = self._config.get(key, [])
        try:
            index = int(index)
        except (TypeError, ValueError):
            self._set_status("Unknown deposit route index.")
            return
        if not (0 <= index < len(routes)):
            self._set_status("Unknown deposit route index.")
            return
        self._route_kind = kind
        self._route_index = index
        self.changed.emit()

    @Slot(str)
    def setTeleport(self, value):
        route = self._route()
        if route is None:
            self._set_status("Add a route before setting teleport.")
            return
        route["teleport"] = str(value)
        self._save("Teleport saved.")

    @Slot(str)
    def addRoute(self, kind):
        kind = str(kind)
        if kind == "crystal":
            key = "depositCrystalData"
            route = default_crystal_route()
        elif kind == "grindable":
            key = "depositGrindableData"
            route = default_grindable_route()
        else:
            return
        routes = self._config.setdefault(key, [])
        routes.append(route)
        self._route_kind = kind
        self._route_index = len(routes) - 1
        self._save("Route added.")

    @Slot()
    def removeCurrentRoute(self):
        key = self._route_key()
        routes = self._config.get(key, [])
        if not routes:
            return
        if len(routes) <= 1:
            self._set_status("At least one route of each type is required.")
            return
        del routes[self._route_index]
        self._route_index = max(0, min(self._route_index, len(routes) - 1))
        self._save("Route removed.")

    @Slot(str)
    def addRow(self, kind):
        route = self._route()
        if route is None:
            self._set_status("Add a route before adding rows.")
            return
        kind = str(kind)
        if kind == "vault":
            route["vault"]["items"].append(default_vault_item())
        elif kind == "dedi":
            route["dedi"]["items"].append(default_dedi_item())
        elif kind == "grinder":
            route["grinder"] = {
                "active": True,
                "location": {"yaw": 0.0, "pitch": 0.0},
                "crouched": False,
            }
        else:
            self._set_status("Unknown deposit row type.")
            return
        self._save("Row added.")

    @Slot(str)
    def captureNewRow(self, kind):
        kind = str(kind)
        if self._busy:
            return
        if kind == "vault" and self._route_kind != "crystal":
            return
        if kind not in {"dedi", "vault"}:
            return
        if not self.launcher_controller.require_ark_window("capture route location"):
            return
        self._set_busy(True, "Capturing new route row...")
        try:
            yaw, pitch = capture_ccc_yaw_pitch()
            route = self._route()
            if route is None:
                self._set_status("Add a route before capturing rows.")
                return
            if kind == "vault":
                item = default_vault_item()
                route["vault"]["items"].append(item)
            else:
                item = default_dedi_item()
                route["dedi"]["items"].append(item)
            item["location"]["yaw"] = yaw
            item["location"]["pitch"] = pitch
            self._save(f"Captured yaw {yaw:.2f}, pitch {pitch:.2f}.")
        except Exception as exc:
            self._set_status(f"Capture failed: {exc}")
            self.dialogRequested.emit("Capture Failed", str(exc), "error")
        finally:
            self._set_busy(False)
            self._refocus_helper()

    @Slot(str, int)
    def removeRow(self, kind, index):
        index = self._coerce_index(index, "Unknown deposit row index.")
        if index is None:
            return
        container = self._container(str(kind))
        if isinstance(container, list) and 0 <= index < len(container):
            del container[index]
            self._save("Row removed.")

    @Slot(str, int, str, "QVariant")
    def updateRow(self, kind, index, key, value):
        index = self._coerce_index(index, "Unknown deposit row index.")
        if index is None:
            return
        item = self._item(str(kind), index)
        if item is None:
            return
        try:
            if key in {"yaw", "pitch"}:
                item["location"][key] = float(value)
            elif key == "crouched":
                item["crouched"] = bool(value)
            elif key == "active":
                item["active"] = bool(value)
            elif key == "items":
                item["items"] = [
                    part.strip() for part in str(value).split(",") if part.strip()
                ]
        except ValueError as exc:
            self.dialogRequested.emit("Invalid Deposit Route", str(exc), "error")
            return
        self._save("Row saved.")

    @Slot(int, str)
    def addVaultItem(self, index, value):
        index = self._coerce_index(index, "Unknown vault row index.")
        if index is None:
            return
        item = self._item("vault", index)
        if item is None:
            return
        text = str(value).strip()
        if not text:
            return
        values = item.setdefault("items", [])
        if text not in values:
            values.append(text)
        try:
            add_vault_item(text, self._config)
        except Exception:
            pass
        self._save("Vault item saved.")

    @Slot(int, int)
    def removeVaultItem(self, index, item_index):
        index = self._coerce_index(index, "Unknown vault row index.")
        if index is None:
            return
        item_index = self._coerce_index(item_index, "Unknown vault item index.")
        if item_index is None:
            return
        item = self._item("vault", index)
        if item is None:
            return
        values = item.setdefault("items", [])
        if 0 <= item_index < len(values):
            del values[item_index]
            self._save("Vault item removed.")

    @Slot(str, int)
    def captureRow(self, kind, index):
        index = self._coerce_index(index, "Unknown deposit row index.")
        if index is None:
            return
        item = self._item(str(kind), index)
        if item is None or self._busy:
            return
        if not self.launcher_controller.require_ark_window("capture route location"):
            return
        self._set_busy(True, "Capturing route location...")
        try:
            yaw, pitch = capture_ccc_yaw_pitch()
            item["location"]["yaw"] = yaw
            item["location"]["pitch"] = pitch
            self._save(f"Captured yaw {yaw:.2f}, pitch {pitch:.2f}.")
        except Exception as exc:
            self._set_status(f"Capture failed: {exc}")
            self.dialogRequested.emit("Capture Failed", str(exc), "error")
        finally:
            self._set_busy(False)
            self._refocus_helper()

    @Slot(str, int)
    def viewRow(self, kind, index):
        index = self._coerce_index(index, "Unknown deposit row index.")
        if index is None:
            return
        item = self._item(str(kind), index)
        if item is None or self._busy:
            return
        if not self.launcher_controller.require_ark_window("view route location"):
            return
        self._set_busy(True, "Setting Ark view...")
        try:
            location = item.get("location", {})
            view_route_entry(
                location.get("yaw", 0.0),
                location.get("pitch", 0.0),
                item.get("crouched", False),
            )
            self._set_status("View applied.")
        except Exception as exc:
            self._set_status(f"View failed: {exc}")
            self.dialogRequested.emit("View Failed", str(exc), "error")
        finally:
            self._set_busy(False)
            self._refocus_helper()

    def _route_key(self):
        return self._route_key_for(self._route_kind)

    @staticmethod
    def _route_key_for(kind):
        if kind == "crystal":
            return "depositCrystalData"
        if kind == "grindable":
            return "depositGrindableData"
        raise ValueError("Unknown deposit route type.")

    def _route(self):
        routes = self._config[self._route_key()]
        if not routes:
            self._route_index = 0
            return None
        self._route_index = max(0, min(self._route_index, len(routes) - 1))
        return routes[self._route_index]

    def _route_title(self):
        if self._route() is None:
            return f"{self._route_kind.upper()} HELPER: NO ROUTES"
        return f"{self._route_kind.upper()} HELPER {self._route_index + 1}: {self.teleport or 'NO TELEPORT'}"

    def _container(self, kind):
        route = self._route()
        if route is None:
            return None
        if kind == "vault":
            return route.get("vault", {}).get("items", [])
        if kind == "dedi":
            return route.get("dedi", {}).get("items", [])
        if kind == "grinder":
            return route.get("grinder", {})
        return None

    def _item(self, kind, index):
        container = self._container(kind)
        if isinstance(container, list):
            if 0 <= index < len(container):
                return container[index]
            return None
        return container if isinstance(container, dict) else None

    def _coerce_index(self, value, message):
        try:
            return int(value)
        except (TypeError, ValueError):
            self._set_status(message)
            return None

    @staticmethod
    def _row(kind, index, item):
        location = item.get("location", {})
        return {
            "kind": kind,
            "index": index,
            "title": f"{kind.upper()} {index + 1}",
            "yaw": str(location.get("yaw", 0.0)),
            "pitch": str(location.get("pitch", 0.0)),
            "crouched": bool(item.get("crouched", False)),
            "active": bool(item.get("active", True)),
        }

    def _save(self, status):
        try:
            self._config = save_deposit_config(self._config)
            self._set_status(status)
        except Exception as exc:
            self._set_status(f"Save failed: {exc}")
            self.dialogRequested.emit("Invalid Deposit Routes", str(exc), "error")
        self.changed.emit()

    def _set_status(self, message):
        self._status = str(message)
        self.changed.emit()

    def _set_busy(self, busy, message=None):
        self._busy = bool(busy)
        if message:
            self._status = message
        self.changed.emit()

    def _refocus_helper(self):
        refocus = getattr(self.launcher_controller, "refocus_active_helper", None)
        if refocus is not None:
            refocus()
