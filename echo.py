import asyncio
import threading

import serial
import serial.threaded
from serial import aio

from protocoll import dump


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


def testDumps(r):
    r.write(dump(0, 0))
    r.write(dump(0, 1))


r = ReaderThread()
r.start()
