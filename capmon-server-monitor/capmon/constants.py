import re

HEADER_V1 = [
    "type", "key", "name", "ip", "up", "dn", "tup", "tdn", "seen",
    "limit", "period", "enabled", "used", "pkey", "since", "day",
]
EXTRA = ["yup", "ydn", "mup", "mdn", "lup", "ldn", "wup", "wdn", "pup", "pdn"]
HEADER = HEADER_V1 + EXTRA
ACCEPTED_HEADERS = (HEADER_V1, HEADER_V1 + EXTRA[:2], HEADER_V1 + EXTRA[:6], HEADER)

PERIODS = frozenset({"none", "daily", "weekly", "monthly"})

DEFAULT_PORT = 8765
DEFAULT_WORKERS = 16
DEFAULT_MAX_ROUTERS = 256

MAX_BODY = 1024 * 1024
MAX_ROWS = 5000
MAX_BYTES = 10 ** 15
MAX_LIMIT = 9 * 10 ** 14
MAX_EPOCH = 4102444800

SOCKET_TIMEOUT = 10
REQUEST_DEADLINE = 20
FAIL_LIMIT = 10
FAIL_WINDOW = 300
FAIL_TRACKED = 10000
LOCK_STRIPES = 64
BACKUP_INTERVAL = 3600
STALE_TEMP_AGE = 3600
REPLACE_ATTEMPTS = 10
REPLACE_DELAY = 0.05

RE_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
RE_MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
RE_ADDR = re.compile(r"^[0-9a-f:.]{2,45}$")
RE_NAME = re.compile(r"^[A-Za-z0-9 ._-]{0,63}$")
RE_NUM = re.compile(r"^[0-9]{1,16}$")
RE_DAY = re.compile(r"^[0-9]{8}$")
RE_PKEY = re.compile(r"^[0-9]{1,8}$")
RE_TOKEN = re.compile(r"^[A-Za-z0-9._-]{16,128}$")
RE_LENGTH = re.compile(r"^[0-9]{1,8}$")
RE_HEX = re.compile(r"^[0-9a-f]{64}$")

RESERVED = frozenset(
    {"con", "prn", "aux", "nul"}
    | {"com%d" % i for i in range(1, 10)}
    | {"lpt%d" % i for i in range(1, 10)}
)
