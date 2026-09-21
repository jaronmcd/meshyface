(() => {
  const fixture = BENCH_FIXTURE;
  const nodes = fixture.nodes;
  const ids = nodes.map(n => n.id);
  const graphNodes = new Map(nodes.map(n => [n.id, n]));
  const edges = [];
  for (let i = 1; i < ids.length; i++) {
    for (const offset of [1, 3, 11]) {
      const peer = Math.max(0, i - offset);
      if (!edges.some(e => e.a === ids[peer] && e.b === ids[i])) {
        edges.push({a: ids[peer], b: ids[i], weight: 10, avgHops: 1, lastSeenUnix: 1800000000});
      }
    }
  }
  const adjacency = buildNetworkGraphAdjacency(graphNodes, edges);
  const targets = ids.filter((_, i) => i > 0 && i % 3 === 0);
  function search() {
    if (typeof chatNodeNavigatorLinkQualityPathStats === 'function') {
      return chatNodeNavigatorLinkQualityPathStats(
        chatNodeNavigatorBuildLinkQualityGraph(adjacency), ids[0], targets, 4);
    }
    return new Map(targets.map(id => [id,
      chatNodeNavigatorEstimatePathDiversity(ids[0], id, adjacency, 4)]));
  }
  search(); // Warm up both implementations with the same graph.
  let started = performance.now();
  const quality = search();
  const qualityMs = performance.now() - started;
  if (quality.size !== targets.length || ![...quality.values()].every(v => v.reachable)) {
    throw new Error('Roster workload did not search every reachable target');
  }
  setActiveNetworkSubview('map', {persist: false});
  applyLayoutView('network', false);
  map.invalidateSize();
  const mapNodes = nodes.slice(0, 150).map((n, i) => ({
    ...n, short_name: '📻', long_name: '📻 Bench ' + i,
    lat: 44.95 + i * 0.0001, lon: -93.2 + i * 0.0001
  }));
  const state = {...fixture, nodes: mapNodes.concat(nodes.slice(150))};
  const markers = mapNodes.map(n => createMapNodeMarker(n.lat, n.lon, n.id, false, 'actual', 0.45, state).addTo(map));
  let iconWrites = 0;
  try {
    for (const marker of markers) {
      if (!marker.getElement()?.querySelector('.map-node-emoji-glyph')) {
        throw new Error('Map workload did not create emoji markers');
      }
      const setIcon = marker.setIcon;
      marker.setIcon = function(...args) { iconWrites++; return setIcon.apply(this, args); };
    }
    const refresh = () => {
      // New state object per poll, unchanged marker appearance.
      const next = {...state, nodes: state.nodes.map(n => ({...n}))};
      markers.forEach((marker, i) => refreshMapNodeMarkerPresentation(marker, mapNodes[i].id, false, 'actual', 0.45, next));
    };
    refresh();
    iconWrites = 0;
    started = performance.now();
    for (let i = 0; i < 20; i++) refresh();
    const mapMs = performance.now() - started;
    return {
      roster_ms: qualityMs, roster_targets: targets.length, graph_edges: edges.length,
      map_refresh_ms: mapMs, map_icon_writes: iconWrites, map_markers: markers.length,
      quality: [...quality].map(([id, value]) => [id, value.pathCount, value.hops, value.reachable])
    };
  } finally { markers.forEach(marker => marker.remove()); }
})()
