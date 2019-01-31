import asyncio
import threading
from typing import Dict

import serial
import serial.threaded
from serial import aio

import const


class Echo(serial.threaded.Packetizer):
    TERMINATOR = const.TERMINATOR
    last_package: bytes = None

    def handle_packet(self, packet: bytes):
        if self.last_package is not None:
            if len(self.last_package) != len(packet):
                print("size changed!!")
            else:
                difs: Dict = {}
                i = 0
                diff_started = False
                diff_start = -1
                while i < len(self.last_package):
                    if diff_started:
                        if self.last_package[i] == packet[i]:
                            difs[diff_started] = (i, self.last_package[diff_start:i], packet[diff_start:i])
                            diff_started = False
                    elif self.last_package[i] == packet[i]:
                        diff_started = True
                        diff_start = i
                if difs:
                    for (start, v) in iter(difs):
                        print(f"dif from {start} to {v[0]} changed {v[1]} to {v[2]}")

    def connection_made(self, transport):
        self.transport = transport
        print(f"made connection to {transport}")

    def connection_lost(self, exc):
        print(f"lost connection: {exc}")

    def write(self, data):
        while self.transport.serial.in_waiting > 0:
            pass
        self.transport.write(data)


class ReaderThread(threading.Thread):
    protocol = Echo()

    def echo(self):
        return self.protocol

    def run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.__loop = asyncio.get_event_loop()
        self.con = serial.aio.create_serial_connection(self.__loop, self.echo, '/dev/ttyS0',
                                                       baudrate=38400)
        self.__loop.run_until_complete(self.con)
        self.__loop.run_forever()
        self.__loop.close()

    def write(self, data):
        self.protocol.write(data)


def asHex(s):
    return ":".join("{:02x}".format(ord(c)) for c in s)


searchQ = b'\xF0\x00\x20\x32\x20\x0E\x40' + bytes([247])


def pingQ(i):
    return b'\xF0\x00\x20\x32' + i.to_bytes(1, "big") + b'\x0E\x44\x00\x00\xF7'


def dump(device_id: int, part: int):
    return b'\xF0\x00\x20\x32' + device_id.to_bytes(1, "big") + b'\x0E\x50\x01\x00' + part.to_bytes(1, "big") + b'\xF7'


def setTM(device_id: int):
    return b'\xF0\x00\x20\x32' + device_id.to_bytes(
        1, "big") + b'\x0E\x3F\x0C\x00\xF7'


r = ReaderThread()
r.start()
r.write(setTM(0))
