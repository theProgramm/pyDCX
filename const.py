BAUD_RATE = 38400
MAX_DEVICES = 16
FRONTEND_PATH = "static/duinoDCX_frontend/"

PING_INTEVAL = 1
#TIMEOUT_TIME = 2
#SEARCH_INTEVAL = 5
RESYNC_INTEVAL = 10

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

COMMAND_START = bytes([240])
TERMINATOR = bytes([247])
VENDOR_HEADER = b'\xF0\x00\x20\x32\x00'