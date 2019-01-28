import asyncio
import atexit
import logging
import threading
from threading import RLock

import serial
import serial.threaded
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from serial import aio
from serial.threaded import Packetizer

import const
from Ultradrive import Ultadrive


class Data:
    def __init__(self):
        logging.getLogger('apscheduler').setLevel(logging.INFO)
        logging.getLogger('flask').setLevel(logging.DEBUG)
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        logging.getLogger('flask.app.api.http').setLevel(logging.ERROR)
        logging.getLogger('flask.app.').setLevel(logging.ERROR)
        logging.getLogger('flask.app.api.http').setLevel(logging.ERROR)
        logging.getLogger('flask.app.ultradrive.io').setLevel(logging.DEBUG)
        logging.getLogger('flask.app.ultradrive.packet').setLevel(logging.INFO)
        logging.getLogger('flask.app.ultradrive.protocol').setLevel(logging.DEBUG)

        self.ultradrive = Ultadrive(app.logger)
        self.start_serial()
        app.logger.info(f"rules: {app.url_map}")

    def start_serial(self):
        self.ultradrive.start()


app = Flask(__name__, static_url_path="/statics")
data = None


@app.before_first_request
def setup():
    global data
    if data is None:
        data = Data()


class Ultadrive(threading.Thread):
    def __init__(self, logger):
        super(Ultadrive, self).__init__()
        self.__logger = logger.getChild("ultradrive")
        self.__io_logger = self.__logger.getChild("io")
        self.__packet_logger = self.__logger.getChild("packet")
        self.__loop = None
        self.__coro = None
        self.__protocol = UltradriveProtocol(self.__logger, self)

        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': ThreadPoolExecutor(2),
        }
        job_defaults = {
            'coalesce': True,
            'max_instances': 1
        }
        self.__scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults)
        self.__logger.debug(f"created new Ultradrive thread {self}")

    def protocol(self):
        self.__logger.debug(f"requesting protocol {self.__protocol}")
        return self.__protocol

    def stop(self):
        self.__logger.debug(f"stoppgin ultradrive thread {self}")
        if self.__loop is not None:
            self.__loop.stop()
            self.__coro = None
            self.__loop = None
        if self.__scheduler is not None and self.__scheduler.running:
            self.__scheduler.shutdown(wait=False)

    def write(self, data):
        self.__loop.call_soon_threadsafe(self.__protocol.write, data)

    def ping_all(self):
        self.__io_logger.debug(f"pinging ")
        self.ping(1)
        self.__io_logger.debug(f"finished pinging")

    def resync(self):
        self.__logger.debug("resyncing...")
        self.search()

    def search(self):
        self.__logger.debug("searching...")
        search_command = b'\xF0\x00\x20\x32\x20\x0E\x40' + bytes([247])
        self.write(search_command)
        self.__io_logger.debug("searching done")

    def ping(self, device_id: int):
        ping_command = b'\xF0\x00\x20\x32' + device_id.to_bytes(
            1, "big") + b'\x0E\x44\x00\x00' + const.TERMINATOR
        self.write(ping_command)

    def dump(self, device_id: int, part: int):
        dump_command = b'\xF0\x00\x20\x32' + device_id.to_bytes(
            1, "big") + b'\x0E\x50\x01\x00' + part.to_bytes(1, "big") + const.TERMINATOR
        self.write(dump_command)

    def dump_device(self, device_id: int):
        self.__io_logger.debug(f"requesting dump for: {device_id}")
        self.dump(device_id, 0)
        self.dump(device_id, 1)
        self.__io_logger.debug(f"finished dump for {device_id}")

    def set_transmit_mode(self, device_id: int):
        self.__logger.debug(f"setting transmit mode for device {device_id}")
        transmit_mode_command = b'\xF0\x00\x20\x32' + device_id.to_bytes(
            1, "big") + b'\x0E\x3F\x0C\x00' + const.TERMINATOR
        self.write(transmit_mode_command)

    def run(self):
        self.__logger.info(f"starting new ultradrive thread")
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.__loop = asyncio.get_event_loop()
        self.__coro = serial.aio.create_serial_connection(self.__loop, self.protocol, '/dev/ttyS0',
                                                          baudrate=const.BAUD_RATE)
        try:
            self.__logger.debug("try connecting...")
            self.__loop.run_until_complete(self.__coro)
            self.__logger.debug("connecting not failed")
            self.__loop.run_forever()
            self.stop()
        except serial.serialutil.SerialException as e:
            self.__logger.warn(f"Serial exception - continuing with demo data \n{e}")
            self.stop()
        self.__logger.info(f"stopped ultradrive thread")

    def connection_made(self):
        self.__logger.debug("ultradrive thread recieved connection_made")
        self.__scheduler.start()
        self.__scheduler.add_job(self.ping_all, 'interval', seconds=const.PING_INTEVAL)
        self.__scheduler.add_job(self.resync, 'interval', seconds=const.RESYNC_INTEVAL)
        atexit.register(self.stop)
        self.__loop.call_soon(self.resync)

    def handle_packet(self, packet):
        self.__packet_logger.debug(f"handling packet {packet}")


class Echo(serial.threaded.Protocol):
    transport = None

    def __init__(self, logger, ultradrive: Ultadrive):
        super(Echo, self).__init__()
        self.__logger = logger.getChild("echo_protocol")
        self.__ultradrive = ultradrive

    def connection_made(self, transport):
        self.transport = transport
        self.__logger.info(f'port opened with transport: {transport}')
        self.__ultradrive.connection_made()

    def data_received(self, data):
        self.__logger.debug(f"received data: {data}")

    def connection_lost(self, exc):
        print(f"lost connection: {exc}")
        self.__logger.info(f"connection on port lost {exec}")
        self.__ultradrive.stop()

    def write(self, data):
        self.transport.write(data)


class UltradriveProtocol(Packetizer):
    TERMINATOR = const.TERMINATOR
    lock: RLock = RLock()

    def __init__(self, logger, ultradrive: Ultadrive):
        super(UltradriveProtocol, self).__init__()
        self.__logger = logger.getChild("protocol")
        self.__ultradrive = ultradrive

    def connection_made(self, transport):
        super(UltradriveProtocol, self).connection_made(transport)
        self.__logger.info(f'port opened with transport: {transport}')
        self.__ultradrive.connection_made()

    def connection_lost(self, exc):
        super(UltradriveProtocol, self).connection_lost(exc)
        self.__logger.info(f"connection on port lost {exec}")
        asyncio.get_event_loop().stop()

    def data_received(self, data):
        self.__logger.debug(f"received data: {data}")
        super(UltradriveProtocol, self).data_received(data)

    def handle_packet(self, packet):
        self.__logger.debug(f"received package: {packet}")
        if packet.startswith(const.VENDOR_HEADER):
            self.__ultradrive.handle_packet(packet)
        else:
            self.__logger.warn(f"package without vendor header received {packet}")

    def write(self, data):
        self.__logger.debug("waiting for empty in_waiting before write")
        with self.lock:
            while self.transport.serial.in_waiting > 0:
                pass
            self.__logger.debug(f"finnaly writing {data}")
            self.transport.write(data)
            blocked = False
            if self.transport.serial.in_waiting > 0:
                blocked = True
            self.__logger.debug(f"wrote {data}")
            return blocked


if __name__ == '__main__':
    print("lets go!")
    app.run(host="0.0.0.0", port=5000, debug=True)
