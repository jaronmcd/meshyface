"""Behavioral guards for the chat roster Link-quality computation.

The roster's Quality field runs a path-diversity search from the local node to every
roster node over the all-time link graph. On the live mesh that is hundreds of targets
over thousands of edges, and the original Map-and-object search cost ~5.4 s per chat
render (2026-09-18). The indexed search that replaced it must produce exactly the same
results, stay within a time budget as the mesh grows, and be cached on its real inputs.

These run the generated dashboard JavaScript in headless Chromium, so they are opt-in
like the other browser probes: MESH_GUI_BENCH_RUN=1 or --run-gui-benchmark.
"""

from __future__ import annotations

import html
import json
import os
import random
import shutil
import subprocess

import pytest

from meshdash.html_js import build_dashboard_js

# Generous ceilings: the point is to fail loudly on an algorithmic regression (the
# original took ~5,400 ms at 1x on a workstation), not to pin a CI machine's speed.
BUDGET_1X_MS = 600
BUDGET_2X_MS = 2500


def _function_block(source: str, start: str, end: str) -> str:
    assert source.count(start) == 1, f"expected one occurrence of {start!r}, found {source.count(start)}"
    body = source.split(start, 1)[1]
    assert end in body, f"end marker {end!r} not found after {start!r}"
    return start + body.split(end, 1)[0]


# The search as it shipped before 2026-09-18, kept verbatim (renamed) as the oracle.
ORACLE_JS = r"""
function oracleMinHeapPush(heap, nodeId, distance) {
  const targetHeap = Array.isArray(heap) ? heap : [];
  const entry = { nodeId: normalizeNodeId(nodeId || ""), distance: Number(distance) || 0 };
  targetHeap.push(entry);
  let index = targetHeap.length - 1;
  while (index > 0) {
    const parent = Math.floor((index - 1) / 2);
    if (targetHeap[parent].distance <= targetHeap[index].distance) break;
    const swap = targetHeap[parent];
    targetHeap[parent] = targetHeap[index];
    targetHeap[index] = swap;
    index = parent;
  }
  return targetHeap;
}
function oracleMinHeapPop(heap) {
  if (!Array.isArray(heap) || heap.length <= 0) return null;
  const first = heap[0];
  const last = heap.pop();
  if (heap.length > 0 && last) {
    heap[0] = last;
    let index = 0;
    while (true) {
      const left = (index * 2) + 1;
      const right = left + 1;
      let smallest = index;
      if (left < heap.length && heap[left].distance < heap[smallest].distance) smallest = left;
      if (right < heap.length && heap[right].distance < heap[smallest].distance) smallest = right;
      if (smallest === index) break;
      const swap = heap[index];
      heap[index] = heap[smallest];
      heap[smallest] = swap;
      index = smallest;
    }
  }
  return first;
}
function oracleFindWeightedPath(sourceNodeId, targetNodeId, adjacency, blockedEdgeKeys = null) {
  const source = normalizeNodeId(sourceNodeId || "");
  const target = normalizeNodeId(targetNodeId || "");
  if (!isSelectableNodeId(source) || !isSelectableNodeId(target) || !(adjacency instanceof Map)
      || !adjacency.has(source) || !adjacency.has(target)) {
    return { path: [], edges: [], cost: Infinity };
  }
  if (source === target) return { path: [source], edges: [], cost: 0 };
  const blocked = blockedEdgeKeys instanceof Set ? blockedEdgeKeys : new Set();
  const distances = new Map([[source, 0]]);
  const previous = new Map();
  const visited = new Set();
  const queue = [];
  oracleMinHeapPush(queue, source, 0);
  while (queue.length > 0) {
    const next = oracleMinHeapPop(queue);
    const currentId = normalizeNodeId(next && next.nodeId);
    const currentDistance = Number(next && next.distance);
    if (!isSelectableNodeId(currentId)) continue;
    if (!Number.isFinite(currentDistance)) continue;
    if (visited.has(currentId)) continue;
    const bestKnownDistance = Number(distances.get(currentId));
    if (!Number.isFinite(bestKnownDistance) || currentDistance > (bestKnownDistance + 1e-9)) continue;
    visited.add(currentId);
    if (currentId === target) break;
    const peers = adjacency.get(currentId);
    if (!(peers instanceof Map)) continue;
    for (const [peerId, edge] of peers.entries()) {
      if (visited.has(peerId)) continue;
      const edgeKey = chatNodeNavigatorLinkQualityEdgeKey(currentId, peerId);
      if (edgeKey && blocked.has(edgeKey)) continue;
      const candidate = currentDistance + chatNodeNavigatorLinkQualityEdgeCost(edge);
      const existing = distances.has(peerId) ? distances.get(peerId) : Infinity;
      if (candidate + 1e-9 < existing) {
        distances.set(peerId, candidate);
        previous.set(peerId, { nodeId: currentId, edge });
        oracleMinHeapPush(queue, peerId, candidate);
      }
    }
  }
  if (!previous.has(target)) return { path: [], edges: [], cost: Infinity };
  const path = [target];
  const edges = [];
  let cursor = target;
  while (cursor !== source) {
    const step = previous.get(cursor);
    if (!step || !step.nodeId) return { path: [], edges: [], cost: Infinity };
    edges.unshift(step.edge);
    cursor = step.nodeId;
    path.unshift(cursor);
  }
  return { path, edges, cost: Number(distances.get(target) || 0) };
}
function oracleEstimatePathDiversity(sourceNodeId, targetNodeId, adjacency, maxPaths = 4) {
  const source = normalizeNodeId(sourceNodeId || "");
  const target = normalizeNodeId(targetNodeId || "");
  if (!isSelectableNodeId(source) || !isSelectableNodeId(target) || source === target) {
    return { pathCount: source === target ? 4 : 0, hops: source === target ? 0 : null, reachable: source === target };
  }
  const sourcePeers = adjacency instanceof Map ? adjacency.get(source) : null;
  const targetPeers = adjacency instanceof Map ? adjacency.get(target) : null;
  const sourceDegree = sourcePeers instanceof Map ? sourcePeers.size : 0;
  const targetDegree = targetPeers instanceof Map ? targetPeers.size : 0;
  if (sourceDegree <= 0 || targetDegree <= 0) return { pathCount: 0, hops: null, reachable: false };
  const pathLimit = Math.max(1, Math.min(6, Math.trunc(Number(maxPaths) || 4)));
  const structuralPathLimit = Math.max(1, Math.min(pathLimit, sourceDegree, targetDegree));
  const blockedEdgeKeys = new Set();
  let pathCount = 0;
  let shortestHops = null;
  for (let index = 0; index < structuralPathLimit; index += 1) {
    const inferred = oracleFindWeightedPath(source, target, adjacency, blockedEdgeKeys);
    const path = Array.isArray(inferred && inferred.path) ? inferred.path : [];
    if (path.length <= 1) break;
    const hops = Math.max(0, path.length - 1);
    if (shortestHops == null || hops < shortestHops) shortestHops = hops;
    pathCount += 1;
    const routeEdges = Array.isArray(inferred && inferred.edges) ? inferred.edges : [];
    for (let edgeIndex = 0; edgeIndex < routeEdges.length; edgeIndex += 1) {
      const edgeKey = chatNodeNavigatorLinkQualityEdgeKey(path[edgeIndex], path[edgeIndex + 1]);
      if (edgeKey) blockedEdgeKeys.add(edgeKey);
    }
  }
  return { pathCount, hops: shortestHops, reachable: pathCount > 0 };
}
"""

# Stand-ins for the graph-source helpers the build function calls. They keep the
# membership and placeholder rules that matter here (live nodes, pinned participants and
# edge endpoints; placeholder hops_away = history-caps last_hops clamped at zero).
STUBS_JS = r"""
let latestState = null;
const chatNodeNavigatorLinkQualityCacheByState = new WeakMap();
function resolveLocalNodeId(state) { return state.local_id; }
function chatNodeNavigatorNetworkHistoryModeForSearch() { return "max"; }
function networkGraphRawEdgesForMode(edges) { return edges; }
function filterNetworkGraphRawEdgesByMode(edges) { return edges; }
function networkGraphHistoryCapsForMode(caps) { return caps; }
function buildNetworkGraphNodeMap(nodes, capsRaw, rawEdges, options) {
  const map = new Map();
  for (const node of nodes) {
    const id = normalizeNodeId(node && node.id);
    if (isSelectableNodeId(id) && !map.has(id)) map.set(id, node);
  }
  const caps = new Map(Object.entries(capsRaw || {}).map(([k, v]) => [normalizeNodeId(k), v]));
  const ensure = (raw) => {
    const id = normalizeNodeId(raw || "");
    if (!isSelectableNodeId(id) || map.has(id)) return;
    const c = caps.get(id) || null;
    const h = Number(c && c.last_hops);
    map.set(id, { id, hops_away: Number.isFinite(h) ? Math.max(0, Math.trunc(h)) : null, placeholder: true });
  };
  for (const id of (options.pinnedNodeIds || [])) ensure(id);
  for (const edge of rawEdges) { ensure(edge.from); ensure(edge.to); }
  return map;
}
function combineNetworkGraphEdges(rawEdges, nodeMap) {
  const out = [];
  const seen = new Set();
  for (const edge of rawEdges) {
    const f = normalizeNodeId(edge.from), t = normalizeNodeId(edge.to);
    if (!isSelectableNodeId(f) || !isSelectableNodeId(t) || f === t || !nodeMap.has(f) || !nodeMap.has(t)) continue;
    const weight = Number(edge.lifetime_count ?? edge.count ?? 0);
    if (!(weight > 0)) continue;
    const a = f < t ? f : t, b = f < t ? t : f;
    const key = a + "::" + b;
    if (seen.has(key)) continue;
    seen.add(key);
    const avgHops = Number(edge.avg_hops);
    out.push({ key, a, b, weight, avgHops: Number.isFinite(avgHops) ? avgHops : null, lastSeenUnix: Number(edge.last_rx_unix) || 0 });
  }
  return out;
}
"""

PROBE_JS = r"""
const F = FIXTURE;
const result = { errors: [] };
try {
  // ---- 1. exact equivalence against the original search, on the same adjacency ----
  const nodeMap = new Map(F.graph_nodes.map((id) => [id, { id }]));
  const adjacency = buildNetworkGraphAdjacency(nodeMap, F.edges);
  const t0 = performance.now();
  const oracle = new Map();
  for (const raw of F.roster) {
    const id = normalizeNodeId(raw);
    if (!isSelectableNodeId(id) || id === F.local || oracle.has(id)) continue;
    oracle.set(id, oracleEstimatePathDiversity(F.local, id, adjacency, 4));
  }
  const oracleMs = performance.now() - t0;
  const t1 = performance.now();
  const graph = chatNodeNavigatorBuildLinkQualityGraph(adjacency);
  const stats = chatNodeNavigatorLinkQualityPathStats(graph, F.local, F.roster, 4);
  const newMs = performance.now() - t1;
  const mismatches = [];
  for (const [id, expected] of oracle) {
    const got = stats.get(id);
    if (JSON.stringify(expected) !== JSON.stringify(got)) mismatches.push({ id, expected, got });
  }
  result.equivalence = {
    oracleEntries: oracle.size, newEntries: stats.size,
    sameKeys: JSON.stringify(Array.from(oracle.keys())) === JSON.stringify(Array.from(stats.keys())),
    mismatches: mismatches.slice(0, 10), mismatchCount: mismatches.length,
    oracleMs: Math.round(oracleMs), newMs: Math.round(newMs * 10) / 10,
    reachable: Array.from(stats.values()).filter((s) => s.reachable).length,
    multiPath: Array.from(stats.values()).filter((s) => s.pathCount >= 2).length,
  };

  // ---- 2. budget at 2x ----
  const G2 = FIXTURE_2X;
  const nodeMap2 = new Map(G2.graph_nodes.map((id) => [id, { id }]));
  const adjacency2 = buildNetworkGraphAdjacency(nodeMap2, G2.edges);
  const t2 = performance.now();
  const stats2 = chatNodeNavigatorLinkQualityPathStats(chatNodeNavigatorBuildLinkQualityGraph(adjacency2), G2.local, G2.roster, 4);
  result.budget = { ms1x: Math.round(newMs * 10) / 10, ms2x: Math.round((performance.now() - t2) * 10) / 10,
    entries2x: stats2.size, nodes2x: nodeMap2.size, edges2x: G2.edges.length };

  // ---- 3. hand-built semantics ----
  // T is reachable by S-A-T, S-B-T and S-C-D-T; E is a leaf; X-Y is another component;
  // Z is isolated; "!deadbeef" is a roster id that is not in the graph at all.
  const S = "!0000000a", A = "!0000000b", B = "!0000000c", C = "!0000000d", Dn = "!0000000e";
  const T = "!0000000f", E = "!00000010", X = "!00000011", Y = "!00000012", Z = "!00000013";
  const dNodes = [S, A, B, C, Dn, T, E, X, Y, Z];
  const dEdge = (a, b) => ({ a: a < b ? a : b, b: a < b ? b : a, weight: 1, avgHops: null, lastSeenUnix: 1 });
  const dEdges = [dEdge(S, A), dEdge(A, T), dEdge(S, B), dEdge(B, T), dEdge(S, C), dEdge(C, Dn), dEdge(Dn, T), dEdge(S, E), dEdge(X, Y)];
  const dAdj = buildNetworkGraphAdjacency(new Map(dNodes.map((id) => [id, { id }])), dEdges);
  const dStats = chatNodeNavigatorLinkQualityPathStats(chatNodeNavigatorBuildLinkQualityGraph(dAdj), S, dNodes.concat(["!deadbeef"]), 4);
  const dOracle = new Map();
  for (const id of dNodes.concat(["!deadbeef"])) if (id !== S) dOracle.set(id, oracleEstimatePathDiversity(S, id, dAdj, 4));
  result.diamond = {
    T: dStats.get(T), E: dStats.get(E), D: dStats.get(Dn), X: dStats.get(X), Z: dStats.get(Z), absent: dStats.get("!deadbeef"),
    matchesOracle: Array.from(dOracle).every(([id, v]) => JSON.stringify(v) === JSON.stringify(dStats.get(id))),
  };

  // ---- 4. the build function: content-keyed cache and hop-candidate rules ----
  let pathStatsCalls = 0;
  const realPathStats = chatNodeNavigatorLinkQualityPathStats;
  chatNodeNavigatorLinkQualityPathStats = function (...args) { pathStatsCalls += 1; return realPathStats.apply(this, args); };
  const rawEdges = F.edges.map((e) => ({ from: e.a, to: e.b, lifetime_count: e.weight, count: e.weight, avg_hops: e.avgHops, last_rx_unix: e.lastSeenUnix }));
  const mkState = (edges, nodes) => ({ local_id: F.local, nodes: nodes || F.live_nodes, history_caps: F.caps, traffic: { edges } });
  const byId = (nodes) => new Map(nodes.map((n) => [normalizeNodeId(n.id), n]));
  const capsById = new Map(Object.entries(F.caps).map(([k, v]) => [normalizeNodeId(k), v]));
  const s1 = mkState(rawEdges);
  const r1 = buildChatNodeNavigatorLinkQualityByNode(s1, byId(s1.nodes), capsById, F.roster);
  const calls1 = pathStatsCalls;
  const s2 = mkState(rawEdges.map((e) => ({ ...e })));           // new state, new array, same content
  const r2 = buildChatNodeNavigatorLinkQualityByNode(s2, byId(s2.nodes), capsById, F.roster);
  const calls2 = pathStatsCalls;
  const s4 = mkState(rawEdges, F.live_nodes.map((n) => ({ ...n, hops_away: 6 })));  // hops change, edges do not
  const r4 = buildChatNodeNavigatorLinkQualityByNode(s4, byId(s4.nodes), capsById, F.roster);
  const calls3 = pathStatsCalls;
  const changed = rawEdges.map((e) => ({ ...e }));
  changed[7].lifetime_count += 1; changed[7].count += 1;          // one edge weight changes
  const s3 = mkState(changed);
  buildChatNodeNavigatorLinkQualityByNode(s3, byId(s3.nodes), capsById, F.roster);
  const calls4 = pathStatsCalls;
  chatNodeNavigatorLinkQualityPathStats = realPathStats;

  // Expected r1 the original way: hop candidates from nodesById || nodeMap placeholder,
  // path stats from the oracle over the adjacency the build function constructs.
  const nodeMapB = buildNetworkGraphNodeMap(s1.nodes, s1.history_caps, rawEdges, { pinnedNodeIds: [F.local].concat(F.roster) });
  const adjB = buildNetworkGraphAdjacency(nodeMapB, combineNetworkGraphEdges(rawEdges, nodeMapB));
  const nodesById1 = byId(s1.nodes);
  const assemblyMismatches = [];
  for (const [id, got] of r1) {
    if (id === F.local) continue;
    const node = nodesById1.get(id) || nodeMapB.get(id) || null;
    const caps = capsById.get(id) || null;
    const cands = [];
    const live = Number(node && (node.hops_away ?? node.hopsAway));
    if (Number.isFinite(live) && live >= 0) cands.push(Math.max(0, Math.trunc(live)));
    const ch = Number(caps && caps.last_hops);
    if (Number.isFinite(ch) && ch >= 0) cands.push(Math.max(0, Math.trunc(ch)));
    const ps = oracleEstimatePathDiversity(F.local, id, adjB, 4);
    const inferred = Number.isFinite(Number(ps.hops)) ? Math.max(0, Math.trunc(Number(ps.hops))) : null;
    const hopCount = cands.length > 0 ? Math.min(...cands) : inferred;
    const expected = chatNodeNavigatorInferLinkQuality(hopCount, ps.pathCount, { reachable: !!ps.reachable });
    if (JSON.stringify(expected) !== JSON.stringify(got)) assemblyMismatches.push({ id, expected, got });
  }
  let hopsChangedRows = 0;
  for (const [id, v] of r4) if (JSON.stringify(v) !== JSON.stringify(r1.get(id))) hopsChangedRows += 1;
  result.cache = {
    calls: [calls1, calls2, calls3, calls4],
    sameResultOnRefetch: JSON.stringify(Array.from(r1)) === JSON.stringify(Array.from(r2)),
    assemblyMismatchCount: assemblyMismatches.length, assemblyMismatches: assemblyMismatches.slice(0, 5),
    entries: r1.size, hopsChangedRows,
    placeholderParticipants: F.roster.filter((id) => !nodesById1.has(normalizeNodeId(id)) && nodeMapB.has(normalizeNodeId(id))).length,
  };
} catch (err) {
  result.errors.push(String(err && err.stack || err));
}
document.getElementById("result").textContent = JSON.stringify(result);
"""


def _node_id(rng: random.Random, used: set[str]) -> str:
    while True:
        candidate = f"!{rng.getrandbits(32):08x}"
        if candidate not in used:
            used.add(candidate)
            return candidate


def _fixture(seed: int, scale: int) -> dict:
    """A synthetic mesh shaped like the live one: a hub-heavy main component with many
    leaves and repeated tie weights, a second component the local node cannot reach,
    isolated nodes, and a roster that also names nodes outside the graph."""
    rng = random.Random(seed)
    used: set[str] = set()
    main = [_node_id(rng, used) for _ in range(1100 * scale)]
    local = main[0]
    other = [_node_id(rng, used) for _ in range(60 * scale)]
    isolated = [_node_id(rng, used) for _ in range(40 * scale)]
    pairs: set[tuple[str, str]] = set()

    def link(a: str, b: str) -> None:
        if a != b:
            pairs.add((a, b) if a < b else (b, a))

    for index in range(1, len(main)):
        degree = 1 if rng.random() < 0.45 else rng.randint(2, 4)
        for _ in range(degree):
            if rng.random() < 0.14:
                link(main[index], local)
            else:
                link(main[index], main[int(index * rng.random() ** 2)])
    while len(pairs) < 3300 * scale:
        link(rng.choice(main), main[int(len(main) * rng.random() ** 2)])
    other_pairs: set[tuple[str, str]] = set()
    for index in range(1, len(other)):
        a, b = other[index], other[rng.randrange(index)]
        other_pairs.add((a, b) if a < b else (b, a))
    while len(other_pairs) < 100 * scale:
        a, b = rng.choice(other), rng.choice(other)
        if a != b:
            other_pairs.add((a, b) if a < b else (b, a))
    edges = []
    for a, b in sorted(pairs | other_pairs):
        weight = rng.randint(1, 5) if rng.random() < 0.6 else min(3000, int(rng.expovariate(1 / 200)) + 6)
        edges.append({
            "a": a, "b": b, "weight": weight,
            "avgHops": None if rng.random() < 0.3 else round(rng.uniform(0, 6), 2),
            "lastSeenUnix": 0 if rng.random() < 0.1 else 1_700_000_000 + rng.randint(0, 10_000_000),
        })
    rng.shuffle(edges)
    roster = (rng.sample(main[1:], 330 * scale) + rng.sample(other, 30 * scale) + rng.sample(isolated, 25 * scale)
              + [_node_id(rng, used) for _ in range(10)])
    roster += roster[:5]  # duplicates
    roster.insert(len(roster) // 2, local)
    roster[3] = roster[3].upper()  # exercises id normalization
    rng.shuffle(roster)
    graph_nodes = main + other + isolated
    live_nodes = []
    for node_id in graph_nodes:
        if rng.random() < 0.7:
            live_nodes.append({"id": node_id, "hops_away": rng.choice([None, None, 0, 1, 2, 3, 4, 7, -1])})
    caps = {}
    for node_id in graph_nodes:
        if rng.random() < 0.6:
            caps[node_id] = {"last_hops": rng.choice([None, 0, 1, 2, 3, 5, -1, -2])}
    return {"local": local, "graph_nodes": graph_nodes, "edges": edges, "roster": roster,
            "live_nodes": live_nodes, "caps": caps}


@pytest.mark.gui_benchmark
def test_link_quality_indexed_search_matches_original_and_stays_in_budget(
    request: pytest.FixtureRequest,
    tmp_path,
) -> None:
    enabled = bool(request.config.getoption("--run-gui-benchmark")) or (
        os.environ.get("MESH_GUI_BENCH_RUN", "").strip().lower() in {"1", "true", "yes", "on"}
    )
    if not enabled:
        pytest.skip("set MESH_GUI_BENCH_RUN=1 or pass --run-gui-benchmark")
    chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    if not chromium:
        pytest.skip("Chromium is required for the JavaScript link-quality probe")

    js = build_dashboard_js(refresh_ms=1000, node_history_hours=24, node_history_max_points=240)
    blocks = [
        _function_block(js, "function normalizeNodeId(nodeId) {", "function isCanonicalNodeId"),
        _function_block(js, "function isSelectableNodeId(nodeId) {", "function parseNodeNum"),
        _function_block(js, "function networkRoutesEdgeCost(edge) {", "function networkRoutesFindInferredPath"),
        _function_block(js, "function networkGraphEdgeKeyBetween(fromNodeId, toNodeId) {", "function buildNetworkGraphEdgeDomKey"),
        _function_block(js, "function buildNetworkGraphAdjacency(nodeMap, edges) {", "function compareNetworkGraphComponents"),
        _function_block(
            js,
            "function chatNodeNavigatorLinkQualityParticipantSignature(participantNodeIds = []) {",
            "function noteChatNodeNavigatorProgrammaticScrollReset",
        ),
    ]
    fixture = _fixture(seed=20260918, scale=1)
    fixture_2x = _fixture(seed=20260919, scale=2)
    page = "<!doctype html><meta charset=\"utf-8\"><pre id=\"result\"></pre><script>\n" + "\n".join(blocks) \
        + "\n" + STUBS_JS + ORACLE_JS \
        + f"\nconst FIXTURE = {json.dumps(fixture)};\nconst FIXTURE_2X = {json.dumps(fixture_2x)};\n" \
        + PROBE_JS + "\n</script>"
    probe_path = tmp_path / "link_quality_probe.html"
    probe_path.write_text(page, encoding="utf-8")

    completed = subprocess.run(
        [chromium, "--headless", "--no-sandbox", "--disable-gpu",
         f"--user-data-dir={tmp_path / 'chromium-profile'}", "--dump-dom", probe_path.as_uri()],
        check=False, capture_output=True, text=True, timeout=300,
    )
    if completed.returncode != 0:
        if "Operation not permitted" in completed.stderr:
            pytest.skip("Chromium launch is blocked by the current process sandbox")
        pytest.fail(f"Chromium probe failed with exit {completed.returncode}: {completed.stderr[-2000:]}")
    marker = '<pre id="result">'
    assert marker in completed.stdout, completed.stdout[-2000:]
    result = json.loads(html.unescape(completed.stdout.split(marker, 1)[1].split("</pre>", 1)[0]))
    assert result["errors"] == [], result["errors"]

    equivalence = result["equivalence"]
    print(f"\nlink quality: original {equivalence['oracleMs']} ms -> indexed {equivalence['newMs']} ms "
          f"over {equivalence['newEntries']} roster nodes ({equivalence['reachable']} reachable, "
          f"{equivalence['multiPath']} multi-path); 2x mesh {result['budget']['ms2x']} ms")
    assert equivalence["oracleEntries"] == equivalence["newEntries"] >= 390
    assert equivalence["sameKeys"], "roster order or membership differs"
    assert equivalence["mismatchCount"] == 0, equivalence["mismatches"]
    assert equivalence["reachable"] > 250 and equivalence["multiPath"] > 50, "fixture is not exercising multi-path targets"

    diamond = result["diamond"]
    assert diamond["T"] == {"pathCount": 3, "hops": 2, "reachable": True}
    assert diamond["D"] == {"pathCount": 2, "hops": 2, "reachable": True}
    assert diamond["E"] == {"pathCount": 1, "hops": 1, "reachable": True}
    assert diamond["X"] == diamond["Z"] == diamond["absent"] == {"pathCount": 0, "hops": None, "reachable": False}
    assert diamond["matchesOracle"]

    budget = result["budget"]
    assert budget["ms1x"] < BUDGET_1X_MS, f"1x mesh took {budget['ms1x']} ms (budget {BUDGET_1X_MS})"
    assert budget["ms2x"] < BUDGET_2X_MS, f"2x mesh took {budget['ms2x']} ms (budget {BUDGET_2X_MS})"

    cache = result["cache"]
    assert cache["assemblyMismatchCount"] == 0, cache["assemblyMismatches"]
    assert cache["placeholderParticipants"] > 20, "fixture has too few non-live participants"
    # Path stats are computed once, reused for a refetched-but-identical edge set and for a
    # hop-only state change, and recomputed once an edge changes.
    assert cache["calls"] == [1, 1, 1, 2], f"path stats recomputed unexpectedly: {cache['calls']}"
    assert cache["sameResultOnRefetch"]
    assert cache["hopsChangedRows"] > 0, "a hop change in the state must reach the result without an edge change"
