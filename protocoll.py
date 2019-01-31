import math
from dataclasses import dataclass
from typing import List

import const


@dataclass
class Query:
    device_id: int
    command: int
    data: bytes

    def __init__(self, device_id: int, command: int, data: bytes = None):
        if device_id is None or command is None:
            raise ValueError()
        self.device_id = device_id
        self.command = command
        self.data = data if data is not None else bytes([])

    def as_bytes(self) -> bytes:
        return const.VENDOR_HEADER + self.device_id.to_bytes(1, "big") + b'\x0E' \
               + self.command.to_bytes(1, "big") + self.data + const.TERMINATOR


@dataclass
class DirectCommandParameter:
    channel: int
    param_num: int
    params: bytes

    def __init__(self, channel: int, param_num: int, value: int = None, direct_params: bytes = None):
        if channel is None:
            raise ValueError("channel must not be none")
        self.channel = channel
        if param_num is None:
            raise ValueError("function must not be none")
        self.param_num = param_num
        if value is not None:
            self.params = calc_value_bytes(value)
        elif direct_params is not None:
            self.params = direct_params
        else:
            raise ValueError("need either integer value or direct bytes")

    def as_bytes(self) -> bytes:
        return self.channel.to_bytes(1, "big") + self.param_num.to_bytes(1, "big") + self.params


@dataclass
class DirectCommand:
    params: List[DirectCommandParameter]

    def __init__(self):
        self.params = []

    def add_new_param(self, func: int, value: int = None, direct_params: bytes = None) -> None:
        self.params.append(DirectCommandParameter(func, value=value, direct_params=direct_params))

    def add_param(self, param: DirectCommandParameter):
        self.params.append(param)

    def as_query(self, device_id: int) -> Query:
        return Query(device_id, 0x20, int_to_byte(len(self.params)) + b''.join([x.as_bytes() for x in self.params]))

    def as_bytes(self, device_id: int) -> bytes:
        return self.as_query(device_id).as_bytes()


def search() -> bytes:
    return b'\xF0\x00\x20\x32\x20\x0E\x40\xF7'


def ping(device_id: int) -> bytes:
    return Query(device_id, 0x44).as_bytes()


def dump(device_id: int, part: int) -> bytes:
    return Query(device_id, 0x50, b'\x01' + part.to_bytes(2, "big")).as_bytes()


def set_transmit_mode(device_id: int) -> bytes:
    return Query(device_id, 0x3F, b'\x0C\x00').as_bytes()


def int_to_byte(i: int) -> bytes:
    return i.to_bytes(1, "big")


def calc_value_bytes(value: int) -> bytes:
    return int(value / 128).to_bytes(1, "big") + int(value % 128).to_bytes(1, "big")


def bool_to_int(b: bool) -> int:
    return 0x01 if b else 0x00


def internal_volume_from_display_value(v: float) -> int:
    return math.floor(v * 10) + 150


def internal_threshold_from_display_value(v: int) -> int:
    return math.floor(v * 10) + 240


def set_muted_param(channel_id: int, muted: bool) -> DirectCommandParameter:
    return DirectCommandParameter(channel_id, 0x03, bool_to_int(muted))


def set_volume_param(channel_id: int, volume: int) -> DirectCommandParameter:
    return DirectCommandParameter(channel_id, 0x02, internal_volume_from_display_value(volume))


def set_limiter_on_param(channel_id: int, on: bool) -> DirectCommandParameter:
    return DirectCommandParameter(channel_id, 0x46, bool_to_int(on))


def set_limiter_threshold_param(channel_id: int, threshold: int) -> DirectCommandParameter:
    return DirectCommandParameter(channel_id, 0x47, internal_threshold_from_display_value(threshold))
