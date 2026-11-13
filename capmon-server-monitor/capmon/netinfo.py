import os
import re
import socket
import subprocess

RE_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
WINDOWS_QUERY = (
    "Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' } | ForEach-Object { "
    "$n = $_.ifIndex; "
    "$m = (Get-NetIPInterface -InterfaceIndex $n -AddressFamily IPv4 -ErrorAction SilentlyContinue).InterfaceMetric; "
    "$g = @(Get-NetRoute -InterfaceIndex $n -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue).Count; "
    "Get-NetIPAddress -InterfaceIndex $n -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
    "ForEach-Object { \"$g $m $($_.IPAddress)\" } }"
)


def usable(address):
    return bool(RE_IPV4.match(address)) and not (
        address.startswith("127.")
        or address.startswith("169.254.")
        or address == "0.0.0.0"
    )


def _run(command):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=15, creationflags=flags,
            stdin=subprocess.DEVNULL
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _physical_windows():
    output = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", WINDOWS_QUERY])
    found = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() and usable(parts[2]):
            found.append((0 if int(parts[0]) else 1, int(parts[1]), parts[2]))
    return [item[2] for item in sorted(found)]


def _physical_linux():
    base = "/sys/class/net"
    try:
        names = sorted(
            name for name in os.listdir(base) if os.path.exists(os.path.join(base, name, "device"))
        )
    except OSError:
        return []
    found = []
    for name in names:
        for line in _run(["ip", "-4", "-o", "addr", "show", "dev", name]).splitlines():
            match = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/", line)
            if match and usable(match.group(1)):
                found.append(match.group(1))
    return found


def _physical():
    if os.name == "nt":
        return _physical_windows()
    if os.path.isdir("/sys/class/net"):
        return _physical_linux()
    return []


def _route_address():
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("10.255.255.255", 1))
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def _host_addresses():
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        return []
    return [info[4][0] for info in infos]


def lan_addresses():
    found = []
    for address in _physical() + [_route_address()] + _host_addresses():
        if address and usable(address) and address not in found:
            found.append(address)
    return found or ["127.0.0.1"]
