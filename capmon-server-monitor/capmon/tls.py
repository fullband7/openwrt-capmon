import base64
import hashlib
import ipaddress
import os
import re
import shutil
import socket
import ssl
import subprocess
from datetime import datetime, timedelta, timezone

RE_PEM = re.compile(r"-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----", re.S)
CERT_DAYS = 3650


class TlsError(Exception):
    pass


def _subject_names(addresses):
    names = {"localhost", socket.gethostname()}
    return sorted(name for name in names if name), list(dict.fromkeys(addresses + ["127.0.0.1"]))


def _write_private(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)


def _generate_native(cert_path, key_path, addresses):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    names, ips = _subject_names(addresses)
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "traffic-sync-server")])
    alternatives = [x509.DNSName(name) for name in names]
    alternatives += [x509.IPAddress(ipaddress.ip_address(address)) for address in ips]
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=CERT_DAYS))
        .add_extension(x509.SubjectAlternativeName(alternatives), critical=False)
        .sign(key, hashes.SHA256())
    )
    _write_private(
        key_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    with open(cert_path, "wb") as handle:
        handle.write(certificate.public_bytes(serialization.Encoding.PEM))


def _generate_openssl(cert_path, key_path, addresses):
    executable = shutil.which("openssl")
    if executable is None:
        raise TlsError(
            "cannot create a certificate: install the 'cryptography' package "
            "(py -3 -m pip install cryptography), install OpenSSL, "
            "or pass --tls-cert and --tls-key"
        )
    names, ips = _subject_names(addresses)
    alternatives = ",".join(["DNS:" + name for name in names] + ["IP:" + address for address in ips])
    command = [
        executable, "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
        "-nodes", "-keyout", key_path, "-out", cert_path, "-days", str(CERT_DAYS),
        "-subj", "/CN=traffic-sync-server", "-addext", "subjectAltName=" + alternatives,
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise TlsError("openssl failed to create the certificate") from exc
    os.chmod(key_path, 0o600)


def ensure_certificate(cert_path, key_path, addresses):
    if os.path.exists(cert_path) and os.path.exists(key_path):
        return False
    os.makedirs(os.path.dirname(os.path.abspath(cert_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(key_path)), exist_ok=True)
    try:
        _generate_native(cert_path, key_path, addresses)
    except ImportError:
        _generate_openssl(cert_path, key_path, addresses)
    return True


def build_context(cert_path, key_path):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.options |= ssl.OP_NO_COMPRESSION
    try:
        context.load_cert_chain(cert_path, key_path)
    except (OSError, ssl.SSLError) as exc:
        raise TlsError("cannot load the certificate or private key") from exc
    return context


def _element(data, offset):
    if offset + 2 > len(data):
        raise TlsError("malformed certificate")
    length = data[offset + 1]
    start = offset + 2
    if length & 0x80:
        count = length & 0x7F
        if count == 0 or count > 4 or start + count > len(data):
            raise TlsError("malformed certificate")
        length = int.from_bytes(data[start:start + count], "big")
        start += count
    end = start + length
    if end > len(data):
        raise TlsError("malformed certificate")
    return data[offset], start, end


def _public_key_info(der):
    tag, start, end = _element(der, 0)
    if tag != 0x30:
        raise TlsError("malformed certificate")
    tag, position, limit = _element(der, start)
    if tag != 0x30:
        raise TlsError("malformed certificate")
    children = []
    while position < limit:
        child_tag, child_start, child_end = _element(der, position)
        children.append((child_tag, position, child_end))
        position = child_end
    index = 7 if children and children[0][0] == 0xA0 else 6
    if len(children) <= index - 1 or children[index - 1][0] != 0x30:
        raise TlsError("malformed certificate")
    _, first, last = children[index - 1]
    return der[first:last]


def public_key_pin(cert_path):
    try:
        with open(cert_path, "r", encoding="ascii") as handle:
            block = RE_PEM.search(handle.read())
    except (OSError, UnicodeDecodeError) as exc:
        raise TlsError("cannot read the certificate") from exc
    if block is None:
        raise TlsError("the certificate file is not in PEM format")
    der = ssl.PEM_cert_to_DER_cert(block.group(0))
    digest = hashlib.sha256(_public_key_info(der)).digest()
    return "sha256//" + base64.b64encode(digest).decode("ascii")
