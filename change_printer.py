import asyncio
import threading
from serial import aio
import serial
import serial.threaded


class Echo(serial.threaded.Protocol):
    def connection_made(self, transport):
        self.transport = transport
        print(f"made connection to {transport}")

    def data_received(self, data):
        print(f"received data: {data}")

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


def testDumps(r):
    r.write(dump(0, 0))
    r.write(dump(0, 1))


r = ReaderThread()
r.start()
