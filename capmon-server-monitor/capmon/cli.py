import argparse
import logging
import logging.handlers
import os
import signal
import sys
import threading

from . import __version__
from .config import Settings
from .constants import (
    DEFAULT_MAX_ROUTERS,
    DEFAULT_PORT,
    DEFAULT_WORKERS,
    FAIL_LIMIT,
    FAIL_TRACKED,
    FAIL_WINDOW,
)
from .netinfo import lan_addresses
from .pairing import RouterGate
from .paths import app_dir
from .security import Authenticator, FailureThrottle
from .server import Services, SyncServer
from .storage import Storage
from .tls import TlsError, build_context, ensure_certificate, public_key_pin

APP_DIR = app_dir()


def build_parser():
    parser = argparse.ArgumentParser(
        prog="capmon_server",
        description="Receives router traffic data and stores it as CSV",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--data-dir", default=os.path.join(APP_DIR, "data"))
    parser.add_argument("--config", default=os.path.join(APP_DIR, "config.json"))
    parser.add_argument("--token", default="")
    parser.add_argument("--reset-token", action="store_true")
    parser.add_argument("--add-router", metavar="ID")
    parser.add_argument("--allow-multiple-routers", action="store_true")
    parser.add_argument("--reset-pairing", action="store_true")
    parser.add_argument("--tls-cert", default=os.path.join(APP_DIR, "certs", "server.crt"))
    parser.add_argument("--tls-key", default=os.path.join(APP_DIR, "certs", "server.key"))
    parser.add_argument("--no-tls", action="store_true")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--max-routers", type=int, default=DEFAULT_MAX_ROUTERS)
    parser.add_argument("--log-file")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def configure_logging(log_file, verbose):
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(
            logging.handlers.RotatingFileHandler(
                log_file, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
            )
        )
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def install_signal_handlers(server):
    def stop(signum, frame):
        threading.Thread(target=server.shutdown, daemon=True).start()

    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        number = getattr(signal, name, None)
        if number is not None:
            try:
                signal.signal(number, stop)
            except (OSError, ValueError):
                pass


def print_banner(args, addresses, pin, generated, storage):
    scheme = "http" if args.no_tls else "https"
    print("Traffic sync server is running")
    for index, address in enumerate(addresses):
        label = "  Server URL for the router : " if index == 0 else "                              "
        print("%s%s://%s:%d" % (label, scheme, address, args.port))
    if pin:
        print("  Certificate pin           : %s" % pin)
    else:
        print("  WARNING: TLS is disabled, the token and all data travel in clear text")
    if generated:
        print("  Access token              : %s  (shown only once)" % generated)
    else:
        print("  Access token              : stored hashed (use --reset-token to issue a new one)")
    print("  CSV files are saved in    : %s" % storage.directory)
    print("Press Ctrl+C to stop.")
    sys.stdout.flush()


def run(args):
    settings = Settings(args.config)
    if args.add_router:
        print("Router %s token: %s" % (args.add_router, settings.add_router(args.add_router)))
        return 0
    token = args.token or os.environ.get("TRAFFIC_SYNC_TOKEN", "")
    if token and args.reset_token:
        raise ValueError("--reset-token cannot be combined with --token")
    generated = settings.ensure_admin(token, args.reset_token)
    if args.reset_pairing or args.reset_token:
        settings.unpair()
    storage = Storage(args.data_dir, max_routers=args.max_routers)
    addresses = lan_addresses() if args.host in ("0.0.0.0", "::") else [args.host]
    context = None
    pin = ""
    if not args.no_tls:
        ensure_certificate(args.tls_cert, args.tls_key, addresses)
        context = build_context(args.tls_cert, args.tls_key)
        pin = public_key_pin(args.tls_cert)
    services = Services(
        storage,
        Authenticator(settings.admin_hash, settings.routers),
        FailureThrottle(FAIL_LIMIT, FAIL_WINDOW, FAIL_TRACKED),
        gate=RouterGate(settings, enforce=not args.allow_multiple_routers),
    )
    server = SyncServer((args.host, args.port), services, max(args.workers, 1), context)
    install_signal_handlers(server)
    print_banner(args, addresses, pin, generated, storage)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    configure_logging(args.log_file, args.verbose)
    try:
        return run(args)
    except (TlsError, ValueError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
