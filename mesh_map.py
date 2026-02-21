import argparse
import json
import socket
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import meshtastic
from mesh_connection import add_mesh_connection_args, mesh_target_label, open_mesh_interface
from pubsub import pub


DEFAULT_MESH_PORT = "/dev/ttyACM0"
DEFAULT_HTTP_HOST = "0.0.0.0"
DEFAULT_HTTP_PORT = 8765
DEFAULT_REFRESH_MS = 2000


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _guess_lan_ipv4() -> Optional[str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass

    try:
        addr_info = socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET)
        for _family, _type, _proto, _canonname, sockaddr in addr_info:
            ip = sockaddr[0]
            if ip and not ip.startswith("127."):
                return ip
    except socket.gaierror:
        pass

    return None


def _format_epoch(epoch_value: Any) -> Optional[str]:
    epoch = _to_int(epoch_value)
    if epoch is None or epoch <= 0:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def _get_node_id_from_num(iface: Any, node_num: Any) -> Optional[str]:
    numeric = _to_int(node_num)
    if numeric is None:
        return None
    if numeric == meshtastic.BROADCAST_NUM:
        return "^all"

    info = (iface.nodesByNum or {}).get(numeric, {})
    user = info.get("user", {}) if isinstance(info, dict) else {}
    node_id = user.get("id") if isinstance(user, dict) else None
    if node_id:
        return str(node_id)
    return f"!{numeric:08x}"


def _extract_position(node_info: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    position = node_info.get("position")
    if not isinstance(position, dict):
        return None

    lat = position.get("latitude")
    lon = position.get("longitude")

    if lat is None and position.get("latitudeI") is not None:
        lat = float(position["latitudeI"]) * 1e-7
    if lon is None and position.get("longitudeI") is not None:
        lon = float(position["longitudeI"]) * 1e-7

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None

    if lat_f == 0.0 and lon_f == 0.0:
        return None
    return lat_f, lon_f


class CommunicationTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.packet_count = 0
        self.edges: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def on_receive(self, packet: Dict[str, Any], interface: Any) -> None:
        with self._lock:
            self.packet_count += 1
            self._record_packet_unlocked(packet, interface)

    def record_packet(self, packet: Dict[str, Any], interface: Any) -> None:
        with self._lock:
            self._record_packet_unlocked(packet, interface)

    def _record_packet_unlocked(
        self, packet: Dict[str, Any], interface: Any
    ) -> None:
        from_id = packet.get("fromId") or _get_node_id_from_num(interface, packet.get("from"))
        to_id = packet.get("toId") or _get_node_id_from_num(interface, packet.get("to"))

        if not from_id or not to_id:
            return
        if to_id in ("^all", "Unknown"):
            return

        key = (str(from_id), str(to_id))
        edge = self.edges.setdefault(
            key,
            {
                "from": str(from_id),
                "to": str(to_id),
                "count": 0,
                "last_rx_time": None,
                "portnums": set(),
            },
        )

        edge["count"] += 1

        rx_time = _to_int(packet.get("rxTime"))
        if rx_time is not None and (edge["last_rx_time"] is None or rx_time > edge["last_rx_time"]):
            edge["last_rx_time"] = rx_time

        decoded = packet.get("decoded", {})
        if isinstance(decoded, dict):
            portnum = decoded.get("portnum")
            if portnum is not None:
                edge["portnums"].add(str(portnum))

    def as_rows(self, nodes_with_position: Dict[str, Dict[str, Any]]) -> list[Dict[str, Any]]:
        with self._lock:
            rows = []
            for edge in self.edges.values():
                if edge["from"] not in nodes_with_position or edge["to"] not in nodes_with_position:
                    continue
                rows.append(
                    {
                        "from": edge["from"],
                        "to": edge["to"],
                        "count": edge["count"],
                        "last_rx_time": _format_epoch(edge["last_rx_time"]),
                        "portnums": sorted(edge["portnums"]),
                    }
                )
        rows.sort(key=lambda item: item["count"], reverse=True)
        return rows


def _snapshot_nodes(iface: Any) -> Dict[str, Dict[str, Any]]:
    nodes_with_position: Dict[str, Dict[str, Any]] = {}
    for node_num, info in list((iface.nodesByNum or {}).items()):
        if not isinstance(info, dict):
            continue

        coords = _extract_position(info)
        if coords is None:
            continue

        node_num_int = _to_int(info.get("num", node_num))
        user = info.get("user", {}) if isinstance(info.get("user"), dict) else {}
        node_id = user.get("id") if user.get("id") else None
        if node_id is None and node_num_int is not None:
            node_id = f"!{node_num_int:08x}"
        if node_id is None:
            continue

        nodes_with_position[str(node_id)] = {
            "id": str(node_id),
            "num": node_num_int,
            "short_name": user.get("shortName"),
            "long_name": user.get("longName"),
            "lat": coords[0],
            "lon": coords[1],
            "last_heard": _format_epoch(info.get("lastHeard")),
            "snr": info.get("snr"),
        }
    return nodes_with_position


def _seed_edges_from_node_db(
    tracker: CommunicationTracker, iface: Any
) -> None:
    for node in list((iface.nodesByNum or {}).values()):
        if not isinstance(node, dict):
            continue
        last_packet = node.get("lastReceived")
        if isinstance(last_packet, dict):
            tracker.record_packet(last_packet, iface)


def _build_state(iface: Any, tracker: CommunicationTracker) -> Dict[str, Any]:
    nodes = _snapshot_nodes(iface)
    edges = tracker.as_rows(nodes)
    return {
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ"),
        "packets_observed": tracker.packet_count,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def _render_realtime_html(refresh_ms: int) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Meshtastic Realtime Map</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <style>
    html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; font-family: sans-serif; }}
    #map {{ width: 100%; height: 100%; }}
    .panel {{
      position: absolute;
      top: 12px;
      right: 12px;
      z-index: 1000;
      background: rgba(255, 255, 255, 0.96);
      padding: 10px 12px;
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
      max-width: 360px;
      line-height: 1.35;
      font-size: 13px;
    }}
    .panel h3 {{ margin: 0 0 6px 0; font-size: 15px; }}
    .status {{
      position: absolute;
      left: 12px;
      bottom: 12px;
      z-index: 1000;
      background: rgba(15, 23, 42, 0.9);
      color: #fff;
      padding: 8px 10px;
      border-radius: 8px;
      font-size: 12px;
      min-width: 200px;
    }}
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="panel">
    <h3>Meshtastic Realtime Map</h3>
    <div id="stats">Loading...</div>
    <div style="margin-top: 6px;">Green circles: nodes with position</div>
    <div>Red lines: observed sender -> receiver traffic</div>
  </div>
  <div id="status" class="status">Waiting for first update...</div>

  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>
  <script>
    const refreshMs = {refresh_ms};
    const map = L.map("map").setView([39.5, -98.35], 4);
    L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    }}).addTo(map);

    let overlayGroup = L.layerGroup().addTo(map);
    let didFitBounds = false;
    let updateCounter = 0;

    function setStatus(message) {{
      document.getElementById("status").textContent = message;
    }}

    function renderState(state) {{
      const nodes = state.nodes || [];
      const edges = state.edges || [];
      updateCounter += 1;

      overlayGroup.clearLayers();
      const nodeById = Object.fromEntries(nodes.map((node) => [node.id, node]));
      const features = [];

      for (const node of nodes) {{
        const label = node.long_name || node.short_name || node.id;
        const popup = `
          <b>${{label}}</b><br/>
          ID: ${{node.id}}<br/>
          Num: ${{node.num ?? "n/a"}}<br/>
          Lat/Lon: ${{node.lat.toFixed(6)}}, ${{node.lon.toFixed(6)}}<br/>
          SNR: ${{node.snr ?? "n/a"}}<br/>
          Last heard: ${{node.last_heard || "n/a"}}
        `;

        const marker = L.circleMarker([node.lat, node.lon], {{
          radius: 7,
          color: "#0f172a",
          weight: 1,
          fillColor: "#22c55e",
          fillOpacity: 0.9
        }}).bindPopup(popup);

        marker.addTo(overlayGroup);
        features.push(marker);
      }}

      for (const edge of edges) {{
        const src = nodeById[edge.from];
        const dst = nodeById[edge.to];
        if (!src || !dst) continue;

        const line = L.polyline(
          [[src.lat, src.lon], [dst.lat, dst.lon]],
          {{
            color: "#e11d48",
            opacity: 0.75,
            weight: Math.min(8, 2 + edge.count)
          }}
        ).bindPopup(`
          <b>${{edge.from}} -> ${{edge.to}}</b><br/>
          Messages: ${{edge.count}}<br/>
          Last seen: ${{edge.last_rx_time || "n/a"}}<br/>
          Ports: ${{edge.portnums.length ? edge.portnums.join(", ") : "n/a"}}
        `);

        line.addTo(overlayGroup);
        features.push(line);
      }}

      if (features.length > 0 && !didFitBounds) {{
        const group = L.featureGroup(features);
        map.fitBounds(group.getBounds().pad(0.2));
        didFitBounds = true;
      }}

      document.getElementById("stats").innerHTML = `
        Updated: ${{state.generated_at || "n/a"}}<br/>
        Packets observed: ${{state.packets_observed ?? 0}}<br/>
        Nodes with position: ${{nodes.length}}<br/>
        Directed links: ${{edges.length}}<br/>
        Poll interval: ${{refreshMs}} ms
      `;
      setStatus(`Live update #${{updateCounter}}`);
    }}

    async function pollState() {{
      try {{
        const res = await fetch("/api/state", {{ cache: "no-store" }});
        if (!res.ok) {{
          setStatus(`API error: ${{res.status}}`);
          return;
        }}
        const state = await res.json();
        renderState(state);
      }} catch (err) {{
        setStatus("Connection lost. Retrying...");
      }}
    }}

    pollState();
    setInterval(pollState, refreshMs);
  </script>
</body>
</html>
"""


def _make_http_handler(html_text: str, state_fn):
    class MapHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            try:
                parsed = urlparse(self.path)
                path = parsed.path

                if path in ("/", "/index.html"):
                    body = html_text.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return

                if path == "/api/state":
                    payload = json.dumps(state_fn(), separators=(",", ":")).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Not Found")
            except (BrokenPipeError, ConnectionResetError):
                # Browser/client closed the socket before the response finished.
                return

        def log_message(self, format: str, *args: Any) -> None:
            return

    return MapHandler


def _render_snapshot_html(nodes: Dict[str, Dict[str, Any]], edges: list[Dict[str, Any]]) -> str:
    generated_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    if not nodes:
        return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Meshtastic Communication Map</title>
  <style>
    body {{ font-family: sans-serif; margin: 2rem; }}
  </style>
</head>
<body>
  <h2>Meshtastic Communication Map</h2>
  <p>No positioned nodes found. Make sure at least one node has valid latitude/longitude.</p>
  <p>Generated at {generated_at}</p>
</body>
</html>
"""

    node_rows = list(nodes.values())
    avg_lat = sum(node["lat"] for node in node_rows) / len(node_rows)
    avg_lon = sum(node["lon"] for node in node_rows) / len(node_rows)

    nodes_json = json.dumps(node_rows)
    edges_json = json.dumps(edges)

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Meshtastic Communication Map</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <style>
    body {{ margin: 0; font-family: sans-serif; }}
    #map {{ height: 100vh; width: 100%; }}
    .panel {{
      position: absolute;
      top: 12px;
      right: 12px;
      z-index: 1000;
      background: rgba(255, 255, 255, 0.95);
      padding: 10px 12px;
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
      max-width: 320px;
    }}
    .panel h3 {{ margin: 0 0 6px 0; font-size: 15px; }}
    .panel p {{ margin: 2px 0; font-size: 13px; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="panel">
    <h3>Meshtastic Communication Map</h3>
    <p>Generated at: {generated_at}</p>
    <p>Nodes with position: {len(node_rows)}</p>
    <p>Observed directed links: {len(edges)}</p>
    <p>Red lines are observed sender -> receiver paths.</p>
  </div>

  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>
  <script>
    const nodes = {nodes_json};
    const edges = {edges_json};

    const map = L.map("map").setView([{avg_lat}, {avg_lon}], 10);
    L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);

    const nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]));
    const features = [];

    nodes.forEach((node) => {{
      const label = node.long_name || node.short_name || node.id;
      const popup = `
        <b>${{label}}</b><br/>
        ID: ${{node.id}}<br/>
        Num: ${{node.num ?? "n/a"}}<br/>
        Lat/Lon: ${{node.lat.toFixed(6)}}, ${{node.lon.toFixed(6)}}<br/>
        SNR: ${{node.snr ?? "n/a"}}<br/>
        Last heard: ${{node.last_heard || "n/a"}}
      `;
      const marker = L.circleMarker([node.lat, node.lon], {{
        radius: 7,
        color: "#0f172a",
        weight: 1,
        fillColor: "#22c55e",
        fillOpacity: 0.9
      }}).bindPopup(popup).addTo(map);
      features.push(marker);
    }});

    edges.forEach((edge) => {{
      const src = nodeById[edge.from];
      const dst = nodeById[edge.to];
      if (!src || !dst) return;

      const line = L.polyline(
        [[src.lat, src.lon], [dst.lat, dst.lon]],
        {{
          color: "#e11d48",
          opacity: 0.75,
          weight: Math.min(8, 2 + edge.count)
        }}
      ).bindPopup(`
        <b>${{edge.from}} -> ${{edge.to}}</b><br/>
        Messages: ${{edge.count}}<br/>
        Last seen: ${{edge.last_rx_time || "n/a"}}<br/>
        Ports: ${{edge.portnums.length ? edge.portnums.join(", ") : "n/a"}}
      `).addTo(map);
      features.push(line);
    }});

    if (features.length > 0) {{
      const group = L.featureGroup(features);
      map.fitBounds(group.getBounds().pad(0.2));
    }}
  </script>
</body>
</html>
"""


def run_snapshot_mode(args: argparse.Namespace) -> None:
    print(f"Connecting to {mesh_target_label(args)} ...")
    iface = open_mesh_interface(args)

    tracker = CommunicationTracker()
    pub.subscribe(tracker.on_receive, "meshtastic.receive")

    print(f"Connected. Known nodes: {len(iface.nodes or {})}")
    print(f"Listening for {args.listen_seconds} seconds (Ctrl+C to stop early) ...")

    started = time.time()
    try:
        while time.time() - started < args.listen_seconds:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping capture early.")
    finally:
        _seed_edges_from_node_db(tracker, iface)
        nodes = _snapshot_nodes(iface)
        edges = tracker.as_rows(nodes)
        html = _render_snapshot_html(nodes, edges)

        with open(args.output, "w", encoding="utf-8") as out_file:
            out_file.write(html)

        iface.close()

    print(f"Wrote {args.output}")
    print(f"Packets observed: {tracker.packet_count}")
    print(f"Nodes with valid position: {len(nodes)}")
    print(f"Directed links drawn: {len(edges)}")


def run_realtime_mode(args: argparse.Namespace) -> None:
    print(f"Connecting to {mesh_target_label(args)} ...")
    iface = open_mesh_interface(args)

    tracker = CommunicationTracker()
    pub.subscribe(tracker.on_receive, "meshtastic.receive")
    _seed_edges_from_node_db(tracker, iface)

    def state_fn() -> Dict[str, Any]:
        return _build_state(iface, tracker)

    html_text = _render_realtime_html(args.refresh_ms)
    handler_cls = _make_http_handler(html_text, state_fn)
    server = ThreadingHTTPServer((args.http_host, args.http_port), handler_cls)
    bound_host, bound_port = server.server_address[:2]

    print("Realtime map server running.")
    print(f"Bound to: {bound_host}:{bound_port}")
    if args.http_host in ("0.0.0.0", "::"):
        print(f"Open from this computer: http://127.0.0.1:{bound_port}")
        lan_ip = _guess_lan_ipv4()
        if lan_ip:
            print(f"Open from Wi-Fi devices: http://{lan_ip}:{bound_port}")
        else:
            print(f"Open from Wi-Fi devices: http://<this-computer-ip>:{bound_port}")
    else:
        print(f"Open: http://{args.http_host}:{bound_port}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("Stopping server...")
    finally:
        server.server_close()
        iface.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Meshtastic map view with realtime or one-shot mode."
    )
    add_mesh_connection_args(parser, default_mesh_port=DEFAULT_MESH_PORT)
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Run one-shot capture and write HTML, then exit.",
    )
    parser.add_argument(
        "--listen-seconds",
        type=int,
        default=30,
        help="Seconds to capture traffic before writing snapshot HTML (snapshot mode only).",
    )
    parser.add_argument(
        "--output",
        default="mesh_map.html",
        help="Output HTML path for snapshot mode.",
    )
    parser.add_argument(
        "--http-host",
        default=DEFAULT_HTTP_HOST,
        help=f"HTTP bind host for realtime mode (default: {DEFAULT_HTTP_HOST})",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=DEFAULT_HTTP_PORT,
        help=f"HTTP bind port for realtime mode (default: {DEFAULT_HTTP_PORT})",
    )
    parser.add_argument(
        "--refresh-ms",
        type=int,
        default=DEFAULT_REFRESH_MS,
        help=f"Browser polling interval in milliseconds for realtime mode (default: {DEFAULT_REFRESH_MS})",
    )
    args = parser.parse_args()

    if args.snapshot:
        run_snapshot_mode(args)
    else:
        run_realtime_mode(args)


if __name__ == "__main__":
    main()
