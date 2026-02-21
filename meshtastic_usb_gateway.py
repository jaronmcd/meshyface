#!/usr/bin/env python3
import argparse
import signal
import socket
import sys
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

import serial
from serial import SerialException


def utc_ts() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def log(message: str) -> None:
    print(f"[{utc_ts()}] {message}", flush=True)


def open_serial_forever(
    serial_path: str,
    baudrate: int,
    timeout: float,
    write_timeout: float,
    retry_seconds: float,
    stop: "StopFlag",
) -> Optional[serial.Serial]:
    while not stop.stop:
        try:
            ser = serial.Serial(
                port=serial_path,
                baudrate=baudrate,
                timeout=timeout,
                write_timeout=write_timeout,
            )
            log(f"Serial connected: {serial_path} @ {baudrate}")
            return ser
        except SerialException as exc:
            log(f"Serial open failed: {exc}. Retrying in {retry_seconds:.1f}s...")
            stop.wait(retry_seconds)
    return None


def bridge_once(
    client: socket.socket,
    ser: serial.Serial,
    *,
    stop: "StopFlag",
    client_timeout: float,
) -> Tuple[bool, bool]:
    """
    Returns:
        (serial_ok, client_ok)
    """
    client.settimeout(client_timeout)
    serial_ok = True
    client_ok = True

    while not stop.stop:
        try:
            from_client = client.recv(4096)
            if from_client == b"":
                client_ok = False
                break
            if from_client:
                ser.write(from_client)
        except socket.timeout:
            pass
        except OSError:
            client_ok = False
            break
        except SerialException:
            serial_ok = False
            break

        try:
            waiting = max(1, ser.in_waiting)
            from_serial = ser.read(waiting)
            if from_serial:
                client.sendall(from_serial)
        except OSError:
            client_ok = False
            break
        except SerialException:
            serial_ok = False
            break

    return serial_ok, client_ok


class StopFlag:
    def __init__(self) -> None:
        self.stop = False

    def handler(self, _signum, _frame) -> None:
        self.stop = True

    def wait(self, seconds: float) -> None:
        end = time.time() + seconds
        while not self.stop and time.time() < end:
            time.sleep(min(0.2, max(0.0, end - time.time())))


def run_gateway(args: argparse.Namespace) -> int:
    stop = StopFlag()
    signal.signal(signal.SIGINT, stop.handler)
    signal.signal(signal.SIGTERM, stop.handler)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.listen_host, args.listen_port))
    server.listen(args.backlog)
    server.settimeout(1.0)

    log(
        f"Gateway listening on {args.listen_host}:{args.listen_port} -> {args.serial} @ {args.baud}"
    )
    log("One TCP client at a time. Press Ctrl+C to stop.")

    try:
        while not stop.stop:
            try:
                client, addr = server.accept()
            except socket.timeout:
                continue
            except OSError:
                if stop.stop:
                    break
                raise

            client_ip, client_port = addr[0], addr[1]
            log(f"Client connected: {client_ip}:{client_port}")

            with client:
                client_ok = True
                while client_ok and not stop.stop:
                    ser = open_serial_forever(
                        serial_path=args.serial,
                        baudrate=args.baud,
                        timeout=args.serial_timeout,
                        write_timeout=args.serial_write_timeout,
                        retry_seconds=args.serial_retry_seconds,
                        stop=stop,
                    )
                    if ser is None:
                        break

                    with ser:
                        serial_ok, client_ok = bridge_once(
                            client,
                            ser,
                            stop=stop,
                            client_timeout=args.client_timeout,
                        )

                    if not client_ok:
                        break
                    if not serial_ok and not stop.stop:
                        log("Serial disconnected. Waiting for device to reappear...")
                        stop.wait(args.serial_retry_seconds)

            log(f"Client disconnected: {client_ip}:{client_port}")

    finally:
        try:
            server.close()
        except OSError:
            pass

    log("Gateway stopped.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Expose a Meshtastic USB serial device on TCP (Meshtastic-compatible byte bridge)."
    )
    parser.add_argument(
        "--serial",
        required=True,
        help="Serial device path. Prefer /dev/serial/by-id/... for stable naming.",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="Serial baudrate (default: 115200).",
    )
    parser.add_argument(
        "--listen-host",
        default="0.0.0.0",
        help="TCP bind host (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--listen-port",
        type=int,
        default=4403,
        help="TCP bind port (default: 4403).",
    )
    parser.add_argument(
        "--backlog",
        type=int,
        default=8,
        help="TCP listen backlog (default: 8).",
    )
    parser.add_argument(
        "--serial-timeout",
        type=float,
        default=0.1,
        help="Serial read timeout seconds (default: 0.1).",
    )
    parser.add_argument(
        "--serial-write-timeout",
        type=float,
        default=1.0,
        help="Serial write timeout seconds (default: 1.0).",
    )
    parser.add_argument(
        "--serial-retry-seconds",
        type=float,
        default=2.0,
        help="Retry delay if serial open fails/disconnects (default: 2.0).",
    )
    parser.add_argument(
        "--client-timeout",
        type=float,
        default=0.2,
        help="TCP client read timeout seconds (default: 0.2).",
    )
    args = parser.parse_args()

    try:
        return run_gateway(args)
    except Exception as exc:
        log(f"Fatal error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
