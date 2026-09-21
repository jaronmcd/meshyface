#!/usr/bin/env python3
"""Real-time GUI responsiveness benchmark with synthetic mesh growth.

The virtual-time benchmark (benchmark_gui_responsiveness.py) cannot see wall-clock costs:
virtual time makes network waits and long tasks disappear. This benchmark drives Chromium
over the DevTools protocol in real time, replaces /api/state with generated payloads of a
chosen node count (every poll is a full 200 with a few fresh nodes, like a busy mesh), and
records main-thread busy time, long tasks, and event-loop lag.

Absolute timings depend on the machine, so the main regression signal is how cost scales
between node counts: a per-node or per-pair regression shows up as a ratio on any host.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_gui_responsiveness import evaluate_thresholds, find_browser, load_thresholds  # noqa: E402

PAGE_PROBE = r"""
(() => {
  window.__meshRealtimeBench = { longTasks: [], lagMax: 0 };
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) window.__meshRealtimeBench.longTasks.push([entry.startTime, entry.duration]);
    }).observe({ type: "longtask", buffered: true });
  } catch (_err) {}
  let expected = performance.now() + 100;
  setInterval(() => {
    const now = performance.now();
    window.__meshRealtimeBench.lagMax = Math.max(window.__meshRealtimeBench.lagMax, now - expected);
    expected = now + 100;
  }, 100);
})();
"""


class CdpClient:
    """Minimal stdlib WebSocket client for the Chrome DevTools protocol."""

    def __init__(self, ws_url: str) -> None:
        rest = ws_url.split("://", 1)[1]
        host_port, path = rest.split("/", 1)
        host, port = host_port.split(":")
        self._sock = socket.create_connection((host, int(port)))
        key = base64.b64encode(os.urandom(16)).decode()
        self._sock.sendall(
            (
                f"GET /{path} HTTP/1.1\r\nHost: {host_port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
            ).encode()
        )
        buffer = b""
        while b"\r\n\r\n" not in buffer:
            buffer += self._sock.recv(4096)
        self._buffer = buffer.split(b"\r\n\r\n", 1)[1]
        self._next_id = 0
        self.events: list[dict] = []

    def _read_exact(self, size: int) -> bytes:
        while len(self._buffer) < size:
            chunk = self._sock.recv(1 << 20)
            if not chunk:
                raise EOFError("DevTools connection closed")
            self._buffer += chunk
        data, self._buffer = self._buffer[:size], self._buffer[size:]
        return data

    def _read_message(self) -> dict:
        data = b""
        while True:
            first, second = self._read_exact(2)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read_exact(8))[0]
            data += self._read_exact(length)
            if first & 0x80:
                return json.loads(data)

    def _send(self, message: dict) -> None:
        payload = json.dumps(message).encode()
        mask = os.urandom(4)
        header = bytes([0x81])
        if len(payload) < 126:
            header += bytes([0x80 | len(payload)])
        elif len(payload) < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", len(payload))
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", len(payload))
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        self._sock.sendall(header + mask + masked)

    def call(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        request_id = self._next_id
        self._send({"id": request_id, "method": method, "params": params or {}})
        while True:
            message = self._read_message()
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})
            self.events.append(message)

    def evaluate(self, expression: str) -> object:
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        return result.get("result", {}).get("value")

    def poll_event(self, timeout: float) -> dict | None:
        if self.events:
            return self.events.pop(0)
        self._sock.settimeout(timeout)
        try:
            return self._read_message()
        except (socket.timeout, TimeoutError):
            return None
        finally:
            self._sock.settimeout(None)


def build_synthetic_state(node_count: int, *, seed: int = 7, now_unix: int | None = None) -> dict:
    """A lite chat-profile state payload with generated nodes around a synthetic metro mesh."""
    rng = random.Random(seed)
    now = int(time.time()) if now_unix is None else int(now_unix)
    center_lat, center_lon = 44.95, -93.2
    nodes = []
    history_caps = {}
    for index in range(node_count):
        node_id = f"!{0x20000000 + index:08x}"
        age = int(rng.expovariate(1 / 21600)) % (13 * 86400)
        positioned = rng.random() < 0.55
        node = {
            "id": node_id,
            "num": 0x20000000 + index,
            "short_name": f"N{index % 10000:04d}",
            "long_name": f"Synthetic Node {index}",
            "hardware_model": rng.choice(["HELTEC_V3", "RAK4631", "T_ECHO", "STATION_G2"]),
            "role": rng.choice(["CLIENT", "CLIENT_MUTE", "ROUTER_LATE"]),
            "last_heard_unix": now - age,
            "hops_away": rng.randint(0, 7),
            "snr": round(rng.uniform(-18, 10), 2),
            "battery_level": rng.randint(5, 101),
            "saved_packets": rng.randint(0, 5000),
            "link_count": rng.randint(0, 12),
        }
        if positioned:
            node["lat"] = center_lat + rng.gauss(0, 0.2)
            node["lon"] = center_lon + rng.gauss(0, 0.3)
            node["position_points"] = rng.randint(1, 400)
        nodes.append(node)
        history_caps[node_id] = {
            "first_seen_unix": now - 40 * 86400,
            "last_seen_unix": node["last_heard_unix"],
            "has_position": positioned,
            "last_hops": node["hops_away"],
            "last_short_name": node["short_name"],
            "last_long_name": node["long_name"],
        }
    node_ids = [node["id"] for node in nodes]
    recent_chat = [
        {
            "from": rng.choice(node_ids),
            "to": "^all",
            "text": f"synthetic message {index}",
            "channel": 0,
            "rx_time_unix": now - (180 - index) * 30,
            "packet_id": 1_000_000 + index,
        }
        for index in range(min(180, node_count))
    ]
    recent_packets = [
        {
            "summary": {
                "packet_id": 2_000_000 + index,
                "from": rng.choice(node_ids),
                "to": "^all",
                "portnum": rng.choice(["TELEMETRY_APP", "POSITION_APP", "NODEINFO_APP", "TEXT_MESSAGE_APP"]),
                "rx_time_unix": now - (120 - index) * 10,
            }
        }
        for index in range(min(120, node_count))
    ]
    online = sum(1 for node in nodes if now - int(node["last_heard_unix"]) < 7200)
    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(now)),
        "local_node_id": node_ids[0] if node_ids else "",
        "nodes": nodes,
        "history_caps": history_caps,
        "meshyface_profiles": {},
        "summary": {
            "node_count": node_count,
            "known_node_count": node_count,
            "node_window_omitted_count": 0,
            "online_node_count": online,
            "nodes_with_position": sum(1 for node in nodes if "lat" in node),
            "live_packet_count": 5000,
            "edge_count": 0,
            "real_edge_count": 0,
            "modem_preset": "MEDIUM_FAST",
            "radio_link": {"state": "connected", "connected": True},
        },
        "traffic": {
            "edges": [],
            "port_counts": [],
            "recent_packets": recent_packets,
            "recent_chat": recent_chat,
            "node_packet_trends": {},
        },
    }


def _wait_for_page_target(port: int, timeout_s: float = 15.0) -> str:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=2))
            for target in targets:
                if target.get("type") == "page":
                    return str(target["webSocketDebuggerUrl"])
        except Exception:
            pass
        time.sleep(0.1)
    raise RuntimeError("Chromium DevTools endpoint did not start")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_scenario(
    *,
    url: str,
    browser: str,
    node_count: int,
    cpu_throttle: float,
    warmup_s: float,
    measure_s: float,
    extra_browser_args: list[str],
    operation_probe: str | None = None,
) -> dict:
    payload = build_synthetic_state(node_count)
    rng = random.Random(node_count)
    port = _free_port()
    # Chromium helper processes can still write to the profile while it is removed.
    with tempfile.TemporaryDirectory(prefix="mesh-gui-realtime-", ignore_cleanup_errors=True) as user_data_dir:
        proc = subprocess.Popen(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                f"--remote-debugging-port={port}",
                f"--user-data-dir={user_data_dir}",
                "--window-size=1600,1000",
                "--remote-allow-origins=*",
                *extra_browser_args,
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            cdp = CdpClient(_wait_for_page_target(port))
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Performance.enable", {"timeDomain": "threadTicks"})
            if cpu_throttle > 1:
                cdp.call("Emulation.setCPUThrottlingRate", {"rate": cpu_throttle})
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": PAGE_PROBE})
            cdp.call("Fetch.enable", {"patterns": [{"urlPattern": "*/api/state*", "requestStage": "Request"}]})
            cdp.call("Page.navigate", {"url": url})
            polls = 0
            exceptions = 0

            def pump(until: float) -> None:
                nonlocal polls, exceptions
                while time.time() < until:
                    event = cdp.poll_event(0.2)
                    if not event:
                        continue
                    method = event.get("method")
                    if method == "Runtime.exceptionThrown":
                        exceptions += 1
                    if method != "Fetch.requestPaused":
                        continue
                    polls += 1
                    now = int(time.time())
                    payload["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(now))
                    for node in rng.sample(payload["nodes"], min(5, len(payload["nodes"]))):
                        node["last_heard_unix"] = now
                    body = base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
                    cdp.call(
                        "Fetch.fulfillRequest",
                        {
                            "requestId": event["params"]["requestId"],
                            "responseCode": 200,
                            "responseHeaders": [
                                {"name": "Content-Type", "value": "application/json; charset=utf-8"},
                                {"name": "ETag", "value": f'W/"realtime-bench-{polls}"'},
                                {"name": "Cache-Control", "value": "no-store"},
                            ],
                            "body": body,
                        },
                    )

            started = time.time()
            pump(started + warmup_s)
            measure_start_ms = float(cdp.evaluate("performance.now()") or 0.0)
            before = {item["name"]: item["value"] for item in cdp.call("Performance.getMetrics")["metrics"]}
            polls_before = polls
            cdp.evaluate("window.__meshRealtimeBench && (window.__meshRealtimeBench.lagMax = 0)")
            pump(time.time() + measure_s)
            after = {item["name"]: item["value"] for item in cdp.call("Performance.getMetrics")["metrics"]}
            probe = cdp.evaluate("JSON.stringify(window.__meshRealtimeBench || {})")
            operations = cdp.evaluate(operation_probe) if operation_probe else None
            if operation_probe and not isinstance(operations, dict):
                raise RuntimeError("Populated operation probe did not return results")
            dom_elements = cdp.evaluate("document.getElementsByTagName('*').length")
            exceptions += sum(1 for event in cdp.events if event.get("method") == "Runtime.exceptionThrown")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    probe_data = json.loads(probe or "{}")
    long_tasks = sorted(
        duration for start, duration in probe_data.get("longTasks", []) if start >= measure_start_ms
    )
    busy_s = float(after.get("TaskDuration", 0.0)) - float(before.get("TaskDuration", 0.0))
    return {
        **({"operations": operations} if operation_probe else {}),
        "nodes": node_count,
        "cpu_throttle": cpu_throttle,
        "measure_seconds": measure_s,
        "polls": polls - polls_before,
        "busy_percent": round(busy_s / measure_s * 100.0, 1),
        "long_tasks": len(long_tasks),
        "long_task_p95_ms": round(long_tasks[int(len(long_tasks) * 0.95)] if long_tasks else 0.0, 1),
        "long_task_max_ms": round(long_tasks[-1] if long_tasks else 0.0, 1),
        "event_loop_lag_max_ms": round(float(probe_data.get("lagMax") or 0.0), 1),
        "dom_elements": int(dom_elements or 0),
        "js_exceptions": exceptions,
    }


def scenario_key(node_count: int, cpu_throttle: float) -> str:
    return f"nodes={node_count},cpu={cpu_throttle:g}"


def add_scaling(result: dict, node_counts: list[int], throttles: list[float]) -> None:
    if len(node_counts) < 2:
        return
    low, high = min(node_counts), max(node_counts)
    scaling = {}
    for throttle in throttles:
        small = result["scenarios"].get(scenario_key(low, throttle))
        large = result["scenarios"].get(scenario_key(high, throttle))
        if not small or not large:
            continue

        def ratio(key: str, floor: float) -> float:
            # Floors keep a near-idle small scenario (for example no long tasks on a fast
            # machine) from turning normal large-scenario costs into a huge ratio.
            return round(float(large[key]) / max(floor, float(small[key])), 2)

        scaling[f"cpu={throttle:g}"] = {
            "from_nodes": low,
            "to_nodes": high,
            "busy_percent_ratio": ratio("busy_percent", 1.0),
            "long_task_max_ratio": ratio("long_task_max_ms", 50.0),
        }
    result["scaling"] = scaling


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8877/", help="Dashboard URL serving the UI assets.")
    parser.add_argument("--browser", default=None, help="Chromium/Chrome executable path or name.")
    parser.add_argument("--nodes", type=int, action="append", help="Synthetic node count; repeatable (default 750 and 3000).")
    parser.add_argument("--cpu-throttle", type=float, action="append", help="Chromium CPU throttle; repeatable (default 1).")
    parser.add_argument("--warmup-seconds", type=float, default=12.0)
    parser.add_argument("--measure-seconds", type=float, default=30.0)
    parser.add_argument("--thresholds", type=Path, default=None)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--browser-arg", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    browser = find_browser(args.browser)
    node_counts = args.nodes or [750, 3000]
    throttles = args.cpu_throttle or [1.0]
    result: dict = {"url": args.url, "scenarios": {}}
    for throttle in throttles:
        for node_count in node_counts:
            scenario = run_scenario(
                url=args.url,
                browser=browser,
                node_count=node_count,
                cpu_throttle=throttle,
                warmup_s=args.warmup_seconds,
                measure_s=args.measure_seconds,
                extra_browser_args=list(args.browser_arg),
            )
            result["scenarios"][scenario_key(node_count, throttle)] = scenario
            print(
                f"{scenario_key(node_count, throttle):20s} polls={scenario['polls']:3d} "
                f"busy={scenario['busy_percent']:5.1f}% long_tasks={scenario['long_tasks']:3d} "
                f"max={scenario['long_task_max_ms']:6.0f}ms lag_max={scenario['event_loop_lag_max_ms']:6.0f}ms "
                f"dom={scenario['dom_elements']} js_exceptions={scenario['js_exceptions']}"
            )
    add_scaling(result, node_counts, throttles)
    for key, scaling in result.get("scaling", {}).items():
        print(
            f"scaling {key}: {scaling['from_nodes']} -> {scaling['to_nodes']} nodes "
            f"busy x{scaling['busy_percent_ratio']} long-task max x{scaling['long_task_max_ratio']}"
        )
    failures = evaluate_thresholds(result, load_thresholds(args.thresholds)) if args.thresholds else []
    result["ok"] = not failures
    result["threshold_failures"] = failures
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for failure in failures:
        print(f"THRESHOLD FAILURE: {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
