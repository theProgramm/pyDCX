import math


def search():
    return b'\xF0\x00\x20\x32\x20\x0E\x40\xF7'


def ping(device_id: int):
    return b'\xF0\x00\x20\x32' + device_id.to_bytes(1, "big") + b'\x0E\x44\x00\x00\xF7'


def dump(device_id: int, part: int):
    return b'\xF0\x00\x20\x32' + device_id.to_bytes(1, "big") + b'\x0E\x50\x01\x00' + part.to_bytes(1, "big") \
           + b'\xf7'


def set_transmit_mode(device_id: int):
    return b'\xF0\x00\x20\x32' + device_id.to_bytes(1, "big") + b'\x0E\x3F\x0C\x00\xf7'


def calc_value_bytes(value: int):
    return int(value / 128).to_bytes(1, "big") + int(value % 128).to_bytes(1, "big")


def set_muted(device_id: int, channel_id: int, muted: bool):
    return b'\xf0\x00\x20\x32' + device_id.to_bytes(1, "big") + b'\x0e\x20\x01' + channel_id.to_bytes(1, "big") \
           + b'\x03' + (b'\x01' if muted else b'\x00') + b'\x01\xf7'


def internal_volume_from_display_value(v: float):
    return math.floor(v * 10) + 150


def set_volume(device_id: int, channel_id: int, volume: int):
    return b'\xf0\x00\x20\x32' + device_id.to_bytes(1, "big") + b'\x0e\x20\x01' + channel_id.to_bytes(1, "big") \
           + b'\x02' + calc_value_bytes(internal_volume_from_display_value(volume)) + b'\xf7'
