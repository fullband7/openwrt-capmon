import csv
import io
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime

UNITS = ("B", "KB", "MB", "GB", "TB", "PB")
PERIODS = (
    ("total", "up", "dn", "All Time"),
    ("today", "tup", "tdn", "Today"),
    ("yesterday", "yup", "ydn", "Yesterday"),
    ("lastweek", "pup", "pdn", "Last Week"),
    ("lastmonth", "lup", "ldn", "Last Month"),
)
PERIOD_INDEX = {entry[0]: index for index, entry in enumerate(PERIODS)}
RENEWS = {"daily": "Every day", "weekly": "Every week", "monthly": "Every month"}
RENEWS_DEFAULT = "Never (reset manually)"
STATES = {"ok": "Active", "blocked": "Blocked", "off": "Disabled"}
ONLINE_WINDOW = 120
SYNC_WINDOW = 150
LOW_PERCENT = 20.0
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_ROWS = 5000
MAX_TEXT = 64
RE_MAC = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
RE_UNSAFE = re.compile("[\x00-\x1f\x7f-\x9f\u061c\u200b-\u200f\u2028-\u202e\u2060-\u206f\ufeff\ufff9-\ufffb]")


def clean(value, limit=MAX_TEXT):
    return RE_UNSAFE.sub("", value or "").strip()[:limit]


def number(value):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return 0
    return result if result > 0 else 0


def fmt_bytes(value):
    size = float(number(value))
    unit = 0
    while size >= 1024 and unit < len(UNITS) - 1:
        size /= 1024
        unit += 1
    if unit == 0 or size >= 100:
        return "%d %s" % (int(size), UNITS[unit])
    text = "%.*f" % (1 if size >= 10 else 2, size)
    return ("99.9" if float(text) >= 100 else text) + " " + UNITS[unit]


def when(stamp):
    if stamp <= 0:
        return "Never"
    moment = datetime.fromtimestamp(stamp)
    hour = moment.hour % 12 or 12
    return "%d/%d/%d, %d:%02d:%02d %s" % (
        moment.month, moment.day, moment.year, hour, moment.minute, moment.second,
        "AM" if moment.hour < 12 else "PM",
    )


@dataclass(frozen=True, slots=True)
class Client:
    key: str
    name: str
    ip: str
    seen: int
    usage: tuple

    @property
    def router(self):
        return self.key == "router"

    @property
    def mac(self):
        return self.key if RE_MAC.match(self.key) else "-"

    @property
    def label(self):
        if self.router:
            return "OpenWrt"
        return self.name if self.name not in ("", "-") else "Unknown device"


@dataclass(frozen=True, slots=True)
class Plan:
    mac: str
    name: str
    limit: int
    period: str
    enabled: bool
    used: int
    pkey: str

    @property
    def exceeded(self):
        return self.limit > 0 and self.used >= self.limit

    @property
    def percent(self):
        return min(100.0, self.used / self.limit * 100) if self.limit > 0 else 0.0

    @property
    def state(self):
        if not self.enabled:
            return "off"
        return "blocked" if self.exceeded else "ok"


@dataclass(frozen=True, slots=True)
class Snapshot:
    router: str
    since: int
    clients: tuple
    plans: tuple

    def client(self, mac):
        for item in self.clients:
            if item.key == mac:
                return item
        return None


def parse(text, router):
    clients = []
    plans = []
    since = 0
    for row in csv.DictReader(io.StringIO(text)):
        if len(clients) + len(plans) >= MAX_ROWS:
            break
        kind = row.get("type")
        key = clean(row.get("key"))
        if kind == "meta":
            since = number(row.get("since"))
        elif kind == "client" and key:
            usage = tuple(
                (number(row.get(up)), number(row.get(dn))) for _, up, dn, _ in PERIODS
            )
            clients.append(
                Client(key, clean(row.get("name")), clean(row.get("ip"), 45),
                       number(row.get("seen")), usage)
            )
        elif kind == "plan" and key:
            plans.append(
                Plan(key, clean(row.get("name")), number(row.get("limit")),
                     clean(row.get("period")) or "none", row.get("enabled") == "1",
                     number(row.get("used")), clean(row.get("pkey"), 8))
            )
    return Snapshot(router, since, tuple(clients), tuple(plans))


def read_snapshot(path, router):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    try:
        with os.fdopen(os.open(path, flags), "rb") as handle:
            raw = handle.read(MAX_FILE_BYTES + 1)
        if len(raw) > MAX_FILE_BYTES:
            return None
        return parse(raw.decode("utf-8"), router)
    except (OSError, UnicodeDecodeError, csv.Error):
        return None


class Store:
    def __init__(self, directory):
        self.directory = directory
        self.latest = 0.0
        self._cache = {}

    def scan(self):
        found = {}
        latest = 0.0
        try:
            with os.scandir(self.directory) as entries:
                files = [
                    e for e in entries
                    if e.name.endswith(".csv") and e.is_file(follow_symlinks=False)
                ]
            for entry in files:
                info = entry.stat(follow_symlinks=False)
                latest = max(latest, info.st_mtime)
                stamp = (info.st_mtime_ns, info.st_size)
                cached = self._cache.get(entry.name)
                if cached and cached[0] == stamp:
                    snapshot = cached[1]
                else:
                    snapshot = read_snapshot(entry.path, entry.name[:-4])
                    self._cache[entry.name] = (stamp, snapshot)
                if snapshot is not None:
                    found[snapshot.router] = snapshot
        except OSError:
            self._cache.clear()
            self.latest = 0.0
            return {}
        self.latest = latest
        self._cache = {k: v for k, v in self._cache.items() if k[:-4] in found}
        return dict(sorted(found.items()))


@dataclass(frozen=True, slots=True)
class Row:
    online: bool
    router: bool
    name: str
    ip: str
    mac: str
    down: str
    up: str
    total: str
    tip: str


@dataclass(frozen=True, slots=True)
class StatsView:
    down: str
    up: str
    total: str
    count: str
    rows: tuple
    since: str
    period: str


def stats_view(snapshot, period, now=None):
    now = time.time() if now is None else now
    index = PERIOD_INDEX[period]
    picked = []
    down = up = 0
    for client in snapshot.clients:
        sent, received = client.usage[index]
        up += sent
        down += received
        if period != "total" and sent + received == 0:
            continue
        picked.append((sent + received, client, sent, received))
    picked.sort(key=lambda item: -item[0])
    rows = []
    for total, client, sent, received in picked:
        online = client.seen > 0 and now - client.seen <= ONLINE_WINDOW
        rows.append(
            Row(online, client.router, client.label, client.ip or "-", client.mac,
                fmt_bytes(received), fmt_bytes(sent), fmt_bytes(total),
                "Active now" if online else "Last seen: " + when(client.seen))
        )
    return StatsView(fmt_bytes(down), fmt_bytes(up), fmt_bytes(down + up), str(len(rows)),
                     tuple(rows), "Tracking since: " + when(snapshot.since), period)


def plan_label(snapshot, plan):
    client = snapshot.client(plan.mac)
    if plan.name:
        return plan.name
    if client is not None and client.name not in ("", "-"):
        return client.name
    return "Unknown device"


@dataclass(frozen=True, slots=True)
class Card:
    name: str
    ip: str
    mac: str
    state: str
    tone: str
    remaining: float
    used_text: str
    percent_text: str
    left_text: str
    renews: str


@dataclass(frozen=True, slots=True)
class AclView:
    active: str
    blocked: str
    blocked_count: int
    usage: str
    cards: tuple


def _order(plan):
    return {"blocked": 0, "ok": 1, "off": 2}[plan.state]


def acl_view(snapshot):
    ordered = sorted(
        snapshot.plans,
        key=lambda p: (_order(p), -p.percent, plan_label(snapshot, p).lower()),
    )
    active = blocked = used = 0
    cards = []
    for plan in snapshot.plans:
        if plan.enabled:
            active += 1
            used += plan.used
            blocked += plan.exceeded
    for plan in ordered:
        client = snapshot.client(plan.mac)
        percent = plan.percent
        state = plan.state
        tone = "over" if state == "blocked" or percent >= 90 else "warn" if percent >= 70 else "ok"
        cards.append(
            Card(plan_label(snapshot, plan), (client.ip if client else "") or "-", plan.mac,
                 state, tone, 100.0 - percent,
                 "%s of %s used" % (fmt_bytes(plan.used), fmt_bytes(plan.limit)),
                 ("%.0f%%" if percent >= 10 else "%.1f%%") % percent,
                 "%s left" % fmt_bytes(max(0, plan.limit - plan.used)),
                 RENEWS.get(plan.period, RENEWS_DEFAULT))
        )
    return AclView(str(active), str(blocked), blocked, fmt_bytes(used), tuple(cards))


@dataclass(frozen=True, slots=True)
class ConnectionView:
    url: str
    token: str
    token_hint: str
    pin: str
    pin_hint: str
    error: str
    blocked: str


def connection_view(info):
    url = "%s://%s:%d" % (info.scheme, info.address, info.port) if info.address and info.port else ""
    return ConnectionView(
        url,
        info.token,
        "Stored hashed, start with --reset-token to issue a new one",
        info.pin,
        "TLS is disabled" if info.scheme == "http" else "Unavailable",
        info.error,
        info.blocked,
    )
