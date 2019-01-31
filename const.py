BAUD_RATE = 38400
MAX_DEVICES = 16
FRONTEND_PATH = "static/duinoDCX_frontend/"

PING_INTEVAL = 500
TIMEOUT_TIME = 5000
SEARCH_INTERVAL = 1000

SEARCH_RESPONSE_LENGTH = 26
PING_RESPONSE_LENGTH = 25
PART_0_LENGTH = 1015
PART_1_LENGTH = 911

SEARCH_RESPONSE = 0
PING_RESPONSE = 4
DUMP_RESPONSE = 16
DIRECT_COMMAND = 32

ID_BYTE = 4
COMMAND_BYTE = 6
PARAM_COUNT_BYTE = 7
CHANNEL_BYTE = 8
PARAM_BYTE = 9
DUMP_PART_BYTE = 9
VALUE_HI_BYTE = 10
VALUE_LOW_BYTE = 11
PART_BYTE = 12

COMMAND_START: bytes = bytes([240])
TERMINATOR: bytes = bytes([247])
TERMINATOR_INT: int = int.from_bytes(TERMINATOR, "big")
VENDOR_HEADER: bytes = b'\xF0\x00\x20\x32'

PORT = "/dev/ttyS0"
