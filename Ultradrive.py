import asyncio
import atexit
import threading
from dataclasses import dataclass
from threading import RLock
from typing import Dict

import serial
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from serial import aio
from serial.threaded import Packetizer

import const


@dataclass
class Device:
    dump0: bytearray
    dump1: bytearray
    search_response: bytearray
    ping_response: bytearray
    device_id: int
    is_new: bool = True

    def __init__(self, device_id: int):
        self.dump0: bytearray = bytearray(const.PART_0_LENGTH)
        self.dump1: bytearray = bytearray(const.PART_1_LENGTH)
        self.search_response: bytearray = bytearray(const.SEARCH_RESPONSE_LENGTH)
        self.ping_response: bytearray = bytearray(const.PING_RESPONSE_LENGTH)
        self.device_id = device_id

    def to_gui(self) -> bytearray:
        ret = bytearray()
        ret.extend(self.dump0)
        ret.extend(self.dump1)
        ret.extend(self.ping_response)
        return ret


class Ultadrive(threading.Thread):
    def __init__(self, logger):
        super(Ultadrive, self).__init__()
        self.__logger = logger.getChild("ultradrive")
        self.__io_logger = self.__logger.getChild("io")
        self.__packet_logger = self.__logger.getChild("packet")
        self.__loop = None
        self.__coro = None
        self.__protocol = UltradriveProtocol(self.__logger, self)
        self.__devices = dict()

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

    def devices(self) -> Dict[int, Device]:
        return self.__devices

    def device(self, n: int) -> Device:
        return self.__devices[n]

    def stop(self):
        self.__logger.debug(f"stoppgin ultradrive thread {self}")
        if self.__loop is not None:
            self.__loop.stop()
            self.__coro = None
            self.__loop = None
        if self.__scheduler is not None and self.__scheduler.running:
            self.__scheduler.shutdown(wait=False)

    # noinspection PyPep8
    def setup_dummy_data(self):
        self.__devices[0] = Device(0)
        self.__devices[1] = Device(1)
        self.devices()[
            0].dump0 = b'\xf0\x00 2\x00\x0e\x10\x01\x01\x00\x02\x00\x00n\x06\x00\x00\x00\x00\x00\x00XPCR\x01\x00\x11\x00\x01^\x06\x00\x00XP\x00RB\x01\x00\x11\x01\x1a\x00\x00\x00\x00\x05\x00\x00\x00\x00\x00\x00\x01\x00\x01\x00D\x00CX2496 \x00       \x00 \'/-=XC\x1eUR\x01\x00\x11\x01|@\x05\x00\x00\x00\x00\x00\x00\x00\x01\x002*3WA\x00Y  \x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x01\x00\x01\x00\x00\x00\x00\x01\x00\x01\x00\'\x00\x16@\x00\x16\x00\x16\x00>\x00*\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00S\x00\x00\x17\x00\x05\x00X\x02\x00\x01\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x004\x00\x14\x10\x00\x00\x01\x01\x00\x01\x00\x00`\x00\x14\x00=\x00\x01\x10\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x004A\x00\x14\x00\x16\x00\x01\x00\x08\x01\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00\x16\x00\x01\x00\x01\x04\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x024\x00\x14\x00\x16\x00\x01\x11\x00\x01\x00>\x00\x00\x00\x08\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00S\x00\x17\x00 \x05\x00X\x02\x00\x004@\x00\x14\x00\x16\x00\x01\x00\x08\x01\x004\x00\x14\x00\x00\x04\x01\x01\x00\x01\x00`\x00\x00\x14\x00=\x00\x01\x00\x01\x04\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x024\x00\x14\x00\x16\x00\x01\x11\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x004A\x00\x14\x00\x16\x00\x01\x00\x08\x01\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00\x16\x00\x01\x00\x01\x04\x00\x16\x00\x00\x00\x00\x00\x02\x00\x00\x01\x00\x00\x00\x00\x00\x00S\x00\x17\x00\x05\x00\x08X\x02\x00\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x02/\x01\x14\x00\x00\x00\x01\x00\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x004A\x00\x14\x00\x16\x00\x01\x00\x08\x01\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00\x16\x00\x01\x00\x01\x04\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x024\x00\x14\x00\x16\x00\x01\x11\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x00\x16A\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00S\x00\x00\x17\x00\x05\x00X\x02\x02\x00\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00,\x01\x00\x00\x00\x00\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x024\x00\x14\x00\x16\x00\x01\x11\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x004A\x00\x14\x00\x16\x00\x01\x00\x08\x01\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00\x16\x00\x01\x00\x01\x04\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x00$\x00\x01\x10\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00S\x00\x17@\x00\x05\x00X\x02\x00\x00\x004\x00\x14\x00\x16\x00\x01\x11\x00\x01\x00\x05\x00\x14\x00\x00\x00\x00\x01\x00\x01\x004@\x00\x14\x00\x16\x00\x01\x00\x08\x01\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00\x16\x00\x01\x00\x01\x04\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x024\x00\x14\x00\x16\x00\x01\x11\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x004A\x00\x14\x00\x16\x00\x01\x00\x08\x01\x00\t\x00\x00\x00\x06\x00\x00\x00\x00\x06\x00|\x00\x00\x00\x00p\x00\r\x00\x00\x14\x00\x00\x00\x00\x00$\x00 \x01\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00S\x00\x00\x17\x00\x05\x00X\x02\x00\x01\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x00\x05\x00\x14\x00\x00\x00\x00\x01\x00\x01\x00\x004\x00\x14\x00\x16\x00\x01\x11\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x004A\x00\x14\x00\x16\x00\x01\x00\x08\x01\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00\x16\x00\x01\x00\x01\x04\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x026\xf7'
        self.devices()[
            0].dump1 = b'\xf0\x00 2\x00\x0e\x10\x01\x01\x00\x02\x00\x014\x00\x14\x00\x16\x00\x01\x11\x00\x01\x00\x10\x00\x01\x00\x00\x06\x00\x00\x00\x06\x00|\x00\x00\x00\x00p\x00\r\x00(\x00\x00\x00\x00\x00\x00\x04@\x00\x01\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00S\x00\x00\x17\x00\x05\x00X\x02\x02\x00\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00,\x01\x01\x00\x01\x00\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x024\x00\x14\x00\x16\x00\x01\x11\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x004A\x00\x14\x00\x16\x00\x01\x00\x08\x01\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00\x16\x00\x01\x00\x01\x04\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x00\x0b\x00\x00\x00\x00\x06\x00|\x00\x06\x00\x00h\x00\x00\x00p\x00\rQ\x00\x00\x00\x00\x00\x00\x00\x00\x04\x00\x01\x00\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00S\x00\x17\x00\x05\x00X\x04\x02\x00\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x004A\x00\x14\x00,\x01\x01\x00\x00\x01\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00\x16\x00\x01\x00\x01\x04\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x024\x00\x14\x00\x16\x00\x01\x11\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x004A\x00\x14\x00\x16\x00\x01\x00\x08\x01\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x00\x12\x00\x00\x01\x00\x06\x00|\x00\x06\x00\x00h\x00\x00\x00p\x00"\r\x00\x00\x00\x00\x00\x00\x01\x00\x16\x00\x01\x00\x00\x00\x02\x00\x00\x01\x00\x00\x00\x00\x00\x00S\x00\x17\x00\x05\x00\x08X\x02\x00\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x02 \x01\x14\x00\x00\x00\x01\x00\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x004A\x00\x14\x00\x16\x00\x01\x00\x08\x01\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00\x16\x00\x01\x00\x01\x04\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x024\x00\x14\x00\x16\x00\x01\x11\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x00\r\x01\x00\x00\x00\x06\x00h\x00 \x00\x00?\x01\x00\x00p@\x00\r\x00\x00\x00\x00\x00\x02\x00\x00\x16\x00\x01\x00\x00\x04\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00S\x00\x17\x00\x05\x10\x00X\x02\x00\x004\x00 \x14\x00\x16\x00\x01\x00\x01\x04\x00 \x01\x14\x00\x00\x00\x00\x01\x00\x01\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x024\x00\x14\x00\x16\x00\x01\x11\x00\x01\x004\x00\x14\x00\x08\x16\x00\x01\x00\x01\x004A\x00\x14\x00\x16\x00\x01\x00\x08\x01\x004\x00\x14\x00\x16D\x00\x01\x00\x01\x004\x00 \x14\x00\x16\x00\x01\x00\x01\x04\x004\x00\x14\x00\x16\x00"\x01\x00\x01\x004\x00\x14\x10\x00\x16\x00\x01\x00\x01\x00\x02\x14\x00\x01\x00\x06\x00h@\x00\x00\x00?\x01\x00\x00\x00p\x00\r\x00\x00\x00\x00\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00I\x00\x00N\x00P\x00U\x00\x00T\x00 \x00A\x00 \x00\x00\x00\x00LLI\x00\x18N\x00P\x00U\x00T\x00\x00 \x00B\x00 \x00\x00\x00\x00L&I\x00N\x00\x00P\x00U\x00T\x00\x00 \x00C\x00 \x00\x00\x00\x00l\x1cS\x00U\x00\x04M\x00 \x00 \x00 \x00\x00 \x00 \x00\x00\x00\x00^L\'<*-X>PRE\x01\x00\x11\x01\x00\x18\x00\x00\x00\x00\x00\x00\x00\x00A     \x00  \x00\x00A  \x00     \x00\x00\x00\'/-:\'/<\x7f-\x00\x00\x00\x00\x00\x00\x01\\\xf7'
        self.devices()[
            0].ping_response = b'\xf0\x00 2\x00\x0e\x04\x10\x04\x05\x05\x04\x04\x02\x02\x04\x02\x00\x00\x00\x00\x0e\x00\x00\xf7'
        for n, d in self.devices().items():
            new_ping = bytearray.fromhex("f0002032000e000111444358323439362d3020202020202020f7")
            new_ping[const.COMMAND_BYTE] = const.SEARCH_RESPONSE
            new_ping[const.ID_BYTE] = n
            d.ping_response = new_ping
            d.is_new = False

    def write(self, data):
        self.__protocol.write(data)

    def ping_all_async(self):
        self.__loop.call_soon_threadsafe(self.ping_all)

    def ping_all(self):
        self.__io_logger.debug(f"pinging all {len(self.__devices)} devices")
        for n, d in self.__devices.items():
            self.ping(n)
        self.__io_logger.debug(f"finished pinging")

    def resync_async(self):
        self.__loop.call_soon_threadsafe(self.resync)

    def resync(self):
        self.__logger.debug("resyncing...")
        self.__devices.clear()
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
            self.setup_dummy_data()
        self.__logger.info(f"stopped ultradrive thread")

    def connection_made(self):
        self.__logger.debug("ultradrive thread recieved connection_made")
        self.__scheduler.start()
        self.__scheduler.add_job(self.ping_all_async, 'interval', seconds=const.PING_INTEVAL)
        self.__scheduler.add_job(self.resync_async, 'interval', seconds=const.RESYNC_INTEVAL)
        atexit.register(self.stop)

    def exception_text(self, infix, actual: int, expected: int, packet):
        text = "received malformed response - " + infix + f" has wrong length {actual} instead of {expected - 1}"
        if self.__packet_logger.level > 10:  # 10 == DEBUG
            text = text + str(packet)
        return text

    def handle_packet(self, packet):
        self.__packet_logger.debug(f"handling packet {packet}")
        device_id = packet[const.ID_BYTE]
        command = packet[const.COMMAND_BYTE]
        self.__packet_logger.info(f"handling command {command} for device: {device_id}")
        if device_id not in self.__devices:
            self.__packet_logger.info(f"received command: {command} from unknown device_id: {device_id}")
            device = Device(device_id)
            self.__devices[device_id] = device
            self.__loop.call_soon_threadsafe(self.dump_device, device_id)
        else:
            device = self.__devices[device_id]

        if command is const.SEARCH_RESPONSE:
            if len(packet) is const.SEARCH_RESPONSE_LENGTH - 1:
                device.search_response[:] = packet
            else:
                raise RuntimeError(
                    self.exception_text("search response", len(packet), const.SEARCH_RESPONSE_LENGTH, packet))
        elif command is const.DUMP_RESPONSE:
            part = packet[const.PART_BYTE]
            if part is 0:
                if len(packet) is const.PART_0_LENGTH - 1:
                    device.dump0[:] = packet
                else:
                    raise RuntimeError(
                        self.exception_text("dump response #0", len(packet), const.PART_0_LENGTH, packet))
            elif part is 1:
                if len(packet) is const.PART_1_LENGTH - 1:
                    device.dump1[:] = packet
                    device.is_new = False
                else:
                    raise RuntimeError(
                        self.exception_text("dump response #1", len(packet), const.PART_1_LENGTH, packet))
            else:
                raise RuntimeError(f"received malformed response - dump part is not 0 or 1 but {part}")
        elif command is const.PING_RESPONSE:
            if len(packet) is const.PING_RESPONSE_LENGTH - 1:
                device.ping_response[:] = packet
            else:
                raise RuntimeError(
                    self.exception_text("ping response", len(packet), const.PING_RESPONSE_LENGTH, packet))
        elif command is const.DIRECT_COMMAND:
            return
            count = packet[const.PARAM_COUNT_BYTE]
            for i in range(count):
                offset = 4 * i
                channel = packet[const.CHANNEL_BYTE + offset]
                param = packet[const.PARAM_BYTE + offset]
                value_high = packet[const.VALUE_HI_BYTE + offset]
                value_low = packet[const.VALUE_LOW_BYTE + offset]
                if channel == 0:
                    self.patchBuffer(device_id, value_low, value_high,
                                     self.setupLocations[param - (11 if param <= 11 else 10)])
                elif channel <= 4:
                    self.patchBuffer(device_id, value_low, value_high, self.inputLocations[channel - 1][param - 2])
                elif channel <= 10:
                    self.patchBuffer(device_id, value_low, value_high, self.outputLocations[channel - 5][param - 2])
        else:
            raise RuntimeError(f"received malformed response - unrecognized command {command}")


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
        # with self.lock:
        while self.transport.serial.in_waiting > 0:
            pass
        self.__logger.debug(f"finnaly writing {data}")
        self.transport.write(data)
        blocked = False
        if self.transport.serial.in_waiting > 0:
            blocked = True
        self.__logger.debug(f"wrote {data}")
        return blocked

#
# void Ultradrive::processIncoming(unsigned long now) {
#   while (serial->available() > 0) {
#     readCommands(now);
#   }
#
#   if (isFirstRun) {
#     isFirstRun = false;
#     lastSearch = now;
#     return search();
#   }
#
#   if (now - lastSearch >= SEARCH_INTEVAL) {
#     lastSearch = now;
#     return search();
#   }
#
#   for (int i = 0; i < MAX_DEVICES; i++) {
#     Device* device = &devices[i];
#     if (device->isNew) {
#       device->isNew = false;
#       device->lastPing = now;
#       setTransmitMode(i);
#       return ping(i);
#     } else if (device->lastPong != 0 && now - device->lastPong < TIMEOUT_TIME) {
#       if (device->dumpStarted) {
#         device->dumpStarted = false;
#         return dump(i, 1);
#       } else if (now - device->lastPing >= PING_INTEVAL) {
#         device->lastPing = now;
#         return ping(i);
#       } else if (now - device->lastResync >= RESYNC_INTEVAL) {
#         device->invalidateSync = false;
#         device->lastResync = now;
#         return dump(i, 0);
#       }
#     } else if (device->lastPong != 0) {
#       device->lastPong = 0;
#     }
#   }
# }
#
# void Ultradrive::writeDevice(Response* res, int deviceId) {
#   res->write(devices[deviceId].dump0, PART_0_LENGTH);
#   res->write(devices[deviceId].dump1, PART_1_LENGTH);
#   res->write(devices[deviceId].pingResponse, PING_RESPONSE_LENGTH);
# }
#
# void Ultradrive::writeDevices(Response* res) {
#   for (int i = 0; i < MAX_DEVICES; i++) {
#     if (devices[i].lastPong) {
#       res->write(devices[i].searchResponse, SEARCH_RESPONSE_LENGTH);
#     }
#   }
# }
#
# void Ultradrive::processOutgoing(Request* req) {
#   if (int bytesRead = req->readBytesUntil(TERMINATOR, serverBuffer, PART_0_LENGTH)) {
#     serverBuffer[bytesRead++] = TERMINATOR;
#
#     if (!memcmp(serverBuffer, vendorHeader, 5)) {
#       int deviceId = serverBuffer[ID_BYTE];
#       int command = serverBuffer[COMMAND_BYTE];
#
#       if (command == DIRECT_COMMAND) {
#         devices[deviceId].invalidateSync = true;
#         int count = serverBuffer[PARAM_COUNT_BYTE];
#
#         for (int i = 0; i < count; i++) {
#           int offset = (4 * i);
#           int channel = serverBuffer[CHANNEL_BYTE + offset];
#           int param = serverBuffer[PARAM_BYTE + offset];
#           int valueHigh = serverBuffer[VALUE_HI_BYTE + offset];
#           int valueLow = serverBuffer[VALUE_LOW_BYTE + offset];
#
#           if (!channel) {
#             patchBuffer(deviceId, valueLow, valueHigh, setupLocations[param - (param <= 11 ? 2 : 10)]);
#           } else if (channel <= 4) {
#             patchBuffer(deviceId, valueLow, valueHigh, inputLocations[channel - 1][param - 2]);
#           } else if (channel <= 10) {
#             patchBuffer(deviceId, valueLow, valueHigh, outputLocations[channel - 5][param - 2]);
#           }
#         }
#
#         write(serverBuffer, bytesRead);
#       }
#     }
#   }
# }
#
# size_t Ultradrive::write(const uint8_t *buffer, size_t size) {
#   size_t written = 0;
#
#   if (requestToSend(1000)) {
#     written = serial->write(buffer, size);
#   }
#
#   endSend();
#
#   return written;
# }
#
# bool Ultradrive::requestToSend(int timeout) {
#   if (!flowControl) {
#     return true;
#   }
#
#   unsigned long start = millis();
#   digitalWrite(rtsPin, HIGH);
#
#   while (millis() - start <= timeout) {
#     if (digitalRead(ctsPin) == HIGH) {
#       return true;
#     }
#   }
#
#   return false;
# }
#
#
# void Ultradrive::endSend() {
#   if (flowControl) {
#     digitalWrite(rtsPin, LOW);
#   }
# }
#
# void Ultradrive::search() {
#   byte searchCommand[] = {0xF0, 0x00, 0x20, 0x32, 0x20, 0x0E, 0x40, TERMINATOR};
#   write(searchCommand, sizeof(searchCommand));
# }
#
# void Ultradrive::setTransmitMode(int deviceId) {
#   byte transmitModeCommand[] = {0xF0, 0x00, 0x20, 0x32, (byte)deviceId, 0x0E, 0x3F, 0x0C, 0x00, TERMINATOR};
#   write(transmitModeCommand, sizeof(transmitModeCommand));
# }
#
# void Ultradrive::ping( int deviceId) {
#   byte pingCommand[] = {0xF0, 0x00, 0x20, 0x32, (byte)deviceId, 0x0E, 0x44, 0x00, 0x00, TERMINATOR};
#   write(pingCommand, sizeof(pingCommand));
# }
#
# void Ultradrive::dump(int deviceId, int part) {
#   byte dumpCommand[] = {0xF0, 0x00, 0x20, 0x32, (byte)deviceId, 0x0E, 0x50, 0x01, 0x00, (byte)part, TERMINATOR};
#   write(dumpCommand, sizeof(dumpCommand));
# }
#
# void Ultradrive::readCommands(unsigned long now) {
#   byte b = serial->read();
#
#   if (b == COMMAND_START) {
#     readingCommand = true;
#     serialRead = 0;
#   }
#
#   if (readingCommand && (serialRead < PART_0_LENGTH)) {
#     serialBuffer[serialRead++] = b;
#   }
#
#   if (b == TERMINATOR) {
#     readingCommand = false;
#     byte vendorHeader[] = {0xF0, 0x00, 0x20, 0x32, 0x00};
#
#     if (!memcmp(serialBuffer, vendorHeader, 5)) {
#       int deviceId = serialBuffer[ID_BYTE];
#       int command = serialBuffer[COMMAND_BYTE];
#       Device* device = &devices[deviceId];
#
#       switch (command) {
#         case SEARCH_RESPONSE: {
#             if (serialRead == SEARCH_RESPONSE_LENGTH) {
#               memcpy(&device->searchResponse, serialBuffer, SEARCH_RESPONSE_LENGTH);
#
#               if (!devices[deviceId].lastPong) {
#                 device->isNew = true;
#               }
#             }
#
#             break;
#           }
#         case DUMP_RESPONSE: {
#             if (device->invalidateSync == true) {
#               serialRead = 0;
#               readingCommand = false;
#               break;
#             }
#
#             int part = serialBuffer[PART_BYTE];
#
#             if (part == 0) {
#               if (serialRead == PART_0_LENGTH) {
#                 memcpy(&device->dump0, serialBuffer, PART_0_LENGTH);
#                 device->dumpStarted = true;
#               }
#             } else if (part == 1) {
#               if (serialRead == PART_1_LENGTH) {
#                 memcpy(&device->dump1, serialBuffer, PART_1_LENGTH);
#               }
#             }
#
#             break;
#           }
#         case PING_RESPONSE: {
#             if (serialRead == PING_RESPONSE_LENGTH) {
#               memcpy(&device->pingResponse, serialBuffer, PING_RESPONSE_LENGTH);
#               device->lastPong = millis();
#             }
#
#             break;
#           }
#         case DIRECT_COMMAND: {
#             int count = serialBuffer[PARAM_COUNT_BYTE];
#
#             for (int i = 0; i < count; i++) {
#               int offset = (4 * i);
#               int channel = serialBuffer[CHANNEL_BYTE + offset];
#               int param = serialBuffer[PARAM_BYTE + offset];
#               int valueHigh = serialBuffer[VALUE_HI_BYTE + offset];
#               int valueLow = serialBuffer[VALUE_LOW_BYTE + offset];
#
#               if (!channel) {
#                 patchBuffer(deviceId, valueLow, valueHigh, setupLocations[param - (param <= 11 ? 2 : 10)]);
#               } else if (channel <= 4) {
#                 patchBuffer(deviceId, valueLow, valueHigh, inputLocations[channel - 1][param - 2]);
#               } else if (channel <= 10) {
#                 patchBuffer(deviceId, valueLow, valueHigh, outputLocations[channel - 5][param - 2]);
#               }
#             }
#
#             break;
#           }
#         default: {}
#       }
#     }
#   }
# }
#
# void Ultradrive::patchBuffer(int deviceId, int low, int high, DataLocation l) {
#   Device* device = &devices[deviceId];
#
#   if (l.low.part == 0) {
#     device->dump0[l.low.byte] = low;
#   } else if (l.low.part == 1) {
#     device->dump1[l.low.byte] = low;
#   }
#
#   if (l.middle.byte > 0) {
#     if (l.middle.part == 0) {
#       if (high & 1) {
#         device->dump0[l.middle.byte] |= (1u << l.middle.index);
#       } else {
#         device->dump0[l.middle.byte] &= ~(1u << l.middle.index);
#       }
#     } else if (l.middle.part == 1) {
#       if (high & 1) {
#         device->dump1[l.middle.byte] |= (1u << l.middle.index);
#       } else {
#         device->dump1[l.middle.byte] &= ~(1u << l.middle.index);
#       }
#     }
#   }
#
#   if (l.high.byte > 0) {
#     int highByte = high >> 1;
#     if (l.high.part == 0) {
#       device->dump0[l.high.byte] = highByte;
#     } else if (l.high.part == 1) {
#       device->dump1[l.high.byte] = highByte;
#     }
#   }
# }
#
# byte Ultradrive::vendorHeader[5] = {0xF0, 0x00, 0x20, 0x32, 0x00};
#
# DataLocation Ultradrive::setupLocations[22] =  {
#   {{0, 117}, { -1, -1, -1}, { -1, -1}},
#   {{0, 119}, { -1, -1, -1}, { -1, -1}},
#   {{0, 121}, { -1, -1, -1}, { -1, -1}},
#   {{0, 123}, { -1, -1, -1}, { -1, -1}},
#   {{0, 126}, { -1, -1, -1}, { -1, -1}},
#   {{0, 128}, { -1, -1, -1}, { -1, -1}},
#   {{0, 130}, { -1, -1, -1}, { -1, -1}},
#   {{0, 133}, { -1, -1, -1}, { -1, -1}},
#   {{0, 135}, { -1, -1, -1}, { -1, -1}},
#   {{0, 137}, { -1, -1, -1}, { -1, -1}},
#   {{0, 55}, { -1, -1, -1}, { -1, -1}},
#   {{0, 57}, { -1, -1, -1}, { -1, -1}},
#   {{0, 139}, {0, 140, 6}, {0, 141}},
#   {{0, 142}, {0, 148, 1}, {0, 143}},
#   {{0, 144}, {0, 148, 3}, {0, 145}}
# };
# DataLocation Ultradrive::inputLocations[4][62] =  {
#   {
#     {{0, 146}, {0, 148, 5}, {0, 147}},
#     {{0, 149}, { -1, -1, -1}, { -1, -1}},
#     {{0, 151}, { -1, -1, -1}, { -1, -1}},
#     {{0, 153}, {0, 156, 4}, {0, 154}},
#     {{0, 155}, { -1, -1, -1}, { -1, -1}},
#     {{0, 158}, { -1, -1, -1}, { -1, -1}},
#     {{0, 160}, { -1, -1, -1}, { -1, -1}},
#     {{0, 162}, { -1, -1, -1}, { -1, -1}},
#     {{0, 165}, {0, 172, 0}, { -1, -1}},
#     {{0, 167}, { -1, -1, -1}, { -1, -1}},
#     {{0, 169}, {0, 172, 4}, {0, 170}},
#     {{0, 171}, { -1, -1, -1}, { -1, -1}},
#     {{0, 174}, {0, 180, 1}, {0, 175}},
#     {{0, 176}, { -1, -1, -1}, { -1, -1}},
#     {{0, 178}, {0, 180, 5}, {0, 179}},
#     {{0, 181}, { -1, -1, -1}, { -1, -1}},
#     {{0, 183}, { -1, -1, -1}, { -1, -1}},
#     {{0, 185}, {0, 188, 4}, {0, 186}},
#     {{0, 187}, { -1, -1, -1}, { -1, -1}},
#     {{0, 190}, {0, 196, 1}, {0, 191}},
#     {{0, 192}, { -1, -1, -1}, { -1, -1}},
#     {{0, 194}, { -1, -1, -1}, { -1, -1}},
#     {{0, 197}, {0, 204, 0}, {0, 198}},
#     {{0, 199}, { -1, -1, -1}, { -1, -1}},
#     {{0, 201}, {0, 204, 4}, {0, 202}},
#     {{0, 203}, { -1, -1, -1}, { -1, -1}},
#     {{0, 206}, { -1, -1, -1}, { -1, -1}},
#     {{0, 208}, {0, 212, 3}, {0, 209}},
#     {{0, 210}, { -1, -1, -1}, { -1, -1}},
#     {{0, 213}, {0, 220, 0}, {0, 214}},
#     {{0, 215}, { -1, -1, -1}, { -1, -1}},
#     {{0, 217}, { -1, -1, -1}, { -1, -1}},
#     {{0, 219}, {0, 220, 6}, {0, 221}},
#     {{0, 222}, { -1, -1, -1}, { -1, -1}},
#     {{0, 224}, {0, 228, 3}, {0, 225}},
#     {{0, 226}, { -1, -1, -1}, { -1, -1}},
#     {{0, 229}, { -1, -1, -1}, { -1, -1}},
#     {{0, 231}, {0, 236, 2}, {0, 232}},
#     {{0, 233}, { -1, -1, -1}, { -1, -1}},
#     {{0, 235}, {0, 236, 6}, {0, 237}},
#     {{0, 238}, { -1, -1, -1}, { -1, -1}},
#     {{0, 240}, { -1, -1, -1}, { -1, -1}},
#     {{0, 242}, {0, 244, 5}, {0, 243}},
#     {{0, 245}, { -1, -1, -1}, { -1, -1}},
#     {{0, 247}, {0, 252, 2}, {0, 248}},
#     {{0, 249}, { -1, -1, -1}, { -1, -1}},
#     {{0, 251}, { -1, -1, -1}, { -1, -1}},
#     {{0, 254}, {0, 260, 1}, {0, 255}},
#     {{0, 256}, { -1, -1, -1}, { -1, -1}},
#     {{0, 258}, {0, 260, 5}, {0, 259}},
#     {{0, 261}, { -1, -1, -1}, { -1, -1}},
#     {{0, 263}, { -1, -1, -1}, { -1, -1}},
#     {{0, 265}, {0, 268, 4}, {0, 266}},
#     {{0, 267}, { -1, -1, -1}, { -1, -1}},
#     {{0, 270}, {0, 276, 1}, {0, 271}},
#     {{0, 272}, { -1, -1, -1}, { -1, -1}},
#     {{0, 274}, { -1, -1, -1}, { -1, -1}},
#     {{0, 277}, {0, 284, 0}, {0, 278}},
#     {{0, 279}, { -1, -1, -1}, { -1, -1}},
#     {{0, 281}, {0, 284, 4}, {0, 282}},
#     {{0, 283}, { -1, -1, -1}, { -1, -1}},
#     {{0, 286}, { -1, -1, -1}, { -1, -1}}
#   }, {
#     {{0, 288}, {0, 292, 3}, {0, 289}},
#     {{0, 290}, { -1, -1, -1}, { -1, -1}},
#     {{0, 293}, { -1, -1, -1}, { -1, -1}},
#     {{0, 295}, {0, 300, 2}, {0, 296}},
#     {{0, 297}, { -1, -1, -1}, { -1, -1}},
#     {{0, 299}, { -1, -1, -1}, { -1, -1}},
#     {{0, 302}, { -1, -1, -1}, { -1, -1}},
#     {{0, 304}, { -1, -1, -1}, { -1, -1}},
#     {{0, 306}, {0, 308, 5}, { -1, -1}},
#     {{0, 309}, { -1, -1, -1}, { -1, -1}},
#     {{0, 311}, {0, 316, 2}, {0, 312}},
#     {{0, 313}, { -1, -1, -1}, { -1, -1}},
#     {{0, 315}, {0, 316, 6}, {0, 317}},
#     {{0, 318}, { -1, -1, -1}, { -1, -1}},
#     {{0, 320}, {0, 324, 3}, {0, 321}},
#     {{0, 322}, { -1, -1, -1}, { -1, -1}},
#     {{0, 325}, { -1, -1, -1}, { -1, -1}},
#     {{0, 327}, {0, 332, 2}, {0, 328}},
#     {{0, 329}, { -1, -1, -1}, { -1, -1}},
#     {{0, 331}, {0, 332, 6}, {0, 333}},
#     {{0, 334}, { -1, -1, -1}, { -1, -1}},
#     {{0, 336}, { -1, -1, -1}, { -1, -1}},
#     {{0, 338}, {0, 340, 5}, {0, 339}},
#     {{0, 341}, { -1, -1, -1}, { -1, -1}},
#     {{0, 343}, {0, 348, 2}, {0, 344}},
#     {{0, 345}, { -1, -1, -1}, { -1, -1}},
#     {{0, 347}, { -1, -1, -1}, { -1, -1}},
#     {{0, 350}, {0, 356, 1}, {0, 351}},
#     {{0, 352}, { -1, -1, -1}, { -1, -1}},
#     {{0, 354}, {0, 356, 5}, {0, 355}},
#     {{0, 357}, { -1, -1, -1}, { -1, -1}},
#     {{0, 359}, { -1, -1, -1}, { -1, -1}},
#     {{0, 361}, {0, 364, 4}, {0, 362}},
#     {{0, 363}, { -1, -1, -1}, { -1, -1}},
#     {{0, 366}, {0, 372, 1}, {0, 367}},
#     {{0, 368}, { -1, -1, -1}, { -1, -1}},
#     {{0, 370}, { -1, -1, -1}, { -1, -1}},
#     {{0, 373}, {0, 380, 0}, {0, 374}},
#     {{0, 375}, { -1, -1, -1}, { -1, -1}},
#     {{0, 377}, {0, 380, 4}, {0, 378}},
#     {{0, 379}, { -1, -1, -1}, { -1, -1}},
#     {{0, 382}, { -1, -1, -1}, { -1, -1}},
#     {{0, 384}, {0, 388, 3}, {0, 385}},
#     {{0, 386}, { -1, -1, -1}, { -1, -1}},
#     {{0, 389}, {0, 396, 0}, {0, 390}},
#     {{0, 391}, { -1, -1, -1}, { -1, -1}},
#     {{0, 393}, { -1, -1, -1}, { -1, -1}},
#     {{0, 395}, {0, 396, 6}, {0, 397}},
#     {{0, 398}, { -1, -1, -1}, { -1, -1}},
#     {{0, 400}, {0, 404, 3}, {0, 401}},
#     {{0, 402}, { -1, -1, -1}, { -1, -1}},
#     {{0, 405}, { -1, -1, -1}, { -1, -1}},
#     {{0, 407}, {0, 412, 2}, {0, 408}},
#     {{0, 409}, { -1, -1, -1}, { -1, -1}},
#     {{0, 411}, {0, 412, 6}, {0, 413}},
#     {{0, 414}, { -1, -1, -1}, { -1, -1}},
#     {{0, 416}, { -1, -1, -1}, { -1, -1}},
#     {{0, 418}, {0, 420, 5}, {0, 419}},
#     {{0, 421}, { -1, -1, -1}, { -1, -1}},
#     {{0, 423}, {0, 428, 2}, {0, 424}},
#     {{0, 425}, { -1, -1, -1}, { -1, -1}},
#     {{0, 427}, { -1, -1, -1}, { -1, -1}}
#   }, {
#     {{0, 430}, {0, 436, 1}, {0, 431}},
#     {{0, 432}, { -1, -1, -1}, { -1, -1}},
#     {{0, 434}, { -1, -1, -1}, { -1, -1}},
#     {{0, 437}, {0, 444, 0}, {0, 438}},
#     {{0, 439}, { -1, -1, -1}, { -1, -1}},
#     {{0, 441}, { -1, -1, -1}, { -1, -1}},
#     {{0, 443}, { -1, -1, -1}, { -1, -1}},
#     {{0, 446}, { -1, -1, -1}, { -1, -1}},
#     {{0, 448}, {0, 452, 3}, { -1, -1}},
#     {{0, 450}, { -1, -1, -1}, { -1, -1}},
#     {{0, 453}, {0, 460, 0}, {0, 454}},
#     {{0, 455}, { -1, -1, -1}, { -1, -1}},
#     {{0, 457}, {0, 460, 4}, {0, 458}},
#     {{0, 459}, { -1, -1, -1}, { -1, -1}},
#     {{0, 462}, {0, 468, 1}, {0, 463}},
#     {{0, 464}, { -1, -1, -1}, { -1, -1}},
#     {{0, 466}, { -1, -1, -1}, { -1, -1}},
#     {{0, 469}, {0, 476, 0}, {0, 470}},
#     {{0, 471}, { -1, -1, -1}, { -1, -1}},
#     {{0, 473}, {0, 476, 4}, {0, 474}},
#     {{0, 475}, { -1, -1, -1}, { -1, -1}},
#     {{0, 478}, { -1, -1, -1}, { -1, -1}},
#     {{0, 480}, {0, 484, 3}, {0, 481}},
#     {{0, 482}, { -1, -1, -1}, { -1, -1}},
#     {{0, 485}, {0, 492, 0}, {0, 486}},
#     {{0, 487}, { -1, -1, -1}, { -1, -1}},
#     {{0, 489}, { -1, -1, -1}, { -1, -1}},
#     {{0, 491}, {0, 492, 6}, {0, 493}},
#     {{0, 494}, { -1, -1, -1}, { -1, -1}},
#     {{0, 496}, {0, 500, 3}, {0, 497}},
#     {{0, 498}, { -1, -1, -1}, { -1, -1}},
#     {{0, 501}, { -1, -1, -1}, { -1, -1}},
#     {{0, 503}, {0, 508, 2}, {0, 504}},
#     {{0, 505}, { -1, -1, -1}, { -1, -1}},
#     {{0, 507}, {0, 508, 6}, {0, 509}},
#     {{0, 510}, { -1, -1, -1}, { -1, -1}},
#     {{0, 512}, { -1, -1, -1}, { -1, -1}},
#     {{0, 514}, {0, 516, 5}, {0, 515}},
#     {{0, 517}, { -1, -1, -1}, { -1, -1}},
#     {{0, 519}, {0, 524, 2}, {0, 520}},
#     {{0, 521}, { -1, -1, -1}, { -1, -1}},
#     {{0, 523}, { -1, -1, -1}, { -1, -1}},
#     {{0, 526}, {0, 532, 1}, {0, 527}},
#     {{0, 528}, { -1, -1, -1}, { -1, -1}},
#     {{0, 530}, {0, 532, 5}, {0, 531}},
#     {{0, 533}, { -1, -1, -1}, { -1, -1}},
#     {{0, 535}, { -1, -1, -1}, { -1, -1}},
#     {{0, 537}, {0, 540, 4}, {0, 538}},
#     {{0, 539}, { -1, -1, -1}, { -1, -1}},
#     {{0, 542}, {0, 548, 1}, {0, 543}},
#     {{0, 544}, { -1, -1, -1}, { -1, -1}},
#     {{0, 546}, { -1, -1, -1}, { -1, -1}},
#     {{0, 549}, {0, 556, 0}, {0, 550}},
#     {{0, 551}, { -1, -1, -1}, { -1, -1}},
#     {{0, 553}, {0, 556, 4}, {0, 554}},
#     {{0, 555}, { -1, -1, -1}, { -1, -1}},
#     {{0, 558}, { -1, -1, -1}, { -1, -1}},
#     {{0, 560}, {0, 564, 3}, {0, 561}},
#     {{0, 562}, { -1, -1, -1}, { -1, -1}},
#     {{0, 565}, {0, 572, 0}, {0, 566}},
#     {{0, 567}, { -1, -1, -1}, { -1, -1}},
#     {{0, 569}, { -1, -1, -1}, { -1, -1}}
#   }, {
#     {{0, 571}, {0, 572, 6}, {0, 573}},
#     {{0, 574}, { -1, -1, -1}, { -1, -1}},
#     {{0, 576}, { -1, -1, -1}, { -1, -1}},
#     {{0, 578}, {0, 580, 5}, {0, 579}},
#     {{0, 581}, { -1, -1, -1}, { -1, -1}},
#     {{0, 583}, { -1, -1, -1}, { -1, -1}},
#     {{0, 585}, { -1, -1, -1}, { -1, -1}},
#     {{0, 587}, { -1, -1, -1}, { -1, -1}},
#     {{0, 590}, {0, 596, 1}, { -1, -1}},
#     {{0, 592}, { -1, -1, -1}, { -1, -1}},
#     {{0, 594}, {0, 596, 5}, {0, 595}},
#     {{0, 597}, { -1, -1, -1}, { -1, -1}},
#     {{0, 599}, {0, 604, 2}, {0, 600}},
#     {{0, 601}, { -1, -1, -1}, { -1, -1}},
#     {{0, 603}, {0, 604, 6}, {0, 605}},
#     {{0, 606}, { -1, -1, -1}, { -1, -1}},
#     {{0, 608}, { -1, -1, -1}, { -1, -1}},
#     {{0, 610}, {0, 612, 5}, {0, 611}},
#     {{0, 613}, { -1, -1, -1}, { -1, -1}},
#     {{0, 615}, {0, 620, 2}, {0, 616}},
#     {{0, 617}, { -1, -1, -1}, { -1, -1}},
#     {{0, 619}, { -1, -1, -1}, { -1, -1}},
#     {{0, 622}, {0, 628, 1}, {0, 623}},
#     {{0, 624}, { -1, -1, -1}, { -1, -1}},
#     {{0, 626}, {0, 628, 5}, {0, 627}},
#     {{0, 629}, { -1, -1, -1}, { -1, -1}},
#     {{0, 631}, { -1, -1, -1}, { -1, -1}},
#     {{0, 633}, {0, 636, 4}, {0, 634}},
#     {{0, 635}, { -1, -1, -1}, { -1, -1}},
#     {{0, 638}, {0, 644, 1}, {0, 639}},
#     {{0, 640}, { -1, -1, -1}, { -1, -1}},
#     {{0, 642}, { -1, -1, -1}, { -1, -1}},
#     {{0, 645}, {0, 652, 0}, {0, 646}},
#     {{0, 647}, { -1, -1, -1}, { -1, -1}},
#     {{0, 649}, {0, 652, 4}, {0, 650}},
#     {{0, 651}, { -1, -1, -1}, { -1, -1}},
#     {{0, 654}, { -1, -1, -1}, { -1, -1}},
#     {{0, 656}, {0, 660, 3}, {0, 657}},
#     {{0, 658}, { -1, -1, -1}, { -1, -1}},
#     {{0, 661}, {0, 668, 0}, {0, 662}},
#     {{0, 663}, { -1, -1, -1}, { -1, -1}},
#     {{0, 665}, { -1, -1, -1}, { -1, -1}},
#     {{0, 667}, {0, 668, 6}, {0, 669}},
#     {{0, 670}, { -1, -1, -1}, { -1, -1}},
#     {{0, 672}, {0, 676, 3}, {0, 673}},
#     {{0, 674}, { -1, -1, -1}, { -1, -1}},
#     {{0, 677}, { -1, -1, -1}, { -1, -1}},
#     {{0, 679}, {0, 684, 2}, {0, 680}},
#     {{0, 681}, { -1, -1, -1}, { -1, -1}},
#     {{0, 683}, {0, 684, 6}, {0, 685}},
#     {{0, 686}, { -1, -1, -1}, { -1, -1}},
#     {{0, 688}, { -1, -1, -1}, { -1, -1}},
#     {{0, 690}, {0, 692, 5}, {0, 691}},
#     {{0, 693}, { -1, -1, -1}, { -1, -1}},
#     {{0, 695}, {0, 700, 2}, {0, 696}},
#     {{0, 697}, { -1, -1, -1}, { -1, -1}},
#     {{0, 699}, { -1, -1, -1}, { -1, -1}},
#     {{0, 702}, {0, 708, 1}, {0, 703}},
#     {{0, 704}, { -1, -1, -1}, { -1, -1}},
#     {{0, 706}, {0, 708, 5}, {0, 707}},
#     {{0, 709}, { -1, -1, -1}, { -1, -1}},
#     {{0, 711}, { -1, -1, -1}, { -1, -1}}
#   }
# };
# DataLocation Ultradrive::outputLocations[6][74] =  {
#   {
#     {{0, 713}, {0, 716, 4}, {0, 714}},
#     {{0, 715}, { -1, -1, -1}, { -1, -1}},
#     {{0, 718}, { -1, -1, -1}, { -1, -1}},
#     {{0, 720}, {0, 724, 3}, {0, 721}},
#     {{0, 722}, { -1, -1, -1}, { -1, -1}},
#     {{0, 725}, { -1, -1, -1}, { -1, -1}},
#     {{0, 727}, { -1, -1, -1}, { -1, -1}},
#     {{0, 729}, { -1, -1, -1}, { -1, -1}},
#     {{0, 731}, {0, 732, 6}, { -1, -1}},
#     {{0, 734}, { -1, -1, -1}, { -1, -1}},
#     {{0, 736}, {0, 740, 3}, {0, 737}},
#     {{0, 738}, { -1, -1, -1}, { -1, -1}},
#     {{0, 741}, {0, 748, 0}, {0, 742}},
#     {{0, 743}, { -1, -1, -1}, { -1, -1}},
#     {{0, 745}, {0, 748, 4}, {0, 746}},
#     {{0, 747}, { -1, -1, -1}, { -1, -1}},
#     {{0, 750}, { -1, -1, -1}, { -1, -1}},
#     {{0, 752}, {0, 756, 3}, {0, 753}},
#     {{0, 754}, { -1, -1, -1}, { -1, -1}},
#     {{0, 757}, {0, 764, 0}, {0, 758}},
#     {{0, 759}, { -1, -1, -1}, { -1, -1}},
#     {{0, 761}, { -1, -1, -1}, { -1, -1}},
#     {{0, 763}, {0, 764, 6}, {0, 765}},
#     {{0, 766}, { -1, -1, -1}, { -1, -1}},
#     {{0, 768}, {0, 772, 3}, {0, 769}},
#     {{0, 770}, { -1, -1, -1}, { -1, -1}},
#     {{0, 773}, { -1, -1, -1}, { -1, -1}},
#     {{0, 775}, {0, 780, 2}, {0, 776}},
#     {{0, 777}, { -1, -1, -1}, { -1, -1}},
#     {{0, 779}, {0, 780, 6}, {0, 781}},
#     {{0, 782}, { -1, -1, -1}, { -1, -1}},
#     {{0, 784}, { -1, -1, -1}, { -1, -1}},
#     {{0, 786}, {0, 788, 5}, {0, 787}},
#     {{0, 789}, { -1, -1, -1}, { -1, -1}},
#     {{0, 791}, {0, 796, 2}, {0, 792}},
#     {{0, 793}, { -1, -1, -1}, { -1, -1}},
#     {{0, 795}, { -1, -1, -1}, { -1, -1}},
#     {{0, 798}, {0, 804, 1}, {0, 799}},
#     {{0, 800}, { -1, -1, -1}, { -1, -1}},
#     {{0, 802}, {0, 804, 5}, {0, 803}},
#     {{0, 805}, { -1, -1, -1}, { -1, -1}},
#     {{0, 807}, { -1, -1, -1}, { -1, -1}},
#     {{0, 809}, {0, 812, 4}, {0, 810}},
#     {{0, 811}, { -1, -1, -1}, { -1, -1}},
#     {{0, 814}, {0, 820, 1}, {0, 815}},
#     {{0, 816}, { -1, -1, -1}, { -1, -1}},
#     {{0, 818}, { -1, -1, -1}, { -1, -1}},
#     {{0, 821}, {0, 828, 0}, {0, 822}},
#     {{0, 823}, { -1, -1, -1}, { -1, -1}},
#     {{0, 825}, {0, 828, 4}, {0, 826}},
#     {{0, 827}, { -1, -1, -1}, { -1, -1}},
#     {{0, 830}, { -1, -1, -1}, { -1, -1}},
#     {{0, 832}, {0, 836, 3}, {0, 833}},
#     {{0, 834}, { -1, -1, -1}, { -1, -1}},
#     {{0, 837}, {0, 844, 0}, {0, 838}},
#     {{0, 839}, { -1, -1, -1}, { -1, -1}},
#     {{0, 841}, { -1, -1, -1}, { -1, -1}},
#     {{0, 843}, {0, 844, 6}, {0, 845}},
#     {{0, 846}, { -1, -1, -1}, { -1, -1}},
#     {{0, 848}, {0, 852, 3}, {0, 849}},
#     {{0, 850}, { -1, -1, -1}, { -1, -1}},
#     {{0, 853}, { -1, -1, -1}, { -1, -1}},
#     {{0, 855}, { -1, -1, -1}, { -1, -1}},
#     {{0, 857}, { -1, -1, -1}, { -1, -1}},
#     {{0, 859}, { -1, -1, -1}, { -1, -1}},
#     {{0, 862}, {0, 868, 1}, {0, 863}},
#     {{0, 864}, { -1, -1, -1}, { -1, -1}},
#     {{0, 866}, {0, 868, 5}, {0, 867}},
#     {{0, 869}, { -1, -1, -1}, { -1, -1}},
#     {{0, 871}, {0, 876, 2}, { -1, -1}},
#     {{0, 873}, {0, 876, 4}, { -1, -1}},
#     {{0, 875}, { -1, -1, -1}, { -1, -1}},
#     {{0, 878}, { -1, -1, -1}, { -1, -1}},
#     {{0, 880}, {0, 884, 3}, {0, 881}}
#   }, {
#     {{0, 882}, {0, 884, 5}, {0, 883}},
#     {{0, 885}, { -1, -1, -1}, { -1, -1}},
#     {{0, 887}, { -1, -1, -1}, { -1, -1}},
#     {{0, 889}, {0, 892, 4}, {0, 890}},
#     {{0, 891}, { -1, -1, -1}, { -1, -1}},
#     {{0, 894}, { -1, -1, -1}, { -1, -1}},
#     {{0, 896}, { -1, -1, -1}, { -1, -1}},
#     {{0, 898}, { -1, -1, -1}, { -1, -1}},
#     {{0, 901}, {0, 908, 0}, { -1, -1}},
#     {{0, 903}, { -1, -1, -1}, { -1, -1}},
#     {{0, 905}, {0, 908, 4}, {0, 906}},
#     {{0, 907}, { -1, -1, -1}, { -1, -1}},
#     {{0, 910}, {0, 916, 1}, {0, 911}},
#     {{0, 912}, { -1, -1, -1}, { -1, -1}},
#     {{0, 914}, {0, 916, 5}, {0, 915}},
#     {{0, 917}, { -1, -1, -1}, { -1, -1}},
#     {{0, 919}, { -1, -1, -1}, { -1, -1}},
#     {{0, 921}, {0, 924, 4}, {0, 922}},
#     {{0, 923}, { -1, -1, -1}, { -1, -1}},
#     {{0, 926}, {0, 932, 1}, {0, 927}},
#     {{0, 928}, { -1, -1, -1}, { -1, -1}},
#     {{0, 930}, { -1, -1, -1}, { -1, -1}},
#     {{0, 933}, {0, 940, 0}, {0, 934}},
#     {{0, 935}, { -1, -1, -1}, { -1, -1}},
#     {{0, 937}, {0, 940, 4}, {0, 938}},
#     {{0, 939}, { -1, -1, -1}, { -1, -1}},
#     {{0, 942}, { -1, -1, -1}, { -1, -1}},
#     {{0, 944}, {0, 948, 3}, {0, 945}},
#     {{0, 946}, { -1, -1, -1}, { -1, -1}},
#     {{0, 949}, {0, 956, 0}, {0, 950}},
#     {{0, 951}, { -1, -1, -1}, { -1, -1}},
#     {{0, 953}, { -1, -1, -1}, { -1, -1}},
#     {{0, 955}, {0, 956, 6}, {0, 957}},
#     {{0, 958}, { -1, -1, -1}, { -1, -1}},
#     {{0, 960}, {0, 964, 3}, {0, 961}},
#     {{0, 962}, { -1, -1, -1}, { -1, -1}},
#     {{0, 965}, { -1, -1, -1}, { -1, -1}},
#     {{0, 967}, {0, 972, 2}, {0, 968}},
#     {{0, 969}, { -1, -1, -1}, { -1, -1}},
#     {{0, 971}, {0, 972, 6}, {0, 973}},
#     {{0, 974}, { -1, -1, -1}, { -1, -1}},
#     {{0, 976}, { -1, -1, -1}, { -1, -1}},
#     {{0, 978}, {0, 980, 5}, {0, 979}},
#     {{0, 981}, { -1, -1, -1}, { -1, -1}},
#     {{0, 983}, {0, 988, 2}, {0, 984}},
#     {{0, 985}, { -1, -1, -1}, { -1, -1}},
#     {{0, 987}, { -1, -1, -1}, { -1, -1}},
#     {{0, 990}, {0, 996, 1}, {0, 991}},
#     {{0, 992}, { -1, -1, -1}, { -1, -1}},
#     {{0, 994}, {0, 996, 5}, {0, 995}},
#     {{0, 997}, { -1, -1, -1}, { -1, -1}},
#     {{0, 999}, { -1, -1, -1}, { -1, -1}},
#     {{0, 1001}, {0, 1004, 4}, {0, 1002}},
#     {{0, 1003}, { -1, -1, -1}, { -1, -1}},
#     {{0, 1006}, {0, 1012, 1}, {0, 1007}},
#     {{0, 1008}, { -1, -1, -1}, { -1, -1}},
#     {{0, 1010}, { -1, -1, -1}, { -1, -1}},
#     {{1, 13}, {1, 20, 0}, {1, 14}},
#     {{1, 15}, { -1, -1, -1}, { -1, -1}},
#     {{1, 17}, {1, 20, 4}, {1, 18}},
#     {{1, 19}, { -1, -1, -1}, { -1, -1}},
#     {{1, 22}, { -1, -1, -1}, { -1, -1}},
#     {{1, 24}, { -1, -1, -1}, { -1, -1}},
#     {{1, 26}, { -1, -1, -1}, { -1, -1}},
#     {{1, 29}, { -1, -1, -1}, { -1, -1}},
#     {{1, 31}, {1, 36, 2}, {1, 32}},
#     {{1, 33}, { -1, -1, -1}, { -1, -1}},
#     {{1, 35}, {1, 36, 6}, {1, 37}},
#     {{1, 38}, { -1, -1, -1}, { -1, -1}},
#     {{1, 40}, {1, 44, 3}, { -1, -1}},
#     {{1, 42}, {1, 44, 5}, { -1, -1}},
#     {{1, 45}, { -1, -1, -1}, { -1, -1}},
#     {{1, 47}, { -1, -1, -1}, { -1, -1}},
#     {{1, 49}, {1, 52, 4}, {1, 50}}
#   }, {
#     {{1, 51}, {1, 52, 6}, {1, 53}},
#     {{1, 54}, { -1, -1, -1}, { -1, -1}},
#     {{1, 56}, { -1, -1, -1}, { -1, -1}},
#     {{1, 58}, {1, 60, 5}, {1, 59}},
#     {{1, 61}, { -1, -1, -1}, { -1, -1}},
#     {{1, 63}, { -1, -1, -1}, { -1, -1}},
#     {{1, 65}, { -1, -1, -1}, { -1, -1}},
#     {{1, 67}, { -1, -1, -1}, { -1, -1}},
#     {{1, 70}, {1, 76, 1}, { -1, -1}},
#     {{1, 72}, { -1, -1, -1}, { -1, -1}},
#     {{1, 74}, {1, 76, 5}, {1, 75}},
#     {{1, 77}, { -1, -1, -1}, { -1, -1}},
#     {{1, 79}, {1, 84, 2}, {1, 80}},
#     {{1, 81}, { -1, -1, -1}, { -1, -1}},
#     {{1, 83}, {1, 84, 6}, {1, 85}},
#     {{1, 86}, { -1, -1, -1}, { -1, -1}},
#     {{1, 88}, { -1, -1, -1}, { -1, -1}},
#     {{1, 90}, {1, 92, 5}, {1, 91}},
#     {{1, 93}, { -1, -1, -1}, { -1, -1}},
#     {{1, 95}, {1, 100, 2}, {1, 96}},
#     {{1, 97}, { -1, -1, -1}, { -1, -1}},
#     {{1, 99}, { -1, -1, -1}, { -1, -1}},
#     {{1, 102}, {1, 108, 1}, {1, 103}},
#     {{1, 104}, { -1, -1, -1}, { -1, -1}},
#     {{1, 106}, {1, 108, 5}, {1, 107}},
#     {{1, 109}, { -1, -1, -1}, { -1, -1}},
#     {{1, 111}, { -1, -1, -1}, { -1, -1}},
#     {{1, 113}, {1, 116, 4}, {1, 114}},
#     {{1, 115}, { -1, -1, -1}, { -1, -1}},
#     {{1, 118}, {1, 124, 1}, {1, 119}},
#     {{1, 120}, { -1, -1, -1}, { -1, -1}},
#     {{1, 122}, { -1, -1, -1}, { -1, -1}},
#     {{1, 125}, {1, 132, 0}, {1, 126}},
#     {{1, 127}, { -1, -1, -1}, { -1, -1}},
#     {{1, 129}, {1, 132, 4}, {1, 130}},
#     {{1, 131}, { -1, -1, -1}, { -1, -1}},
#     {{1, 134}, { -1, -1, -1}, { -1, -1}},
#     {{1, 136}, {1, 140, 3}, {1, 137}},
#     {{1, 138}, { -1, -1, -1}, { -1, -1}},
#     {{1, 141}, {1, 148, 0}, {1, 142}},
#     {{1, 143}, { -1, -1, -1}, { -1, -1}},
#     {{1, 145}, { -1, -1, -1}, { -1, -1}},
#     {{1, 147}, {1, 148, 6}, {1, 149}},
#     {{1, 150}, { -1, -1, -1}, { -1, -1}},
#     {{1, 152}, {1, 156, 3}, {1, 153}},
#     {{1, 154}, { -1, -1, -1}, { -1, -1}},
#     {{1, 157}, { -1, -1, -1}, { -1, -1}},
#     {{1, 159}, {1, 164, 2}, {1, 160}},
#     {{1, 161}, { -1, -1, -1}, { -1, -1}},
#     {{1, 163}, {1, 164, 6}, {1, 165}},
#     {{1, 166}, { -1, -1, -1}, { -1, -1}},
#     {{1, 168}, { -1, -1, -1}, { -1, -1}},
#     {{1, 170}, {1, 172, 5}, {1, 171}},
#     {{1, 173}, { -1, -1, -1}, { -1, -1}},
#     {{1, 175}, {1, 180, 2}, {1, 176}},
#     {{1, 177}, { -1, -1, -1}, { -1, -1}},
#     {{1, 179}, { -1, -1, -1}, { -1, -1}},
#     {{1, 182}, {1, 188, 1}, {1, 183}},
#     {{1, 184}, { -1, -1, -1}, { -1, -1}},
#     {{1, 186}, {1, 188, 5}, {1, 187}},
#     {{1, 189}, { -1, -1, -1}, { -1, -1}},
#     {{1, 191}, { -1, -1, -1}, { -1, -1}},
#     {{1, 193}, { -1, -1, -1}, { -1, -1}},
#     {{1, 195}, { -1, -1, -1}, { -1, -1}},
#     {{1, 198}, { -1, -1, -1}, { -1, -1}},
#     {{1, 200}, {1, 204, 3}, {1, 201}},
#     {{1, 202}, { -1, -1, -1}, { -1, -1}},
#     {{1, 205}, {1, 212, 0}, {1, 206}},
#     {{1, 207}, { -1, -1, -1}, { -1, -1}},
#     {{1, 209}, {1, 212, 4}, { -1, -1}},
#     {{1, 211}, {1, 212, 6}, { -1, -1}},
#     {{1, 214}, { -1, -1, -1}, { -1, -1}},
#     {{1, 216}, { -1, -1, -1}, { -1, -1}},
#     {{1, 218}, {1, 220, 5}, {1, 219}}
#   }, {
#     {{1, 221}, {1, 228, 0}, {1, 222}},
#     {{1, 223}, { -1, -1, -1}, { -1, -1}},
#     {{1, 225}, { -1, -1, -1}, { -1, -1}},
#     {{1, 227}, {1, 228, 6}, {1, 229}},
#     {{1, 230}, { -1, -1, -1}, { -1, -1}},
#     {{1, 232}, { -1, -1, -1}, { -1, -1}},
#     {{1, 234}, { -1, -1, -1}, { -1, -1}},
#     {{1, 237}, { -1, -1, -1}, { -1, -1}},
#     {{1, 239}, {1, 244, 2}, { -1, -1}},
#     {{1, 241}, { -1, -1, -1}, { -1, -1}},
#     {{1, 243}, {1, 244, 6}, {1, 245}},
#     {{1, 246}, { -1, -1, -1}, { -1, -1}},
#     {{1, 248}, {1, 252, 3}, {1, 249}},
#     {{1, 250}, { -1, -1, -1}, { -1, -1}},
#     {{1, 253}, {1, 260, 0}, {1, 254}},
#     {{1, 255}, { -1, -1, -1}, { -1, -1}},
#     {{1, 257}, { -1, -1, -1}, { -1, -1}},
#     {{1, 259}, {1, 260, 6}, {1, 261}},
#     {{1, 262}, { -1, -1, -1}, { -1, -1}},
#     {{1, 264}, {1, 268, 3}, {1, 265}},
#     {{1, 266}, { -1, -1, -1}, { -1, -1}},
#     {{1, 269}, { -1, -1, -1}, { -1, -1}},
#     {{1, 271}, {1, 276, 2}, {1, 272}},
#     {{1, 273}, { -1, -1, -1}, { -1, -1}},
#     {{1, 275}, {1, 276, 6}, {1, 277}},
#     {{1, 278}, { -1, -1, -1}, { -1, -1}},
#     {{1, 280}, { -1, -1, -1}, { -1, -1}},
#     {{1, 282}, {1, 284, 5}, {1, 283}},
#     {{1, 285}, { -1, -1, -1}, { -1, -1}},
#     {{1, 287}, {1, 292, 2}, {1, 288}},
#     {{1, 289}, { -1, -1, -1}, { -1, -1}},
#     {{1, 291}, { -1, -1, -1}, { -1, -1}},
#     {{1, 294}, {1, 300, 1}, {1, 295}},
#     {{1, 296}, { -1, -1, -1}, { -1, -1}},
#     {{1, 298}, {1, 300, 5}, {1, 299}},
#     {{1, 301}, { -1, -1, -1}, { -1, -1}},
#     {{1, 303}, { -1, -1, -1}, { -1, -1}},
#     {{1, 305}, {1, 308, 4}, {1, 306}},
#     {{1, 307}, { -1, -1, -1}, { -1, -1}},
#     {{1, 310}, {1, 316, 1}, {1, 311}},
#     {{1, 312}, { -1, -1, -1}, { -1, -1}},
#     {{1, 314}, { -1, -1, -1}, { -1, -1}},
#     {{1, 317}, {1, 324, 0}, {1, 318}},
#     {{1, 319}, { -1, -1, -1}, { -1, -1}},
#     {{1, 321}, {1, 324, 4}, {1, 322}},
#     {{1, 323}, { -1, -1, -1}, { -1, -1}},
#     {{1, 326}, { -1, -1, -1}, { -1, -1}},
#     {{1, 328}, {1, 332, 3}, {1, 329}},
#     {{1, 330}, { -1, -1, -1}, { -1, -1}},
#     {{1, 333}, {1, 340, 0}, {1, 334}},
#     {{1, 335}, { -1, -1, -1}, { -1, -1}},
#     {{1, 337}, { -1, -1, -1}, { -1, -1}},
#     {{1, 339}, {1, 340, 6}, {1, 341}},
#     {{1, 342}, { -1, -1, -1}, { -1, -1}},
#     {{1, 344}, {1, 348, 3}, {1, 345}},
#     {{1, 346}, { -1, -1, -1}, { -1, -1}},
#     {{1, 349}, { -1, -1, -1}, { -1, -1}},
#     {{1, 351}, {1, 356, 2}, {1, 352}},
#     {{1, 353}, { -1, -1, -1}, { -1, -1}},
#     {{1, 355}, {1, 356, 6}, {1, 357}},
#     {{1, 358}, { -1, -1, -1}, { -1, -1}},
#     {{1, 360}, { -1, -1, -1}, { -1, -1}},
#     {{1, 362}, { -1, -1, -1}, { -1, -1}},
#     {{1, 365}, { -1, -1, -1}, { -1, -1}},
#     {{1, 367}, { -1, -1, -1}, { -1, -1}},
#     {{1, 369}, {1, 372, 4}, {1, 370}},
#     {{1, 371}, { -1, -1, -1}, { -1, -1}},
#     {{1, 374}, {1, 380, 1}, {1, 375}},
#     {{1, 376}, { -1, -1, -1}, { -1, -1}},
#     {{1, 378}, {1, 380, 5}, { -1, -1}},
#     {{1, 381}, {1, 388, 0}, { -1, -1}},
#     {{1, 383}, { -1, -1, -1}, { -1, -1}},
#     {{1, 385}, { -1, -1, -1}, { -1, -1}},
#     {{1, 387}, {1, 388, 6}, {1, 389}}
#   }, {
#     {{1, 390}, {1, 396, 1}, {1, 391}},
#     {{1, 392}, { -1, -1, -1}, { -1, -1}},
#     {{1, 394}, { -1, -1, -1}, { -1, -1}},
#     {{1, 397}, {1, 404, 0}, {1, 398}},
#     {{1, 399}, { -1, -1, -1}, { -1, -1}},
#     {{1, 401}, { -1, -1, -1}, { -1, -1}},
#     {{1, 403}, { -1, -1, -1}, { -1, -1}},
#     {{1, 406}, { -1, -1, -1}, { -1, -1}},
#     {{1, 408}, {1, 412, 3}, { -1, -1}},
#     {{1, 410}, { -1, -1, -1}, { -1, -1}},
#     {{1, 413}, {1, 420, 0}, {1, 414}},
#     {{1, 415}, { -1, -1, -1}, { -1, -1}},
#     {{1, 417}, {1, 420, 4}, {1, 418}},
#     {{1, 419}, { -1, -1, -1}, { -1, -1}},
#     {{1, 422}, {1, 428, 1}, {1, 423}},
#     {{1, 424}, { -1, -1, -1}, { -1, -1}},
#     {{1, 426}, { -1, -1, -1}, { -1, -1}},
#     {{1, 429}, {1, 436, 0}, {1, 430}},
#     {{1, 431}, { -1, -1, -1}, { -1, -1}},
#     {{1, 433}, {1, 436, 4}, {1, 434}},
#     {{1, 435}, { -1, -1, -1}, { -1, -1}},
#     {{1, 438}, { -1, -1, -1}, { -1, -1}},
#     {{1, 440}, {1, 444, 3}, {1, 441}},
#     {{1, 442}, { -1, -1, -1}, { -1, -1}},
#     {{1, 445}, {1, 452, 0}, {1, 446}},
#     {{1, 447}, { -1, -1, -1}, { -1, -1}},
#     {{1, 449}, { -1, -1, -1}, { -1, -1}},
#     {{1, 451}, {1, 452, 6}, {1, 453}},
#     {{1, 454}, { -1, -1, -1}, { -1, -1}},
#     {{1, 456}, {1, 460, 3}, {1, 457}},
#     {{1, 458}, { -1, -1, -1}, { -1, -1}},
#     {{1, 461}, { -1, -1, -1}, { -1, -1}},
#     {{1, 463}, {1, 468, 2}, {1, 464}},
#     {{1, 465}, { -1, -1, -1}, { -1, -1}},
#     {{1, 467}, {1, 468, 6}, {1, 469}},
#     {{1, 470}, { -1, -1, -1}, { -1, -1}},
#     {{1, 472}, { -1, -1, -1}, { -1, -1}},
#     {{1, 474}, {1, 476, 5}, {1, 475}},
#     {{1, 477}, { -1, -1, -1}, { -1, -1}},
#     {{1, 479}, {1, 484, 2}, {1, 480}},
#     {{1, 481}, { -1, -1, -1}, { -1, -1}},
#     {{1, 483}, { -1, -1, -1}, { -1, -1}},
#     {{1, 486}, {1, 492, 1}, {1, 487}},
#     {{1, 488}, { -1, -1, -1}, { -1, -1}},
#     {{1, 490}, {1, 492, 5}, {1, 491}},
#     {{1, 493}, { -1, -1, -1}, { -1, -1}},
#     {{1, 495}, { -1, -1, -1}, { -1, -1}},
#     {{1, 497}, {1, 500, 4}, {1, 498}},
#     {{1, 499}, { -1, -1, -1}, { -1, -1}},
#     {{1, 502}, {1, 508, 1}, {1, 503}},
#     {{1, 504}, { -1, -1, -1}, { -1, -1}},
#     {{1, 506}, { -1, -1, -1}, { -1, -1}},
#     {{1, 509}, {1, 516, 0}, {1, 510}},
#     {{1, 511}, { -1, -1, -1}, { -1, -1}},
#     {{1, 513}, {1, 516, 4}, {1, 514}},
#     {{1, 515}, { -1, -1, -1}, { -1, -1}},
#     {{1, 518}, { -1, -1, -1}, { -1, -1}},
#     {{1, 520}, {1, 524, 3}, {1, 521}},
#     {{1, 522}, { -1, -1, -1}, { -1, -1}},
#     {{1, 525}, {1, 532, 0}, {1, 526}},
#     {{1, 527}, { -1, -1, -1}, { -1, -1}},
#     {{1, 529}, { -1, -1, -1}, { -1, -1}},
#     {{1, 531}, { -1, -1, -1}, { -1, -1}},
#     {{1, 534}, { -1, -1, -1}, { -1, -1}},
#     {{1, 536}, { -1, -1, -1}, { -1, -1}},
#     {{1, 538}, {1, 540, 5}, {1, 539}},
#     {{1, 541}, { -1, -1, -1}, { -1, -1}},
#     {{1, 543}, {1, 548, 2}, {1, 544}},
#     {{1, 545}, { -1, -1, -1}, { -1, -1}},
#     {{1, 547}, {1, 548, 6}, { -1, -1}},
#     {{1, 550}, {1, 556, 1}, { -1, -1}},
#     {{1, 552}, { -1, -1, -1}, { -1, -1}},
#     {{1, 554}, { -1, -1, -1}, { -1, -1}},
#     {{1, 557}, {1, 564, 0}, {1, 558}}
#   }, {
#     {{1, 559}, {1, 564, 2}, {1, 560}},
#     {{1, 561}, { -1, -1, -1}, { -1, -1}},
#     {{1, 563}, { -1, -1, -1}, { -1, -1}},
#     {{1, 566}, {1, 572, 1}, {1, 567}},
#     {{1, 568}, { -1, -1, -1}, { -1, -1}},
#     {{1, 570}, { -1, -1, -1}, { -1, -1}},
#     {{1, 573}, { -1, -1, -1}, { -1, -1}},
#     {{1, 575}, { -1, -1, -1}, { -1, -1}},
#     {{1, 577}, {1, 580, 4}, { -1, -1}},
#     {{1, 579}, { -1, -1, -1}, { -1, -1}},
#     {{1, 582}, {1, 588, 1}, {1, 583}},
#     {{1, 584}, { -1, -1, -1}, { -1, -1}},
#     {{1, 586}, {1, 588, 5}, {1, 587}},
#     {{1, 589}, { -1, -1, -1}, { -1, -1}},
#     {{1, 591}, {1, 596, 2}, {1, 592}},
#     {{1, 593}, { -1, -1, -1}, { -1, -1}},
#     {{1, 595}, { -1, -1, -1}, { -1, -1}},
#     {{1, 598}, {1, 604, 1}, {1, 599}},
#     {{1, 600}, { -1, -1, -1}, { -1, -1}},
#     {{1, 602}, {1, 604, 5}, {1, 603}},
#     {{1, 605}, { -1, -1, -1}, { -1, -1}},
#     {{1, 607}, { -1, -1, -1}, { -1, -1}},
#     {{1, 609}, {1, 612, 4}, {1, 610}},
#     {{1, 611}, { -1, -1, -1}, { -1, -1}},
#     {{1, 614}, {1, 620, 1}, {1, 615}},
#     {{1, 616}, { -1, -1, -1}, { -1, -1}},
#     {{1, 618}, { -1, -1, -1}, { -1, -1}},
#     {{1, 621}, {1, 628, 0}, {1, 622}},
#     {{1, 623}, { -1, -1, -1}, { -1, -1}},
#     {{1, 625}, {1, 628, 4}, {1, 626}},
#     {{1, 627}, { -1, -1, -1}, { -1, -1}},
#     {{1, 630}, { -1, -1, -1}, { -1, -1}},
#     {{1, 632}, {1, 636, 3}, {1, 633}},
#     {{1, 634}, { -1, -1, -1}, { -1, -1}},
#     {{1, 637}, {1, 644, 0}, {1, 638}},
#     {{1, 639}, { -1, -1, -1}, { -1, -1}},
#     {{1, 641}, { -1, -1, -1}, { -1, -1}},
#     {{1, 643}, {1, 644, 6}, {1, 645}},
#     {{1, 646}, { -1, -1, -1}, { -1, -1}},
#     {{1, 648}, {1, 652, 3}, {1, 649}},
#     {{1, 650}, { -1, -1, -1}, { -1, -1}},
#     {{1, 653}, { -1, -1, -1}, { -1, -1}},
#     {{1, 655}, {1, 660, 2}, {1, 656}},
#     {{1, 657}, { -1, -1, -1}, { -1, -1}},
#     {{1, 659}, {1, 660, 6}, {1, 661}},
#     {{1, 662}, { -1, -1, -1}, { -1, -1}},
#     {{1, 664}, { -1, -1, -1}, { -1, -1}},
#     {{1, 666}, {1, 668, 5}, {1, 667}},
#     {{1, 669}, { -1, -1, -1}, { -1, -1}},
#     {{1, 671}, {1, 676, 2}, {1, 672}},
#     {{1, 673}, { -1, -1, -1}, { -1, -1}},
#     {{1, 675}, { -1, -1, -1}, { -1, -1}},
#     {{1, 678}, {1, 684, 1}, {1, 679}},
#     {{1, 680}, { -1, -1, -1}, { -1, -1}},
#     {{1, 682}, {1, 684, 5}, {1, 683}},
#     {{1, 685}, { -1, -1, -1}, { -1, -1}},
#     {{1, 687}, { -1, -1, -1}, { -1, -1}},
#     {{1, 689}, {1, 692, 4}, {1, 690}},
#     {{1, 691}, { -1, -1, -1}, { -1, -1}},
#     {{1, 694}, {1, 700, 1}, {1, 695}},
#     {{1, 696}, { -1, -1, -1}, { -1, -1}},
#     {{1, 698}, { -1, -1, -1}, { -1, -1}},
#     {{1, 701}, { -1, -1, -1}, { -1, -1}},
#     {{1, 703}, { -1, -1, -1}, { -1, -1}},
#     {{1, 705}, { -1, -1, -1}, { -1, -1}},
#     {{1, 707}, {1, 708, 6}, {1, 709}},
#     {{1, 710}, { -1, -1, -1}, { -1, -1}},
#     {{1, 712}, {1, 716, 3}, {1, 713}},
#     {{1, 714}, { -1, -1, -1}, { -1, -1}},
#     {{1, 717}, {1, 724, 0}, { -1, -1}},
#     {{1, 719}, {1, 724, 2}, { -1, -1}},
#     {{1, 721}, { -1, -1, -1}, { -1, -1}},
#     {{1, 723}, { -1, -1, -1}, { -1, -1}},
#     {{1, 726}, {1, 732, 1}, {1, 727}}
#   }
# };
