from typing import TypedDict


class ObjectAim(TypedDict):
    yaw: float
    pitch: float


class DediStorageState(TypedDict):
    location: ObjectAim
    crouched: bool
