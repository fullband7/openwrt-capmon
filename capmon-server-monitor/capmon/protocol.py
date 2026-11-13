import csv
import io
import ipaddress
from datetime import datetime

from .constants import (
    ACCEPTED_HEADERS,
    EXTRA,
    HEADER,
    MAX_BYTES,
    MAX_EPOCH,
    MAX_LIMIT,
    MAX_ROWS,
    PERIODS,
    RE_ADDR,
    RE_DAY,
    RE_ID,
    RE_MAC,
    RE_NAME,
    RE_NUM,
    RE_PKEY,
    RESERVED,
)


class RowError(ValueError):
    pass


def valid_router_id(router_id):
    return (
        isinstance(router_id, str)
        and bool(RE_ID.match(router_id))
        and router_id.lower() not in RESERVED
    )


def _number(value, label, ceiling):
    if not RE_NUM.match(value) or int(value) > ceiling:
        raise RowError("invalid " + label)
    return str(int(value))


def _name(value):
    if not RE_NAME.match(value):
        raise RowError("invalid name")
    if value.startswith("-") and value != "-":
        return value.lstrip("-") or "-"
    return value


def _address(value, label):
    if not RE_ADDR.match(value):
        raise RowError("invalid " + label)
    try:
        ipaddress.ip_address(value)
    except ValueError:
        raise RowError("invalid " + label) from None
    return value


def _meta(fields, router_id):
    if fields["key"] != router_id:
        raise RowError("invalid key")
    try:
        if not RE_DAY.match(fields["day"]):
            raise ValueError
        datetime.strptime(fields["day"], "%Y%m%d")
    except ValueError:
        raise RowError("invalid day") from None
    return {
        "key": fields["key"],
        "since": _number(fields["since"], "since", MAX_EPOCH),
        "day": fields["day"],
    }


def _client(fields, router_id):
    key = fields["key"]
    if key != "router" and not RE_MAC.match(key):
        _address(key, "key")
    ip = fields["ip"] or "-"
    if ip != "-":
        _address(ip, "ip")
    out = {"key": key, "name": _name(fields["name"]), "ip": ip}
    for column in ("up", "dn", "tup", "tdn"):
        out[column] = _number(fields[column], column, MAX_BYTES)
    for column in EXTRA:
        value = fields.get(column, "")
        out[column] = _number(value, column, MAX_BYTES) if value != "" else ""
    out["seen"] = _number(fields["seen"], "seen", MAX_EPOCH)
    return out


def _plan(fields, router_id):
    if not RE_MAC.match(fields["key"]):
        raise RowError("invalid key")
    if fields["period"] not in PERIODS:
        raise RowError("invalid period")
    if fields["enabled"] not in ("0", "1"):
        raise RowError("invalid enabled")
    if not RE_PKEY.match(fields["pkey"]):
        raise RowError("invalid pkey")
    return {
        "key": fields["key"],
        "name": _name(fields["name"]),
        "limit": _number(fields["limit"], "limit", MAX_LIMIT),
        "period": fields["period"],
        "enabled": fields["enabled"],
        "used": _number(fields["used"], "used", MAX_LIMIT),
        "pkey": fields["pkey"],
    }


_BUILDERS = {"meta": _meta, "client": _client, "plan": _plan}


def parse_payload(raw, router_id):
    try:
        text = raw.decode("utf-8").replace("\r\n", "\n")
        rows = list(csv.reader(io.StringIO(text), strict=True))
    except (UnicodeDecodeError, csv.Error):
        raise RowError("invalid data") from None
    if not rows or rows[0] not in ACCEPTED_HEADERS:
        raise RowError("bad header")
    columns = rows[0]
    if len(rows) - 1 > MAX_ROWS:
        raise RowError("too many rows")
    clean = []
    seen = set()
    metas = 0
    for row in rows[1:]:
        if len(row) != len(columns):
            raise RowError("bad column count")
        fields = dict(zip(columns, row))
        kind = fields["type"]
        builder = _BUILDERS.get(kind)
        if builder is None:
            raise RowError("unknown type")
        built = builder(fields, router_id)
        identity = (kind, built["key"])
        if identity in seen:
            raise RowError("duplicate row")
        seen.add(identity)
        metas += kind == "meta"
        out = dict.fromkeys(HEADER, "")
        out.update(built)
        out["type"] = kind
        clean.append(out)
    if metas != 1:
        raise RowError("meta row required")
    return clean


def render_csv(rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(HEADER)
    for row in rows:
        writer.writerow([row[name] for name in HEADER])
    return buffer.getvalue()
