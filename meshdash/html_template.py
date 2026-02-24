from .html_context import build_html_render_context as _build_html_render_context_helper

def render_html(
    refresh_ms: int,
    packet_limit: int,
    show_secrets: bool,
    history_enabled: bool,
    history_max_rows: int,
    history_retention_days: int,
    node_history_hours: int,
    node_history_max_points: int,
    revision_label: str,
    revision_title: str,
) -> str:
    render_context = _build_html_render_context_helper(
        show_secrets=show_secrets,
        history_enabled=history_enabled,
        history_max_rows=history_max_rows,
        history_retention_days=history_retention_days,
    )
    safety_label = render_context["safety_label"]
    history_label = render_context["history_label"]
    theme_css = render_context["theme_css"]
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Meshtastic Dashboard</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  />
  <style>
{theme_css}
    * {{ box-sizing: border-box; }}
    html, body {{
      margin: 0;
      padding: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 20% -10%, #d7ead3 0, transparent 45%),
        radial-gradient(circle at 80% 0%, #d0e6d4 0, transparent 40%),
        var(--bg);
      min-height: 100%;
    }}
    .topbar {{
      padding: 10px 14px;
      background: linear-gradient(100deg, #173d2d, #2d6f50);
      color: #f4fff7;
      box-shadow: var(--shadow);
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    .topbar h1 {{ margin: 0; font-size: 16px; letter-spacing: 0.1px; }}
    .topbar .sub {{
      margin-top: 2px;
      font-size: 11px;
      opacity: 0.95;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .topbar .sub .sub-text {{
      margin-right: 2px;
    }}
    .theme-btn {{
      border: 1px solid rgba(214, 238, 223, 0.55);
      background: rgba(248, 255, 251, 0.12);
      color: #f2fff7;
      border-radius: 999px;
      padding: 3px 10px;
      font-size: 11px;
      line-height: 1.2;
      cursor: pointer;
      white-space: nowrap;
    }}
    .theme-btn:hover {{
      background: rgba(248, 255, 251, 0.22);
    }}
    .workspace-shell {{
      --rail-width: 72px;
      --chat-panel-width: 250px;
      display: grid;
      grid-template-columns: var(--rail-width) minmax(0, 1fr);
      gap: 8px;
      padding: 8px;
      align-items: start;
    }}
    .workspace-shell.chat-panel-open {{
      grid-template-columns: var(--rail-width) minmax(190px, var(--chat-panel-width)) minmax(0, 1fr);
    }}
    .workspace-main {{
      min-width: 0;
      width: 100%;
    }}
    .teams-rail {{
      position: sticky;
      top: 84px;
      height: calc(100vh - 96px);
      min-height: 420px;
      border: 1px solid #c6d6c0;
      border-radius: 10px;
      background: #eef6ee;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 8px 6px;
      overflow-y: auto;
    }}
    .teams-rail-title {{
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.35px;
      color: #355445;
      text-transform: uppercase;
      text-align: center;
      margin-bottom: 2px;
    }}
    .rail-btn {{
      border: 1px solid #c4d8c6;
      background: #f4faf3;
      color: #234735;
      border-radius: 8px;
      padding: 6px 4px;
      font-size: 10px;
      line-height: 1.2;
      text-align: center;
      cursor: pointer;
    }}
    .rail-btn:hover {{
      background: #e7f3eb;
    }}
    .rail-btn.has-unread {{
      border-color: #2f855a;
      box-shadow: inset 0 0 0 1px rgba(47, 133, 90, 0.22);
      font-weight: 700;
    }}
    .rail-btn.active {{
      background: #2f855a;
      border-color: #256f4a;
      color: #effff4;
      font-weight: 700;
    }}
    .chat-left-panel {{
      position: sticky;
      top: 84px;
      height: calc(100vh - 96px);
      min-height: 420px;
      border: 1px solid #c6d6c0;
      border-radius: 10px;
      background: #f6fbf5;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      min-width: 0;
      overflow: hidden;
    }}
    .chat-left-panel[hidden] {{
      display: none !important;
    }}
    .chat-left-head {{
      border-bottom: 1px solid #d2e1d0;
      background: #edf6ec;
      padding: 8px 10px 7px 10px;
    }}
    .chat-left-title {{
      font-size: 11px;
      font-weight: 700;
      color: #274935;
      letter-spacing: 0.15px;
      text-transform: uppercase;
    }}
    .chat-left-sub {{
      font-size: 10px;
      color: #4a6958;
      margin-top: 3px;
    }}
    .chat-left-section {{
      border-bottom: 1px solid #d9e7d6;
      padding: 7px 6px 6px 6px;
      background: #f7fcf7;
    }}
    .chat-left-section.chat-users-section {{
      border-bottom: none;
      flex: 1 1 auto;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .chat-left-label {{
      font-size: 10px;
      color: #466656;
      text-transform: uppercase;
      letter-spacing: 0.2px;
      margin: 0 0 5px 2px;
      font-weight: 700;
    }}
    .chat-channel-list {{
      display: flex;
      flex-direction: column;
      gap: 4px;
    }}
    .chat-channel-item {{
      border: 1px solid #c7dac5;
      background: #eef8ef;
      color: #214434;
      border-radius: 7px;
      padding: 6px 7px;
      font-size: 10px;
      line-height: 1.15;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      min-width: 0;
      text-align: left;
    }}
    .chat-channel-item:hover {{
      background: #e4f2e7;
    }}
    .chat-channel-item.active {{
      background: #d8efe1;
      border-color: #99c5aa;
      color: #173e2b;
      font-weight: 700;
    }}
    .chat-channel-main {{
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}
    .chat-channel-name {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .chat-channel-unread-from {{
      font-size: 9px;
      color: #486959;
      opacity: 0.95;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
    }}
    .chat-channel-meta {{
      font-size: 9px;
      color: #5f7b6c;
      opacity: 0.92;
      white-space: nowrap;
      flex: 0 0 auto;
    }}
    .chat-channel-meta-wrap {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      flex: 0 0 auto;
    }}
    .chat-channel-unread {{
      font-size: 9px;
      line-height: 1;
      font-weight: 700;
      color: #13442d;
      background: #dff1e6;
      border: 1px solid #9bc7ab;
      border-radius: 999px;
      padding: 1px 5px;
      min-width: 18px;
      text-align: center;
    }}
    .chat-left-panel .chat-member-list {{
      padding: 6px;
      flex: 1 1 auto;
    }}
    .list-search-input,
    #chat-input {{
      width: 100%;
      border: 1px solid #c2d8c7;
      border-radius: 7px;
      padding: 5px 7px;
      font-size: 11px;
      line-height: 1.25;
      color: #183223;
      background: #f9fdf9;
      box-sizing: border-box;
      appearance: none;
      -webkit-appearance: none;
      min-height: 27px;
    }}
    .list-search-input:focus,
    #chat-input:focus {{
      outline: 2px solid #9ac5aa;
      outline-offset: 0;
      border-color: #9ac5aa;
      background: #ffffff;
      box-shadow: none;
    }}
    .chat-user-search-wrap {{
      padding: 0;
    }}
    .chat-left-bottom-bar {{
      border: 1px solid #c8dacc;
      border-radius: 10px;
      background: #f3faf5;
      padding: 6px;
      flex: 0 0 auto;
    }}
    .nodes-search-wrap {{
      padding: 0 0 2px 0;
    }}
    .chat-member-empty {{
      border: 1px dashed #d2e2d4;
      border-radius: 8px;
      padding: 9px;
      font-size: 11px;
      color: #5d7566;
      background: #f8fcf8;
      line-height: 1.3;
      margin: 2px 4px 0 4px;
    }}
    .favorites-search-wrap {{
      flex: 1 1 auto;
      min-width: 0;
    }}
    .favorites-clear-btn {{
      border: 1px solid #c2d8c7;
      background: #f4faf3;
      color: #214434;
      border-radius: 7px;
      padding: 5px 9px;
      font-size: 11px;
      line-height: 1.2;
      cursor: pointer;
      white-space: nowrap;
    }}
    .favorites-clear-btn:hover {{
      background: #e7f3eb;
    }}
    .layout {{
      --split-left-pct: 64%;
      --splitter-size: 8px;
      --split-top-px: 430px;
      --split-mid-px: 250px;
      --split-low-px: 240px;
      --network-nodes-list-pct: 52%;
      display: grid;
      gap: 8px;
      padding: 0;
      grid-template-columns: minmax(380px, var(--split-left-pct)) var(--splitter-size) minmax(320px, 1fr);
      grid-template-rows:
        auto
        minmax(240px, var(--split-top-px))
        var(--splitter-size)
        minmax(180px, var(--split-mid-px))
        var(--splitter-size)
        minmax(260px, 380px)
        auto
        minmax(160px, var(--split-low-px))
        var(--splitter-size)
        auto;
      align-items: stretch;
      width: 100%;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 10px;
      box-shadow: var(--shadow);
      overflow: hidden;
      scroll-margin-top: 84px;
    }}
    .card h2 {{
      margin: 0;
      padding: 8px 10px;
      font-size: 13px;
      border-bottom: 1px solid var(--line);
      background: #f8fbf7;
    }}
    .card.chat {{
      border: 1px solid #c6d6c0;
      background: #f6fbf5;
      display: flex;
      flex-direction: column;
    }}
    .chat-card-head {{
      border-bottom: 1px solid #d2e1d0;
      background: #edf6ec;
      padding: 8px 10px 7px 10px;
    }}
    .chat-card-head h2 {{
      margin: 0;
      font-size: 11px;
      font-weight: 700;
      color: #274935;
      letter-spacing: 0.15px;
      text-transform: uppercase;
      border: 0;
      background: transparent;
      padding: 0;
    }}
    .card .body {{
      padding: 8px 10px;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(115px, 1fr));
      gap: 6px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 6px 7px;
      background: #fcfffc;
    }}
    .metric-action {{
      cursor: pointer;
      user-select: none;
      transition: border-color 140ms ease, background 140ms ease, box-shadow 140ms ease;
    }}
    .metric-action:hover {{
      background: #f2faf4;
      border-color: #a8c7b4;
    }}
    .metric-action:focus-visible {{
      outline: 2px solid #2f855a;
      outline-offset: 2px;
    }}
    .metric-action.active {{
      border-color: #2f855a;
      box-shadow: inset 0 0 0 1px rgba(47, 133, 90, 0.2);
      background: #eef8f1;
    }}
    .metric .label {{ font-size: 10px; color: var(--muted); }}
    .metric .value {{ font-size: 15px; font-weight: 700; margin-top: 2px; line-height: 1.1; }}
    .summary {{ grid-column: 1 / span 3; grid-row: 1; }}
    .map {{
      grid-column: 1 / span 3;
      grid-row: 6;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .map .body {{
      padding: 8px 10px;
      display: flex;
      flex: 1 1 auto;
      min-height: 0;
    }}
    .map-frame {{
      flex: 1 1 auto;
      width: 100%;
      max-width: none;
      margin: 0;
      min-height: 260px;
      border: 1px solid #d7e5d2;
      border-radius: 8px;
      overflow: hidden;
      background: #eef6ee;
    }}
    .map-frame.map-wheel-active {{
      border-color: #8ab79b;
      box-shadow: inset 0 0 0 2px rgba(138, 183, 155, 0.55);
    }}
    .saved-node-details {{
      display: none;
      flex: 1 1 auto;
      min-height: 0;
      border: 1px solid #d7e5d2;
      border-radius: 8px;
      background: #f9fdf9;
      padding: 8px;
      overflow: auto;
    }}
    .saved-node-details-empty {{
      border: 1px dashed #c6d8cc;
      border-radius: 8px;
      background: #f7fcf8;
      color: #446355;
      font-size: 12px;
      line-height: 1.35;
      padding: 12px;
    }}
    .saved-node-details-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      border-bottom: 1px solid #d7e5d2;
      padding-bottom: 8px;
      flex-wrap: wrap;
    }}
    .saved-node-title-wrap {{
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}
    .saved-node-title {{
      font-size: 15px;
      font-weight: 700;
      color: #1a3b2b;
      line-height: 1.2;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .saved-node-subtitle {{
      font-size: 11px;
      color: #4d6759;
      line-height: 1.2;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .saved-node-status {{
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.2px;
      text-transform: uppercase;
      border: 1px solid #c7dac5;
      border-radius: 999px;
      padding: 2px 8px;
      background: #edf5ef;
      color: #2f4f3d;
      white-space: nowrap;
    }}
    .saved-node-status.status-online {{
      border-color: #2f855a;
      background: #e9f8ee;
      color: #1d5a3b;
    }}
    .saved-node-status.status-warn {{
      border-color: #d3a856;
      background: #fff8e8;
      color: #7a5a1f;
    }}
    .saved-node-status.status-stale {{
      border-color: #ce8e8e;
      background: #fff2f2;
      color: #7a2f2f;
    }}
    .saved-node-sections {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      min-height: 0;
    }}
    .saved-node-section {{
      border: 1px solid #d7e5d2;
      border-radius: 8px;
      background: #fbfffb;
      padding: 8px;
    }}
    .saved-node-section-title {{
      margin: 0 0 6px 0;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.35px;
      color: #5b7467;
    }}
    .saved-node-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 6px;
    }}
    .saved-node-stat {{
      border: 1px solid #deeadf;
      border-radius: 8px;
      background: #f6fcf7;
      padding: 6px 7px;
      min-width: 0;
    }}
    .saved-node-stat-k {{
      font-size: 10px;
      color: #5a7264;
      text-transform: uppercase;
      letter-spacing: 0.2px;
      line-height: 1.2;
    }}
    .saved-node-stat-v {{
      margin-top: 2px;
      font-size: 12px;
      color: #183926;
      font-weight: 600;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }}
    .saved-node-note {{
      margin-top: 6px;
      font-size: 10px;
      color: #5d7467;
      line-height: 1.25;
    }}
    #map {{
      width: 100%;
      height: 100%;
      min-height: 0;
    }}
    .chat {{
      grid-column: 1 / span 3;
      grid-row: 2;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .map-data {{
      grid-column: 1 / span 3;
      grid-row: 7;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .map-data .body {{
      flex: 1 1 auto;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .map-data-live, .map-data-node, .map-data-activity {{
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex: 1 1 auto;
    }}
    .map-data-live[hidden], .map-data-node[hidden], .map-data-activity[hidden] {{
      display: none !important;
    }}
    .history-caption {{
      font-size: 12px;
      color: #3e5a46;
      line-height: 1.35;
    }}
    .history-tabs {{
      display: flex;
      gap: 6px;
      border-bottom: 1px solid #d7e5d2;
      padding-bottom: 6px;
    }}
    .history-tab-btn {{
      border: 1px solid #c2d8c7;
      background: #f3faf5;
      color: #1f5d40;
      border-radius: 999px;
      font-size: 11px;
      padding: 4px 10px;
      cursor: pointer;
    }}
    .history-tab-btn.active {{
      background: #dff1e6;
      border-color: #87b99a;
      color: #14442d;
      font-weight: 600;
    }}
    .history-panel[hidden] {{
      display: none !important;
    }}
    #signal-chart-wrap, #online-activity-chart-wrap {{
      position: relative;
      width: 100%;
      min-height: 220px;
      height: 220px;
      border: 1px solid #d7e5d2;
      border-radius: 8px;
      background: linear-gradient(180deg, #fbfffc 0%, #eef8f1 100%);
      overflow: hidden;
    }}
    #signal-chart, #online-activity-chart {{
      width: 100%;
      height: 100%;
      display: block;
    }}
    .signal-empty {{
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #5d7467;
      font-size: 12px;
      text-align: center;
      padding: 10px;
      background: rgba(250, 255, 251, 0.9);
    }}
    .signal-empty[hidden] {{
      display: none !important;
    }}
    .signal-legend {{
      margin-top: 6px;
      font-size: 11px;
      color: #284a37;
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .signal-timeline {{
      position: relative;
      height: 34px;
      margin-top: 6px;
    }}
    .signal-timeline-track {{
      position: absolute;
      top: 8px;
      height: 1px;
      background: #c6d8cc;
      border-radius: 1px;
      pointer-events: none;
    }}
    .signal-timeline-mark {{
      position: absolute;
      top: 0;
      transform: translateX(-50%);
      pointer-events: none;
    }}
    .signal-timeline-mark.edge-start {{
      transform: translateX(0);
    }}
    .signal-timeline-mark.edge-end {{
      transform: translateX(-100%);
    }}
    .signal-timeline-tick {{
      width: 1px;
      height: 7px;
      margin-top: 5px;
      background: #6d8577;
      border-radius: 1px;
    }}
    .signal-timeline-label {{
      margin-top: 3px;
      font-size: 10px;
      color: #4f6759;
      white-space: nowrap;
      font-variant-numeric: tabular-nums;
    }}
    .signal-timeline-empty {{
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #5d7467;
      font-size: 11px;
      text-align: center;
      padding: 2px 4px;
    }}
    .activity-legend-nodes {{
      color: #1f6f53;
    }}
    .legend-chip {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }}
    .legend-chip::before {{
      content: "";
      width: 11px;
      height: 2px;
      border-radius: 1px;
      background: currentColor;
    }}
    .overview-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 6px;
    }}
    .overview-item {{
      border: 1px solid #d7e5d2;
      border-radius: 8px;
      background: #f9fdf9;
      padding: 6px 7px;
    }}
    .overview-item .k {{
      color: #5e6e64;
      font-size: 10px;
      text-transform: uppercase;
    }}
    .overview-item .v {{
      margin-top: 2px;
      font-size: 12px;
      font-weight: 600;
      color: #193a28;
      line-height: 1.2;
    }}
    .nodes {{
      grid-column: 1 / span 3;
      grid-row: 4;
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .favorites {{
      grid-column: 1 / span 3;
      grid-row: 4;
      display: none;
      flex-direction: column;
      min-height: 0;
    }}
    .favorites .body {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex: 1 1 auto;
      min-height: 0;
    }}
    .favorites-toolbar {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .favorites-caption {{
      font-size: 11px;
      color: #4a6958;
      line-height: 1.25;
    }}
    .favorites-list {{
      flex: 1 1 auto;
      min-height: 200px;
      max-height: none;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .favorites-empty {{
      border: 1px dashed #d2e2d4;
      border-radius: 8px;
      padding: 10px;
      font-size: 11px;
      color: #5d7566;
      background: #f8fcf8;
      line-height: 1.3;
    }}
    .favorite-node-item {{
      border: 1px solid #c7dac5;
      background: #ecf7ef;
      color: #204233;
      border-radius: 8px;
      padding: 6px 7px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 7px;
      align-items: start;
      cursor: pointer;
    }}
    .favorite-node-item:hover {{
      background: #e2f0e7;
    }}
    .favorite-node-item.status-warn {{
      background: #fff9e7;
      color: #5d4a1b;
      border-color: #ecd89c;
    }}
    .favorite-node-item.status-stale {{
      background: #fff0f0;
      color: #6a3333;
      border-color: #e6b5b5;
    }}
    .favorite-node-item.status-unknown {{
      background: #f2f5f2;
      color: #607268;
      border-color: #d8e3d8;
    }}
    .favorite-node-item.selected-node {{
      background: #d8efe1;
      border-color: #99c5aa;
      color: #16402c;
      box-shadow: inset 2px 0 0 #2f855a;
    }}
    .favorite-node-main {{
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}
    .favorite-node-name-row {{
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
    }}
    .favorite-node-name {{
      font-size: 12px;
      font-weight: 600;
      color: inherit;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      min-width: 0;
    }}
    .favorite-node-id {{
      font-size: 10px;
      color: #5d7566;
      opacity: 0.95;
      white-space: nowrap;
      flex: 0 0 auto;
    }}
    .favorite-node-meta {{
      font-size: 10px;
      color: #5a7462;
      line-height: 1.25;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .nodes .body {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      flex: 1 1 auto;
      min-height: 0;
      overflow: hidden;
    }}
    .network-node-stack {{
      display: flex;
      flex-direction: column;
      flex: 1 1 auto;
      min-height: 0;
      gap: 0;
    }}
    .nodes-table-scroll {{
      flex: 1 1 auto;
      max-height: none;
      min-height: 0;
    }}
    .network-node-splitter {{
      display: none;
      position: relative;
      border-radius: 8px;
      border: 1px solid #d1e0cb;
      background: linear-gradient(90deg, #f4faf3, #edf5ea);
      cursor: row-resize;
      touch-action: none;
      user-select: none;
      min-height: 6px;
      flex: 0 0 var(--splitter-size);
      margin: 8px 0;
    }}
    .network-node-splitter::before {{
      content: "";
      position: absolute;
      left: 8px;
      right: 8px;
      top: 50%;
      height: 2px;
      transform: translateY(-50%);
      background: #b8cab9;
      border-radius: 1px;
    }}
    .network-node-splitter:hover::before,
    .network-node-splitter.active::before {{
      background: #2f855a;
    }}
    .network-node-history-host {{
      display: none;
      flex-direction: column;
      gap: 8px;
      min-height: 0;
      padding-top: 0;
      border-top: none;
    }}
    .network-node-history-host:not([hidden]) {{
      display: flex;
    }}
    .network-node-history-host.empty::before {{
      content: "Select a node to view signal history and rollups.";
      display: block;
      border: 1px dashed #c3d8c8;
      border-radius: 8px;
      background: #f7fcf8;
      color: #466656;
      font-size: 11px;
      line-height: 1.3;
      padding: 8px 10px;
    }}
    .packets {{ grid-column: 1; grid-row: 8; }}
    .raw {{ grid-column: 3; grid-row: 8; }}
    .console {{ grid-column: 1 / span 3; grid-row: 10; }}
    .splitter {{
      grid-column: 2;
      position: relative;
      border-radius: 8px;
      border: 1px solid #d1e0cb;
      background: linear-gradient(180deg, #f4faf3, #edf5ea);
      cursor: col-resize;
      touch-action: none;
      user-select: none;
      min-width: 6px;
    }}
    .splitter[data-row="8"] {{ grid-row: 8; }}
    .splitter::before {{
      content: "";
      position: absolute;
      left: 50%;
      top: 8px;
      bottom: 8px;
      width: 2px;
      transform: translateX(-50%);
      background: #b8cab9;
      border-radius: 1px;
    }}
    .splitter:hover::before, .splitter.active::before {{
      background: #2f855a;
    }}
    .hsplitter {{
      grid-column: 1 / span 3;
      position: relative;
      border-radius: 8px;
      border: 1px solid #d1e0cb;
      background: linear-gradient(90deg, #f4faf3, #edf5ea);
      cursor: row-resize;
      touch-action: none;
      user-select: none;
      min-height: 6px;
    }}
    .hsplitter[data-target="top"] {{ grid-row: 3; }}
    .hsplitter[data-target="mid"] {{ grid-row: 5; }}
    .hsplitter[data-target="low"] {{ grid-row: 9; }}
    .hsplitter::before {{
      content: "";
      position: absolute;
      left: 8px;
      right: 8px;
      top: 50%;
      height: 2px;
      transform: translateY(-50%);
      background: #b8cab9;
      border-radius: 1px;
    }}
    .hsplitter:hover::before, .hsplitter.active::before {{
      background: #2f855a;
    }}
    body.resizing-panels-x, body.resizing-panels-x * {{
      cursor: col-resize !important;
      user-select: none !important;
    }}
    body.resizing-panels-y, body.resizing-panels-y * {{
      cursor: row-resize !important;
      user-select: none !important;
    }}
    .layout.view-chat {{
      height: calc(100vh - 96px);
      height: calc(100dvh - 96px);
      min-height: 520px;
      grid-template-rows: minmax(0, 1fr);
    }}
    .layout.view-chat .chat {{
      grid-row: 1;
      min-height: 0;
    }}
    .layout.view-chat .map,
    .layout.view-chat .map-data,
    .layout.view-chat .summary,
    .layout.view-chat .nodes,
    .layout.view-chat .packets,
    .layout.view-chat .raw,
    .layout.view-chat .console,
    .layout.view-chat .splitter,
    .layout.view-chat .hsplitter {{
      display: none !important;
    }}

    .layout.view-network {{
      height: calc(100vh - 96px);
      height: calc(100dvh - 96px);
      min-height: 560px;
      grid-template-columns: minmax(350px, var(--split-left-pct)) var(--splitter-size) minmax(320px, 1fr);
      grid-template-rows: auto minmax(0, 1fr);
    }}
    .layout.view-network .summary {{
      display: block;
      grid-column: 1 / span 3;
      grid-row: 1;
    }}
    .layout.view-network .nodes {{
      grid-column: 1;
      grid-row: 2;
      min-height: 0;
    }}
    .layout.view-network .map {{
      grid-column: 3;
      grid-row: 2;
      min-height: 0;
    }}
    .layout.view-network .nodes .body {{
      min-height: 0;
      overflow: hidden;
    }}
    .layout.view-network .nodes-table-scroll {{
      flex: 0 0 var(--network-nodes-list-pct);
      min-height: 150px;
    }}
    .layout.view-network .network-node-splitter {{
      display: block;
    }}
    .layout.view-network .network-node-history-host {{
      flex: 1 1 auto;
      min-height: 200px;
      overflow: auto;
    }}
    .layout.view-network .network-node-history-host #map-data-node {{
      display: flex;
      flex-direction: column;
      min-height: 0;
      gap: 8px;
    }}
    .layout.view-network .network-node-history-host #tab-panel-signal {{
      display: flex;
      flex-direction: column;
      min-height: 0;
    }}
    .layout.view-network .network-node-history-host #tab-panel-signal,
    .layout.view-network .network-node-history-host #tab-panel-overview {{
      flex: 1 1 auto;
      min-height: 0;
    }}
    .layout.view-network .network-node-history-host #signal-chart-wrap {{
      height: auto;
      min-height: 160px;
      flex: 1 1 auto;
    }}
    .layout.view-network .map .body {{
      min-height: 0;
    }}
    .layout.view-network .map-frame {{
      min-height: 0;
    }}
    .layout.view-network .map-data,
    .layout.view-network .chat,
    .layout.view-network .packets,
    .layout.view-network .raw,
    .layout.view-network .console,
    .layout.view-network .hsplitter[data-target="top"],
    .layout.view-network .hsplitter[data-target="mid"],
    .layout.view-network .hsplitter[data-target="low"] {{
      display: none !important;
    }}
    .layout.view-network .splitter {{
      display: block;
      grid-row: 2;
    }}

    .layout.view-packets {{
      height: calc(100vh - 96px);
      height: calc(100dvh - 96px);
      min-height: 560px;
      grid-template-rows:
        auto
        minmax(240px, var(--split-top-px))
        var(--splitter-size)
        minmax(170px, 1fr);
    }}
    .layout.view-packets .packets {{
      grid-column: 1 / span 3;
      grid-row: 2;
    }}
    .layout.view-packets .console {{
      grid-column: 1 / span 3;
      grid-row: 4;
    }}
    .layout.view-packets .chat,
    .layout.view-packets .nodes,
    .layout.view-packets .map,
    .layout.view-packets .map-data,
    .layout.view-packets .raw,
    .layout.view-packets .splitter,
    .layout.view-packets .hsplitter[data-target="top"],
    .layout.view-packets .hsplitter[data-target="mid"] {{
      display: none !important;
    }}
    .layout.view-packets .hsplitter[data-target="low"] {{ grid-row: 3; }}

    .layout.view-data {{
      height: calc(100vh - 96px);
      height: calc(100dvh - 96px);
      min-height: 560px;
      grid-template-rows:
        auto
        minmax(240px, var(--split-top-px))
        var(--splitter-size)
        minmax(170px, 1fr);
    }}
    .layout.view-data .raw {{
      grid-column: 1 / span 3;
      grid-row: 2;
    }}
    .layout.view-data .console {{
      grid-column: 1 / span 3;
      grid-row: 4;
    }}
    .layout.view-data .chat,
    .layout.view-data .nodes,
    .layout.view-data .map,
    .layout.view-data .map-data,
    .layout.view-data .packets,
    .layout.view-data .splitter,
    .layout.view-data .hsplitter[data-target="top"],
    .layout.view-data .hsplitter[data-target="mid"] {{
      display: none !important;
    }}
    .layout.view-data .hsplitter[data-target="low"] {{ grid-row: 3; }}

    .layout.view-saved {{
      height: calc(100vh - 96px);
      height: calc(100dvh - 96px);
      min-height: 560px;
      grid-template-columns: minmax(350px, var(--split-left-pct)) var(--splitter-size) minmax(320px, 1fr);
      grid-template-rows: minmax(0, 1fr);
    }}
    .layout.view-saved .favorites {{
      display: flex;
      grid-column: 1;
      grid-row: 1;
      min-height: 0;
    }}
    .layout.view-saved .map {{
      display: flex;
      grid-column: 3;
      grid-row: 1;
      min-height: 0;
    }}
    .layout.view-saved .map .body {{
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .layout.view-saved .map-frame {{
      display: block;
      order: 2;
      flex: 0 0 clamp(170px, 28vh, 280px);
      min-height: 170px;
    }}
    .layout.view-saved .saved-node-details {{
      display: flex;
      order: 1;
      flex: 1 1 auto;
      min-height: 0;
    }}
    .layout.view-saved .summary,
    .layout.view-saved .map-data,
    .layout.view-saved .chat,
    .layout.view-saved .nodes,
    .layout.view-saved .packets,
    .layout.view-saved .raw,
    .layout.view-saved .console,
    .layout.view-saved .hsplitter[data-target="top"],
    .layout.view-saved .hsplitter[data-target="mid"],
    .layout.view-saved .hsplitter[data-target="low"] {{
      display: none !important;
    }}
    .layout.view-saved .splitter {{
      display: block;
      grid-row: 1;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 11px;
    }}
    th, td {{
      text-align: left;
      border-bottom: 1px solid #e7efe4;
      padding: 4px 5px;
      vertical-align: middle;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    th {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: #f4faf3;
      color: #204231;
      font-size: 10px;
      letter-spacing: 0.2px;
      text-transform: uppercase;
    }}
    th.sortable {{
      cursor: pointer;
      user-select: none;
    }}
    th.sortable::after {{
      content: " \2195";
      font-size: 9px;
      opacity: 0.35;
    }}
    th.sortable.sorted-asc::after {{
      content: " \25B2";
      opacity: 0.9;
    }}
    th.sortable.sorted-desc::after {{
      content: " \25BC";
      opacity: 0.9;
    }}
    #nodes-table tbody tr.node-selectable {{
      cursor: pointer;
    }}
    #nodes-table tbody tr.node-selectable:hover {{
      background: #edf8f1;
    }}
    #nodes-table tbody tr.selected-node {{
      background: #d8efe1;
    }}
    #nodes-table tbody tr.selected-node td {{
      background: #d8efe1;
      color: #123222;
    }}
    #nodes-table tbody tr.selected-node td:first-child {{
      box-shadow: inset 3px 0 0 #2f855a;
    }}
    .mono {{ font-family: "IBM Plex Mono", "Consolas", "Menlo", monospace; }}
    #nodes-table th:nth-child(1), #nodes-table td:nth-child(1) {{ width: 13%; }}
    #nodes-table th:nth-child(2), #nodes-table td:nth-child(2) {{ width: 12%; }}
    #nodes-table th:nth-child(3), #nodes-table td:nth-child(3) {{ width: 20%; }}
    #nodes-table th:nth-child(4), #nodes-table td:nth-child(4) {{ width: 14%; }}
    #nodes-table th:nth-child(5), #nodes-table td:nth-child(5) {{ width: 6%; }}
    #nodes-table th:nth-child(6), #nodes-table td:nth-child(6) {{ width: 6%; }}
    #nodes-table th:nth-child(7), #nodes-table td:nth-child(7) {{ width: 7%; }}
    #nodes-table th:nth-child(8), #nodes-table td:nth-child(8) {{ width: 9%; }}
    #nodes-table th:nth-child(9), #nodes-table td:nth-child(9) {{ width: 10%; }}
    #nodes-table th:nth-child(10), #nodes-table td:nth-child(10) {{ width: 3%; }}
    #nodes-table th:nth-child(10), #nodes-table td:nth-child(10) {{
      text-align: right;
    }}
    #nodes-table td:nth-child(10) {{
      padding-right: 4px;
      overflow: visible;
      text-overflow: clip;
    }}
    #nodes-table th:nth-child(10) {{
      color: #6a856f;
      font-size: 9px;
      letter-spacing: 0;
      text-transform: none;
    }}
    #nodes-table td:nth-child(3) {{
      overflow: visible;
      text-overflow: clip;
    }}
    .node-name-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
      gap: 6px;
      min-width: 0;
      max-width: 100%;
      width: 100%;
    }}
    .node-name-label {{
      flex: 1 1 auto;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
    }}
    .chat .body {{
      display: flex;
      flex-direction: column;
      flex: 1;
      min-height: 0;
      gap: 0;
      padding: 0;
      background: #f7fcf7;
      overflow: hidden;
    }}
    #chat-caption {{
      font-size: 10px;
      color: #4a6958;
      margin: 3px 0 0 0;
      line-height: 1.25;
    }}
    .chat-shell {{
      display: flex;
      flex-direction: column;
      flex: 1 1 auto;
      min-height: 0;
      padding: 7px 6px 6px 6px;
      overflow: hidden;
    }}
    .chat-member-pane {{
      grid-area: members;
      grid-column: 2;
      border: 1px solid #d6e5d2;
      border-radius: 7px;
      background: #f8fcf8;
      min-height: 0;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}
    .chat-member-list {{
      padding: 4px;
      overflow: auto;
      min-height: 0;
      display: flex;
      flex-direction: column;
      gap: 3px;
    }}
    .chat-member-item {{
      display: grid;
      grid-template-columns: 11px minmax(0, 1fr);
      gap: 6px;
      align-items: center;
      border: 1px solid #c7dac5;
      background: #ecf7ef;
      color: #204233;
      border-radius: 6px;
      padding: 3px 6px;
      font-size: 10px;
      line-height: 1.2;
      cursor: pointer;
    }}
    .chat-member-item:hover {{
      background: #e2f0e7;
    }}
    .chat-member-item.status-warn {{
      background: #fff9e7;
      color: #5d4a1b;
      border-color: #ecd89c;
    }}
    .chat-member-item.status-stale {{
      background: #fff0f0;
      color: #6a3333;
      border-color: #e6b5b5;
    }}
    .chat-member-item.status-unknown {{
      background: #f2f5f2;
      color: #607268;
      border-color: #d8e3d8;
    }}
    .chat-member-item.selected-node {{
      background: #d8efe1;
      border-color: #99c5aa;
      color: #16402c;
    }}
    .chat-member-status {{
      width: 10px;
      text-align: center;
      font-size: 10px;
      font-weight: 700;
      line-height: 1;
      color: #2aa85a;
    }}
    .chat-member-status.status-online {{
      color: #2aa85a;
    }}
    .chat-member-status.status-warn {{
      color: #d2a022;
    }}
    .chat-member-status.status-stale {{
      color: #d15757;
    }}
    .chat-member-status.status-unknown {{
      color: #99aaa0;
    }}
    .chat-member-main {{
      display: flex;
      flex-direction: column;
      min-width: 0;
      gap: 1px;
    }}
    .chat-member-name-row {{
      display: flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
      max-width: 100%;
      width: 100%;
    }}
    .chat-member-name-left {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      min-width: 0;
      flex: 1 1 auto;
      max-width: 100%;
    }}
    .favorite-toggle-btn {{
      border: 1px solid rgba(103, 132, 115, 0.35);
      background: transparent;
      color: #6b7f72;
      border-radius: 999px;
      min-width: 16px;
      height: 16px;
      padding: 0 3px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      flex: 0 0 auto;
      line-height: 1;
      font-size: 9px;
      opacity: 0.76;
      transition: color 120ms ease, border-color 120ms ease, background 120ms ease, opacity 120ms ease;
    }}
    .favorite-toggle-btn:hover {{
      background: rgba(72, 110, 87, 0.08);
      border-color: rgba(63, 103, 80, 0.55);
      color: #355d48;
      opacity: 1;
    }}
    .favorite-toggle-btn.active {{
      border-color: rgba(182, 153, 62, 0.82);
      background: rgba(255, 241, 178, 0.4);
      color: #6f5600;
      opacity: 0.95;
    }}
    .favorite-toggle-icon {{
      line-height: 1;
      transform: translateY(-0.5px);
    }}
    .node-favorite-btn {{
      min-width: 16px;
      height: 16px;
      font-size: 9px;
    }}
    .chat-favorite-btn {{
      min-width: 15px;
      height: 15px;
      font-size: 8px;
      padding: 0 2px;
    }}
    .favorites-card-star {{
      min-width: 18px;
      height: 18px;
      font-size: 9px;
      padding: 0 5px;
    }}
    .node-name-row .favorite-toggle-btn,
    .chat-member-name-row .favorite-toggle-btn {{
      margin-left: auto;
    }}
    .node-name-row .favorite-toggle-btn {{
      margin-left: 0;
      justify-self: end;
    }}
    .chat-member-name {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
      color: inherit;
    }}
    .chat-member-name.status-warn {{
      color: #6d541d;
    }}
    .chat-member-name.status-stale {{
      color: #7b3d3d;
    }}
    .chat-member-name.status-unknown {{
      color: #667a70;
      opacity: 0.8;
    }}
    .chat-member-id {{
      font-size: 9px;
      color: #6c8578;
      opacity: 0.46;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
    }}
    .chat-main-pane {{
      display: grid;
      grid-template-rows: minmax(0, 1fr) auto;
      row-gap: 6px;
      flex: 1 1 auto;
      min-height: 0;
      overflow: hidden;
    }}
    .chat-log-scroll {{
      grid-row: 1;
      flex: 1 1 auto;
      max-height: none;
      min-height: 0;
      display: flex;
      flex-direction: column;
      border: 0;
      border-radius: 0;
      background: transparent;
      padding: 0;
    }}
    .chat-feed {{
      display: flex;
      flex-direction: column;
      gap: 0;
      width: 100%;
      min-height: 0;
      margin-top: auto;
    }}
    .chat-feed-item:last-child {{
      border-bottom: 0;
    }}
    .chat-feed-item {{
      width: 100%;
      box-sizing: border-box;
      border: 0;
      border-radius: 0;
      border-bottom: 1px solid #d7e5d2;
      padding: 6px 7px;
      background: transparent;
      color: #204233;
    }}
    .chat-feed-item.chat-selectable {{
      cursor: pointer;
    }}
    .chat-feed-item.chat-selectable:hover {{
      background: #eef6f1;
    }}
    .chat-feed-item.selected-node {{
      background: #e7f2eb;
      box-shadow: inset 2px 0 0 #2f855a;
    }}
    .chat-feed-meta {{
      display: flex;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 6px;
      font-size: 10px;
      color: #5a7462;
      line-height: 1.2;
      margin-bottom: 3px;
    }}
    .chat-feed-arrow {{
      color: #6e8c78;
      opacity: 0.75;
    }}
    .chat-feed-time {{
      margin-left: auto;
      font-size: 10px;
      color: #6a8572;
      white-space: nowrap;
    }}
    .chat-feed-hops {{
      font-size: 10px;
      color: #3f6b52;
      background: #edf6ef;
      border: 1px solid #c9dece;
      border-radius: 999px;
      padding: 1px 7px;
      line-height: 1.3;
      white-space: nowrap;
    }}
    .chat-feed-actions {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      margin-left: 2px;
    }}
    .chat-reply-btn {{
      border: 1px solid #bfd6c3;
      background: #f4fbf6;
      color: #24533a;
      border-radius: 999px;
      padding: 1px 7px;
      font-size: 10px;
      line-height: 1.4;
      cursor: pointer;
      white-space: nowrap;
    }}
    .chat-reply-btn:hover {{
      background: #e6f2e9;
      border-color: #9dc3a7;
    }}
    .chat-react-btn {{
      border: 1px solid #bdd4c1;
      background: #f5fbf6;
      color: #26543a;
      border-radius: 999px;
      padding: 1px 7px;
      font-size: 11px;
      line-height: 1.4;
      cursor: pointer;
      white-space: nowrap;
    }}
    .chat-react-btn:hover {{
      background: #e8f4eb;
      border-color: #9ec2a8;
    }}
    .chat-retry-btn {{
      border: 1px solid #d5bb80;
      background: #fff8e7;
      color: #7a4e12;
      border-radius: 999px;
      padding: 1px 8px;
      font-size: 10px;
      line-height: 1.4;
      cursor: pointer;
      white-space: nowrap;
    }}
    .chat-retry-btn:hover {{
      background: #fff2d3;
      border-color: #be9c54;
    }}
    .chat-delivery-pill {{
      display: inline-flex;
      align-items: center;
      border: 1px solid #cfdccc;
      border-radius: 999px;
      padding: 1px 7px;
      font-size: 10px;
      line-height: 1.35;
      white-space: nowrap;
      margin-left: 2px;
    }}
    .chat-delivery-pill.state-pending {{
      background: #fff8e5;
      border-color: #e0c88f;
      color: #7a5a20;
    }}
    .chat-delivery-pill.state-sent {{
      background: #eff6ef;
      border-color: #c5d8c7;
      color: #3c6648;
    }}
    .chat-delivery-pill.state-acked {{
      background: #e7f5eb;
      border-color: #9ec8aa;
      color: #1f6138;
    }}
    .chat-delivery-pill.state-nak,
    .chat-delivery-pill.state-timeout,
    .chat-delivery-pill.state-error {{
      background: #fff0f0;
      border-color: #dfadad;
      color: #8a2c2c;
    }}
    .chat-feed-text {{
      font-size: 12px;
      color: #173827;
      line-height: 1.35;
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .chat-feed-text.chat-reply-trigger {{
      cursor: pointer;
    }}
    .chat-feed-text.chat-reply-trigger:hover {{
      color: #0f4d2f;
    }}
    .chat-reply-inline {{
      margin-bottom: 5px;
      border-left: 3px solid #a9cbb3;
      padding: 2px 0 2px 8px;
      color: #3f6050;
      font-size: 10px;
      line-height: 1.25;
      display: flex;
      flex-direction: column;
      gap: 1px;
    }}
    .chat-reply-inline .chat-reply-inline-label {{
      color: #2a513d;
      font-weight: 600;
    }}
    .chat-reply-inline .chat-reply-inline-text {{
      color: #587364;
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .chat-reply-inline.missing {{
      border-left-color: #d6d6d6;
      color: #6f7c76;
    }}
    .chat-reaction-row {{
      margin-top: 5px;
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      align-items: center;
    }}
    .chat-reaction-chip {{
      border: 1px solid #b9d2bf;
      background: #ecf7ef;
      color: #1f4e35;
      border-radius: 999px;
      padding: 1px 8px;
      font-size: 11px;
      line-height: 1.3;
      cursor: pointer;
      white-space: nowrap;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}
    .chat-reaction-chip:hover {{
      background: #dff0e4;
      border-color: #94bd9f;
    }}
    .chat-reaction-chip:focus-visible {{
      outline: 2px solid #8fbca0;
      outline-offset: 1px;
    }}
    .chat-reaction-emoji {{
      font-size: 12px;
      line-height: 1;
    }}
    .chat-reaction-count {{
      font-size: 10px;
      font-weight: 700;
      color: #355f48;
    }}
    .chat-reaction-popover {{
      position: fixed;
      z-index: 1300;
      min-width: 220px;
      max-width: 320px;
      border: 1px solid #bdd4c3;
      border-radius: 12px;
      background: #fbfefc;
      box-shadow: 0 10px 24px rgba(8, 35, 20, 0.18);
      color: #193926;
      padding: 8px;
    }}
    .chat-reaction-popover[hidden] {{
      display: none !important;
    }}
    .chat-reaction-popover-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      font-size: 12px;
      font-weight: 600;
      color: #1f4f35;
      margin-bottom: 6px;
      padding-bottom: 6px;
      border-bottom: 1px solid #deebe1;
    }}
    .chat-reaction-popover-emoji {{
      font-size: 15px;
      line-height: 1;
    }}
    .chat-reaction-popover-count {{
      color: #4c705b;
      font-size: 11px;
      font-weight: 600;
    }}
    .chat-reaction-popover-list {{
      display: flex;
      flex-direction: column;
      gap: 4px;
      max-height: 220px;
      overflow: auto;
      padding-right: 2px;
    }}
    .chat-reaction-popover-row {{
      display: flex;
      align-items: center;
      gap: 7px;
      font-size: 12px;
      line-height: 1.25;
      color: #20452f;
      padding: 2px 1px;
    }}
    .chat-reaction-popover-avatar {{
      width: 20px;
      height: 20px;
      border-radius: 999px;
      border: 1px solid #bfd7c7;
      background: #ecf7f0;
      color: #25523a;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 10px;
      font-weight: 700;
      line-height: 1;
      flex: 0 0 auto;
    }}
    .chat-reaction-popover-name {{
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .chat-reaction-popover-more {{
      margin-top: 3px;
      padding-top: 6px;
      border-top: 1px solid #deebe1;
      font-size: 11px;
      color: #597767;
    }}
    .chat-feed-empty {{
      border: 1px dashed #d2e2d4;
      border-radius: 8px;
      padding: 10px;
      font-size: 12px;
      color: #5d7566;
      background: #f8fcf8;
    }}
    .chat-compose-shell {{
      border: 1px solid #c8dacc;
      border-radius: 10px;
      background: #f3faf5;
      padding: 6px;
      display: flex;
      flex-direction: column;
      gap: 5px;
      min-height: 0;
    }}
    .chat-composer {{
      position: relative;
      display: flex;
      flex-direction: column;
      gap: 0;
      align-items: stretch;
      min-height: 0;
    }}
    .chat-composer-top {{
      display: none;
      align-items: center;
      gap: 6px;
      min-height: 0;
    }}
    .chat-composer-top.has-reply {{
      display: flex;
      margin-bottom: 5px;
    }}
    .chat-composer-input-row {{
      display: flex;
      align-items: stretch;
      gap: 6px;
      min-height: 0;
    }}
    .chat-reply-context {{
      flex: 1 1 auto;
      min-width: 0;
      border: 1px solid #c4d9c9;
      border-radius: 7px;
      background: #f3faf5;
      color: #234635;
      font-size: 11px;
      line-height: 1.25;
      padding: 4px 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .chat-reply-context[hidden] {{
      display: none !important;
    }}
    .chat-reply-label {{
      flex: 1 1 auto;
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .chat-reply-clear-btn {{
      border: 1px solid #bdd4c1;
      background: #ffffff;
      color: #2c5a42;
      border-radius: 999px;
      width: 20px;
      height: 20px;
      padding: 0;
      font-size: 13px;
      line-height: 1;
      cursor: pointer;
      flex: 0 0 auto;
    }}
    .chat-reply-clear-btn:hover {{
      background: #edf6f0;
    }}
    #chat-input {{
      flex: 1 1 auto;
      width: auto;
      min-width: 0;
    }}
    #chat-send-btn {{
      border: 1px solid #9cc9ad;
      background: #e3f4ea;
      color: #184a32;
      border-radius: 8px;
      height: 27px;
      padding: 0 11px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
    }}
    #chat-send-btn:hover {{
      background: #d7ecdf;
    }}
    #chat-send-btn:disabled {{
      opacity: 0.6;
      cursor: default;
    }}
    #chat-emoji-btn {{
      border: 1px solid #9cc9ad;
      background: #f1f9f4;
      color: #184a32;
      border-radius: 8px;
      height: 27px;
      padding: 0 9px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      line-height: 1;
      cursor: pointer;
      white-space: nowrap;
    }}
    #chat-emoji-btn:hover {{
      background: #e6f2ea;
    }}
    #chat-emoji-btn:disabled {{
      opacity: 0.6;
      cursor: default;
    }}
    .chat-emoji-panel {{
      position: absolute;
      right: 58px;
      bottom: calc(100% + 6px);
      width: min(320px, 92%);
      border: 1px solid #c9dbcc;
      border-radius: 8px;
      background: #fbfefb;
      box-shadow: 0 8px 20px rgba(16, 36, 24, 0.18);
      padding: 6px;
      z-index: 9;
    }}
    .chat-emoji-panel[hidden] {{
      display: none !important;
    }}
    .chat-emoji-grid {{
      display: grid;
      grid-template-columns: repeat(8, minmax(0, 1fr));
      gap: 4px;
    }}
    .chat-emoji-item {{
      border: 1px solid #d9e7da;
      border-radius: 6px;
      background: #ffffff;
      padding: 5px 4px;
      font-size: 16px;
      line-height: 1;
      cursor: pointer;
    }}
    .chat-emoji-item:hover {{
      background: #ecf5ef;
      border-color: #b4d0bd;
    }}
    .chat-send-status {{
      min-height: 0;
      font-size: 10px;
      color: #446551;
      line-height: 1.25;
    }}
    .chat-send-status:empty {{
      display: none;
    }}
    .chat-send-status.error {{
      color: #b43b3b;
      font-weight: 600;
    }}
    .chat-endpoint {{
      display: inline-flex;
      align-items: baseline;
      gap: 5px;
      max-width: 100%;
      min-width: 0;
    }}
    .chat-name-meta {{
      display: inline-flex;
      align-items: center;
      gap: 3px;
      flex-wrap: nowrap;
      min-width: 0;
    }}
    .chat-name-chip {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid #c9dece;
      border-radius: 999px;
      background: #edf6ef;
      color: #3f6b52;
      font-size: 9px;
      line-height: 1.25;
      padding: 1px 5px;
      white-space: nowrap;
    }}
    .chat-name-chip.offline {{
      border-color: #cfd7d2;
      background: #eff3f0;
      color: #65756c;
      opacity: 0.8;
    }}
    .chat-name-chip.gps {{
      font-size: 10px;
      line-height: 1;
      padding: 1px 4px;
    }}
    .chat-name {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 100%;
    }}
    .chat-name.status-warn {{
      color: #7a6322;
    }}
    .chat-name.status-stale {{
      color: #8a4545;
      opacity: 0.9;
    }}
    .chat-name.status-unknown {{
      color: #667a70;
      opacity: 0.72;
    }}
    .chat-id-bg {{
      font-size: 9px;
      color: #6c8578;
      opacity: 0.5;
      letter-spacing: 0.12px;
      white-space: nowrap;
    }}
    .chat-id-bg.status-warn {{
      color: #7f6b2d;
      opacity: 0.45;
    }}
    .chat-id-bg.status-stale {{
      color: #875151;
      opacity: 0.4;
    }}
    .chat-id-bg.status-unknown {{
      opacity: 0.36;
    }}
    .scroll {{
      max-height: 300px;
      overflow: auto;
    }}
    .chat-log-scroll.scroll {{
      max-height: none;
      height: 100%;
      overflow: auto;
    }}
    .scroll.wheel-scroll-active,
    #live-console.wheel-scroll-active,
    details pre.wheel-scroll-active {{
      outline: 2px solid #8ab79b;
      outline-offset: -2px;
    }}
    .pill {{
      display: inline-block;
      font-size: 10px;
      border-radius: 999px;
      padding: 2px 7px;
      border: 1px solid #c2d8c7;
      background: #f0f8f2;
      margin-left: 6px;
      color: #1e5e40;
    }}
    .pill.selection-pill {{
      border-color: #a8d2b6;
      background: #e7f6ec;
      color: #194c33;
    }}
    .selection-btn {{
      margin-left: 6px;
      font-size: 10px;
      line-height: 1.2;
      border: 1px solid #c2d8c7;
      color: #194c33;
      background: #f0f8f2;
      border-radius: 999px;
      padding: 3px 8px;
      cursor: pointer;
    }}
    .selection-btn:hover {{
      background: #e1f2e7;
    }}
    .selection-btn:disabled {{
      opacity: 0.55;
      cursor: default;
    }}
    .disk-meter {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-left: auto;
      padding: 2px 7px;
      border-radius: 999px;
      border: 1px solid rgba(226, 248, 233, 0.35);
      background: rgba(8, 30, 18, 0.2);
    }}
    .disk-label {{
      font-size: 10px;
      color: #e7fff0;
      white-space: nowrap;
    }}
    .disk-track {{
      width: 118px;
      height: 8px;
      border-radius: 999px;
      overflow: hidden;
      background: rgba(231, 255, 240, 0.28);
    }}
    .disk-fill {{
      width: 0%;
      height: 100%;
      border-radius: 999px;
      background: #66dc8a;
      transition: width 220ms ease, background-color 220ms ease;
    }}
    .disk-fill.warn {{
      background: #f4c652;
    }}
    .disk-fill.danger {{
      background: #ff7676;
    }}
    .topbar .sub .revision-text {{
      color: #e7fff0;
      font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
      letter-spacing: 0.1px;
    }}
    .warn {{ color: var(--danger); font-weight: 600; }}
    .console .body {{
      padding: 8px 10px;
    }}
    .console-controls {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
      font-size: 11px;
      color: #294735;
    }}
    .console-controls button {{
      border: 1px solid #c2d8c7;
      background: #f0f8f2;
      color: #1e5e40;
      border-radius: 6px;
      font-size: 11px;
      padding: 4px 8px;
      cursor: pointer;
    }}
    .console-controls button:hover {{
      background: #e1f2e7;
    }}
    #live-console {{
      margin: 0;
      background: #0e1f16;
      color: #cbffde;
      border-radius: 6px;
      padding: 8px;
      min-height: 180px;
      max-height: 280px;
      overflow: auto;
      font-size: 10px;
      line-height: 1.3;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    details {{
      border: 1px solid #d7e5d2;
      border-radius: 6px;
      padding: 6px 8px;
      margin-bottom: 6px;
      background: #fcfffc;
    }}
    summary {{ cursor: pointer; font-weight: 600; }}
    pre {{
      margin: 10px 0 0 0;
      background: #0e1f16;
      color: #cbffde;
      border-radius: 6px;
      padding: 8px;
      max-height: 200px;
      overflow: auto;
      font-size: 10px;
      line-height: 1.35;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    [data-theme="dark"] {{
      --bg: #0f1512;
      --ink: #e4f1e8;
      --panel: #16201b;
      --line: #32453b;
      --muted: #8ea99b;
      --shadow: 0 12px 28px rgba(0, 0, 0, 0.42);
      color-scheme: dark;
    }}
    [data-theme="dark"] body {{
      background:
        radial-gradient(circle at 20% -10%, #1b2922 0, transparent 45%),
        radial-gradient(circle at 80% 0%, #1a2b22 0, transparent 40%),
        var(--bg);
      color: var(--ink);
    }}
    [data-theme="dark"] .topbar {{
      background: linear-gradient(100deg, #101c16, #1a2f25);
      color: #e6f7ed;
    }}
    [data-theme="dark"] .topbar .sub .revision-text {{
      color: #dbf7e8;
    }}
    [data-theme="dark"] .theme-btn {{
      border-color: rgba(168, 205, 184, 0.45);
      background: rgba(166, 215, 190, 0.18);
      color: #e5f8ec;
    }}
    [data-theme="dark"] .theme-btn:hover {{
      background: rgba(166, 215, 190, 0.28);
    }}
    [data-theme="dark"] .pill,
    [data-theme="dark"] .selection-btn {{
      background: #22342a;
      border-color: #355041;
      color: #d6e8dd;
    }}
    [data-theme="dark"] .selection-btn:disabled {{
      opacity: 0.65;
    }}
    [data-theme="dark"] .disk-meter {{
      background: rgba(12, 21, 17, 0.45);
      border-color: #2f483b;
      color: #d0e5d8;
    }}
    [data-theme="dark"] .disk-track {{
      background: rgba(185, 231, 207, 0.18);
    }}
    [data-theme="dark"] .teams-rail,
    [data-theme="dark"] .chat-left-panel,
    [data-theme="dark"] .card {{
      background: #17231c;
      border-color: #33483c;
      color: #dbece3;
    }}
    [data-theme="dark"] .teams-rail-title,
    [data-theme="dark"] .chat-left-title,
    [data-theme="dark"] .chat-left-label,
    [data-theme="dark"] .chat-left-sub,
    [data-theme="dark"] .card h2,
    [data-theme="dark"] .metric .label {{
      color: #9fbead;
    }}
    [data-theme="dark"] .workspace-shell,
    [data-theme="dark"] .workspace-main {{
      color: #dbece3;
    }}
    [data-theme="dark"] .rail-btn,
    [data-theme="dark"] .chat-channel-item,
    [data-theme="dark"] .chat-member-item,
    [data-theme="dark"] .metric {{
      background: #213229;
      border-color: #3a5346;
      color: #d8ebe0;
    }}
    [data-theme="dark"] .rail-btn:hover,
    [data-theme="dark"] .chat-channel-item:hover,
    [data-theme="dark"] .chat-member-item:hover,
    [data-theme="dark"] .metric:hover {{
      background: #284034;
    }}
    [data-theme="dark"] .rail-btn.active {{
      background: #2f855a;
      border-color: #3f9868;
      color: #ebfff3;
    }}
    [data-theme="dark"] .chat-left-head,
    [data-theme="dark"] .chat-left-section {{
      background: #1b2b22;
      border-color: #33483c;
    }}
    [data-theme="dark"] .card.chat .chat-card-head {{
      background: #1b2b22;
      border-color: #33483c;
    }}
    [data-theme="dark"] .card.chat .chat-shell {{
      background: #1b2b22;
    }}
    [data-theme="dark"] .chat-feed-item {{
      background: #1a2a21;
      border-color: #31473b;
      color: #d9ece1;
    }}
    [data-theme="dark"] .chat-feed-item.chat-selectable:hover {{
      background: #24392f;
      border-color: #436553;
    }}
    [data-theme="dark"] .chat-feed-item.selected-node {{
      background: #2b4638;
      border-color: #5a8a72;
    }}
    [data-theme="dark"] .chat-feed-meta,
    [data-theme="dark"] .chat-feed-time,
    [data-theme="dark"] .chat-feed-arrow,
    [data-theme="dark"] .chat-reply-inline,
    [data-theme="dark"] .chat-reply-inline .chat-reply-inline-text {{
      color: #98b7a7;
    }}
    [data-theme="dark"] .chat-reply-inline .chat-reply-inline-label,
    [data-theme="dark"] .chat-feed-text,
    [data-theme="dark"] .chat-endpoint .chat-name {{
      color: #deeee4;
    }}
    [data-theme="dark"] .chat-endpoint .chat-id-bg,
    [data-theme="dark"] .chat-feed-hops {{
      background: #24382f;
      border-color: #416253;
      color: #c9e2d4;
    }}
    [data-theme="dark"] .chat-reaction-chip,
    [data-theme="dark"] .chat-reply-btn,
    [data-theme="dark"] .chat-react-btn,
    [data-theme="dark"] .chat-retry-btn {{
      background: #263a30;
      border-color: #426452;
      color: #d5e9de;
    }}
    [data-theme="dark"] .chat-reaction-chip:hover,
    [data-theme="dark"] .chat-reply-btn:hover,
    [data-theme="dark"] .chat-react-btn:hover,
    [data-theme="dark"] .chat-retry-btn:hover {{
      background: #30493c;
      border-color: #547d66;
    }}
    [data-theme="dark"] .chat-delivery-pill.state-pending {{
      background: #4a3b1f;
      border-color: #8c7240;
      color: #f4dd9f;
    }}
    [data-theme="dark"] .chat-delivery-pill.state-acked {{
      background: #1e3d2d;
      border-color: #4c8b6a;
      color: #bde9d0;
    }}
    [data-theme="dark"] .chat-delivery-pill.state-nak,
    [data-theme="dark"] .chat-delivery-pill.state-timeout,
    [data-theme="dark"] .chat-delivery-pill.state-error {{
      background: #4a2525;
      border-color: #8f4b4b;
      color: #ffbebe;
    }}
    [data-theme="dark"] .chat-reaction-popover {{
      background: #1a2921;
      border-color: #385546;
      color: #d7ebe0;
      box-shadow: 0 12px 28px rgba(0, 0, 0, 0.46);
    }}
    [data-theme="dark"] .chat-reaction-popover-head,
    [data-theme="dark"] .chat-reaction-popover-more {{
      border-color: #315043;
    }}
    [data-theme="dark"] .chat-reaction-popover-avatar {{
      background: #243b30;
      border-color: #446a57;
      color: #d3eadf;
    }}
    [data-theme="dark"] .chat-composer,
    [data-theme="dark"] .chat-compose-shell,
    [data-theme="dark"] .chat-left-bottom-bar,
    [data-theme="dark"] .chat-reply-context,
    [data-theme="dark"] #chat-send-btn,
    [data-theme="dark"] #chat-emoji-btn,
    [data-theme="dark"] .chat-emoji-panel,
    [data-theme="dark"] .chat-emoji-item {{
      background: #22352b;
      border-color: #3b5949;
      color: #deeee5;
    }}
    [data-theme="dark"] #chat-send-btn:hover,
    [data-theme="dark"] #chat-emoji-btn:hover,
    [data-theme="dark"] .chat-emoji-item:hover {{
      background: #2f4a3c;
      border-color: #5b866f;
    }}
    [data-theme="dark"] table,
    [data-theme="dark"] th,
    [data-theme="dark"] td,
    [data-theme="dark"] details {{
      border-color: #355041;
      color: #d8eae0;
    }}
    [data-theme="dark"] th {{
      background: #22362b;
    }}
    [data-theme="dark"] td {{
      background: #18261f;
    }}
    [data-theme="dark"] tr:nth-child(even) td {{
      background: #1c2d24;
    }}
    [data-theme="dark"] .console-controls {{
      color: #a8c6b6;
    }}
    [data-theme="dark"] .console-controls button {{
      background: #22352b;
      border-color: #3e5e4d;
      color: #d9ece2;
    }}
    [data-theme="dark"] .console-controls button:hover {{
      background: #2b4337;
    }}
    [data-theme="dark"] #live-console,
    [data-theme="dark"] pre {{
      background: #07120d;
      color: #bff0d5;
    }}
    [data-theme="dark"] .leaflet-container {{
      background: #101814;
    }}
    [data-theme="dark"] .leaflet-tile {{
      filter: brightness(0.62) invert(0.9) hue-rotate(180deg) saturate(0.45);
    }}
    [data-theme="dark"] a {{
      color: #8fc9ff;
    }}
    /* High-contrast blackout theme pass */
    [data-theme="dark"] {{
      --bg: #000000;
      --ink: #b9ffcf;
      --panel: #040704;
      --line: #1f6a41;
      --muted: #95efb8;
      --accent: #33ff8f;
      --accent-2: #25c979;
      --shadow: 0 0 0 1px rgba(41, 155, 98, 0.38), 0 16px 36px rgba(0, 0, 0, 0.62);
    }}
    [data-theme="dark"] body {{
      background: #000000 !important;
      color: var(--ink);
    }}
    [data-theme="dark"] .topbar {{
      background: #000000 !important;
      border-bottom: 1px solid #1f6a41;
      box-shadow: none;
    }}
    [data-theme="dark"] .topbar h1,
    [data-theme="dark"] .topbar .sub,
    [data-theme="dark"] .topbar .sub .sub-text,
    [data-theme="dark"] .topbar .sub .revision-text {{
      color: #c8ffd9;
    }}
    [data-theme="dark"] .theme-btn,
    [data-theme="dark"] .pill,
    [data-theme="dark"] .selection-btn {{
      background: #07120b;
      border-color: #2d8f5d;
      color: #c4ffd8;
    }}
    [data-theme="dark"] .theme-btn:hover,
    [data-theme="dark"] .selection-btn:hover {{
      background: #0b1f14;
      border-color: #39af72;
    }}
    [data-theme="dark"] .disk-meter {{
      background: #030a06;
      border-color: #246f47;
      color: #bfffd4;
    }}
    [data-theme="dark"] .disk-track {{
      background: rgba(121, 255, 182, 0.16);
    }}
    [data-theme="dark"] .teams-rail,
    [data-theme="dark"] .chat-left-panel,
    [data-theme="dark"] .card,
    [data-theme="dark"] .rail-btn,
    [data-theme="dark"] .chat-channel-item,
    [data-theme="dark"] .chat-member-item,
    [data-theme="dark"] .metric,
    [data-theme="dark"] .chat-feed-item,
    [data-theme="dark"] .chat-composer,
    [data-theme="dark"] .chat-compose-shell,
    [data-theme="dark"] .chat-left-bottom-bar,
    [data-theme="dark"] .chat-reply-context,
    [data-theme="dark"] .chat-emoji-panel,
    [data-theme="dark"] .chat-emoji-item,
    [data-theme="dark"] details {{
      background: #050905;
      border-color: #246f47;
      color: #c1ffd6;
    }}
    [data-theme="dark"] .chat-left-head,
    [data-theme="dark"] .chat-left-section,
    [data-theme="dark"] th,
    [data-theme="dark"] td,
    [data-theme="dark"] tr:nth-child(even) td {{
      background: #070d07;
      border-color: #236744;
      color: #c1ffd5;
    }}
    [data-theme="dark"] .card.chat .chat-card-head {{
      background: #070d07;
      border-color: #236744;
    }}
    [data-theme="dark"] .card.chat .chat-shell {{
      background: #070d07;
    }}
    [data-theme="dark"] .rail-btn:hover,
    [data-theme="dark"] .chat-channel-item:hover,
    [data-theme="dark"] .chat-member-item:hover,
    [data-theme="dark"] .metric:hover,
    [data-theme="dark"] .chat-feed-item.chat-selectable:hover,
    [data-theme="dark"] .chat-reaction-chip:hover,
    [data-theme="dark"] .chat-reply-btn:hover,
    [data-theme="dark"] .chat-react-btn:hover,
    [data-theme="dark"] .chat-retry-btn:hover,
    [data-theme="dark"] #chat-send-btn:hover,
    [data-theme="dark"] #chat-emoji-btn:hover,
    [data-theme="dark"] .chat-emoji-item:hover {{
      background: #0d1d13;
      border-color: #38af72;
    }}
    [data-theme="dark"] .rail-btn.active {{
      background: #12844e;
      border-color: #24b469;
      color: #ecfff4;
    }}
    [data-theme="dark"] .chat-feed-item.selected-node {{
      background: #0f2518;
      border-color: #38af72;
    }}
    [data-theme="dark"] .teams-rail-title,
    [data-theme="dark"] .chat-left-title,
    [data-theme="dark"] .chat-left-label,
    [data-theme="dark"] .chat-left-sub,
    [data-theme="dark"] .card h2,
    [data-theme="dark"] .metric .label,
    [data-theme="dark"] .chat-feed-meta,
    [data-theme="dark"] .chat-feed-time,
    [data-theme="dark"] .chat-feed-arrow,
    [data-theme="dark"] .chat-reply-inline,
    [data-theme="dark"] .chat-reply-inline .chat-reply-inline-text,
    [data-theme="dark"] .chat-reaction-count,
    [data-theme="dark"] .chat-member-id,
    [data-theme="dark"] .chat-channel-meta,
    [data-theme="dark"] .chat-send-status,
    [data-theme="dark"] .console-controls {{
      color: #96efb9;
    }}
    [data-theme="dark"] .chat-feed-text,
    [data-theme="dark"] .chat-endpoint .chat-name,
    [data-theme="dark"] .chat-reply-inline .chat-reply-inline-label,
    [data-theme="dark"] .chat-member-name,
    [data-theme="dark"] .chat-channel-name {{
      color: #c6ffdb;
    }}
    [data-theme="dark"] .chat-endpoint .chat-id-bg,
    [data-theme="dark"] .chat-feed-hops,
    [data-theme="dark"] .chat-reaction-chip,
    [data-theme="dark"] .chat-reply-btn,
    [data-theme="dark"] .chat-react-btn,
    [data-theme="dark"] .chat-retry-btn,
    [data-theme="dark"] #chat-send-btn,
    [data-theme="dark"] #chat-emoji-btn,
    [data-theme="dark"] .list-search-input,
    [data-theme="dark"] #chat-input {{
      background: #07140d;
      border-color: #2b8a59;
      color: #c6ffdb;
    }}
    [data-theme="dark"] .list-search-input::placeholder,
    [data-theme="dark"] #chat-input::placeholder {{
      color: #90d9ac;
    }}
    [data-theme="dark"] .chat-reaction-popover {{
      background: #060d08;
      border-color: #2d8f5d;
      color: #c6ffda;
      box-shadow: 0 0 0 1px rgba(57, 175, 114, 0.34), 0 18px 34px rgba(0, 0, 0, 0.64);
    }}
    [data-theme="dark"] .chat-reaction-popover-head,
    [data-theme="dark"] .chat-reaction-popover-more {{
      border-color: #246f47;
    }}
    [data-theme="dark"] .chat-reaction-popover-avatar {{
      background: #0b2115;
      border-color: #2d8f5d;
      color: #b7ffd0;
    }}
    [data-theme="dark"] .chat-delivery-pill.state-pending {{
      background: #342f0a;
      border-color: #8f7a17;
      color: #ffe59b;
    }}
    [data-theme="dark"] .chat-delivery-pill.state-acked {{
      background: #0b2b19;
      border-color: #34a56a;
      color: #c2ffd8;
    }}
    [data-theme="dark"] .chat-delivery-pill.state-nak,
    [data-theme="dark"] .chat-delivery-pill.state-timeout,
    [data-theme="dark"] .chat-delivery-pill.state-error {{
      background: #3d1515;
      border-color: #944343;
      color: #ffbcbc;
    }}
    [data-theme="dark"] #live-console,
    [data-theme="dark"] pre {{
      background: #010503;
      color: #bfffd4;
    }}
    [data-theme="dark"] .console-controls button {{
      background: #07140d;
      border-color: #2d8f5d;
      color: #c6ffda;
    }}
    [data-theme="dark"] .console-controls button:hover {{
      background: #0d1d13;
      border-color: #39af72;
    }}
    [data-theme="dark"] #chat-caption,
    [data-theme="dark"] #updated-at,
    [data-theme="dark"] #local-state-error {{
      color: #9df4be !important;
    }}
    [data-theme="dark"] .signal-legend .legend-chip {{
      color: #9df4be !important;
    }}
    [data-theme="dark"] .leaflet-container {{
      background: #010503;
    }}
    [data-theme="dark"] .leaflet-tile {{
      filter: brightness(0.45) invert(0.92) hue-rotate(165deg) saturate(0.75) contrast(1.18);
    }}
    [data-theme="dark"] a {{
      color: #86ffd2;
    }}
    [data-theme="dark"] body {{
      background: linear-gradient(180deg, #0a1016 0%, #0d1117 42%, #0f141b 100%);
      color: var(--ui-text);
      text-shadow: none;
    }}
    [data-theme="dark"] .topbar {{
      background: linear-gradient(180deg, #121a25 0%, #0f1721 100%) !important;
      border-bottom: 1px solid var(--ui-border);
      box-shadow: var(--ui-shadow);
    }}
    [data-theme="dark"] .topbar h1,
    [data-theme="dark"] .topbar .sub {{
      color: var(--ui-text);
    }}
    [data-theme="dark"] .topbar .sub .sub-text,
    [data-theme="dark"] .topbar .sub .revision-text,
    [data-theme="dark"] #chat-caption,
    [data-theme="dark"] #updated-at,
    [data-theme="dark"] #local-state-error,
    [data-theme="dark"] .signal-legend .legend-chip {{
      color: var(--ui-text-soft) !important;
    }}
    [data-theme="dark"] .teams-rail,
    [data-theme="dark"] .chat-left-panel,
    [data-theme="dark"] .card,
    [data-theme="dark"] details,
    [data-theme="dark"] #live-console,
    [data-theme="dark"] pre {{
      background: var(--ui-panel);
      border-color: var(--ui-border) !important;
      color: var(--ui-text);
      box-shadow: none;
    }}
    [data-theme="dark"] th {{
      background: #1d2733;
      color: #dce8f5;
      border-color: var(--ui-border) !important;
    }}
    [data-theme="dark"] td {{
      background: var(--ui-panel);
      border-color: var(--ui-border) !important;
      color: var(--ui-text);
    }}
    [data-theme="dark"] tr:nth-child(even) td {{
      background: #18202a;
    }}
    [data-theme="dark"] .pill,
    [data-theme="dark"] .selection-btn,
    [data-theme="dark"] .theme-btn,
    [data-theme="dark"] .disk-meter,
    [data-theme="dark"] .rail-btn,
    [data-theme="dark"] .chat-channel-item,
    [data-theme="dark"] .chat-member-item,
    [data-theme="dark"] .metric,
    [data-theme="dark"] .chat-feed-item,
    [data-theme="dark"] .chat-endpoint .chat-id-bg,
    [data-theme="dark"] .chat-feed-hops,
    [data-theme="dark"] .chat-reaction-chip,
    [data-theme="dark"] .chat-reply-btn,
    [data-theme="dark"] .chat-react-btn,
    [data-theme="dark"] .chat-retry-btn,
    [data-theme="dark"] .chat-reaction-popover,
    [data-theme="dark"] .chat-reaction-popover-head,
    [data-theme="dark"] .chat-reaction-popover-more,
    [data-theme="dark"] .chat-reaction-popover-avatar,
    [data-theme="dark"] .chat-composer,
    [data-theme="dark"] .chat-reply-context,
    [data-theme="dark"] #chat-send-btn,
    [data-theme="dark"] #chat-emoji-btn,
    [data-theme="dark"] .chat-emoji-panel,
    [data-theme="dark"] .chat-emoji-item,
    [data-theme="dark"] .console-controls button {{
      background: var(--ui-panel-alt);
      border-color: var(--ui-border) !important;
      color: var(--ui-text);
      box-shadow: none;
    }}
    [data-theme="dark"] .history-caption,
    [data-theme="dark"] .teams-rail-title,
    [data-theme="dark"] .chat-left-title,
    [data-theme="dark"] .chat-left-label,
    [data-theme="dark"] .chat-left-sub,
    [data-theme="dark"] .card h2,
    [data-theme="dark"] .metric .label,
    [data-theme="dark"] .chat-feed-meta,
    [data-theme="dark"] .chat-feed-time,
    [data-theme="dark"] .chat-feed-arrow,
    [data-theme="dark"] .chat-reply-inline,
    [data-theme="dark"] .chat-reply-inline .chat-reply-inline-text,
    [data-theme="dark"] .chat-reaction-count,
    [data-theme="dark"] .chat-member-id,
    [data-theme="dark"] .chat-channel-meta,
    [data-theme="dark"] .chat-send-status,
    [data-theme="dark"] .overview-item .k,
    [data-theme="dark"] .console-controls {{
      color: var(--ui-text-soft) !important;
    }}
    [data-theme="dark"] .chat-feed-text,
    [data-theme="dark"] .chat-endpoint .chat-name,
    [data-theme="dark"] .chat-reply-inline .chat-reply-inline-label,
    [data-theme="dark"] .chat-member-name,
    [data-theme="dark"] .chat-channel-name,
    [data-theme="dark"] .overview-item .v {{
      color: var(--ui-text) !important;
    }}
    [data-theme="dark"] .chat-name-chip {{
      background: #07140d;
      border-color: #2b8a59;
      color: #c6ffdb;
    }}
    [data-theme="dark"] .card.chat {{
      background: var(--ui-panel);
      border-color: var(--ui-border);
    }}
    [data-theme="dark"] .card.chat .chat-card-head {{
      background: #070d07;
      border-bottom: 1px solid #236744;
      border-color: #236744;
    }}
    [data-theme="dark"] .card.chat .body {{
      background: #070d07;
    }}
    [data-theme="dark"] .card.chat .chat-shell {{
      background: #070d07;
    }}
    [data-theme="dark"] .card.chat .chat-log-scroll {{
      background: transparent;
      border: 0;
    }}
    [data-theme="dark"] .card.chat .chat-feed-item {{
      background: transparent;
      border: 0;
      border-bottom: 1px solid #2f3b4b;
      border-radius: 0;
      color: var(--ui-text);
    }}
    [data-theme="dark"] .card.chat .chat-feed-item:last-child {{
      border-bottom: 0;
    }}
    [data-theme="dark"] .card.chat .chat-feed-item.chat-selectable:hover {{
      background: #1f2d3a;
    }}
    [data-theme="dark"] .card.chat .chat-compose-shell {{
      background: #101a24;
      border-color: #2f3b4b;
    }}
    [data-theme="dark"] .card.chat .chat-feed-hops,
    [data-theme="dark"] .card.chat .chat-endpoint .chat-id-bg,
    [data-theme="dark"] .card.chat .chat-reaction-chip,
    [data-theme="dark"] .card.chat .chat-reply-btn,
    [data-theme="dark"] .card.chat .chat-react-btn,
    [data-theme="dark"] .card.chat .chat-retry-btn {{
      background: #16273a;
      border-color: #35556d;
      color: #dbeeff;
    }}
    [data-theme="dark"] .chat-compose-shell,
    [data-theme="dark"] .chat-left-bottom-bar {{
      background: var(--ui-panel-alt);
      border-color: var(--ui-border);
    }}
    [data-theme="dark"] .chat-name-chip.offline {{
      background: #212933;
      border-color: #41505f;
      color: #9aabbb;
      opacity: 0.82;
    }}
    [data-theme="dark"] .chat-channel-unread-from {{
      color: #a8bed2;
    }}
    [data-theme="dark"] .chat-channel-unread {{
      color: #d8ffdf;
      background: #1f4f35;
      border-color: #3fb950;
    }}
    [data-theme="dark"] .history-tabs {{
      border-bottom-color: var(--ui-border);
    }}
    [data-theme="dark"] .history-tab-btn {{
      background: var(--ui-panel-alt);
      border-color: var(--ui-border);
      color: var(--ui-text-soft);
    }}
    [data-theme="dark"] .history-tab-btn.active {{
      background: #223447;
      border-color: #3d5973;
      color: #ebf3ff;
    }}
    [data-theme="dark"] #signal-chart-wrap,
    [data-theme="dark"] #online-activity-chart-wrap {{
      background: linear-gradient(180deg, #141c27 0%, #111823 100%);
      border-color: var(--ui-border);
    }}
    [data-theme="dark"] .signal-empty {{
      color: var(--ui-text-soft);
      background: rgba(13, 17, 23, 0.9);
    }}
    [data-theme="dark"] .signal-timeline-track {{
      background: #344353;
    }}
    [data-theme="dark"] .signal-timeline-tick {{
      background: #70879f;
    }}
    [data-theme="dark"] .signal-timeline-label,
    [data-theme="dark"] .signal-timeline-empty {{
      color: #a4b7c9;
    }}
    [data-theme="dark"] .saved-node-details {{
      border-color: var(--ui-border);
      background: var(--ui-panel-alt);
    }}
    [data-theme="dark"] .saved-node-details-empty {{
      border-color: var(--ui-border);
      background: #121b24;
      color: #a9bfd3;
    }}
    [data-theme="dark"] .saved-node-details-head {{
      border-bottom-color: var(--ui-border);
    }}
    [data-theme="dark"] .saved-node-title {{
      color: #e6eef8;
    }}
    [data-theme="dark"] .saved-node-subtitle,
    [data-theme="dark"] .saved-node-section-title,
    [data-theme="dark"] .saved-node-stat-k,
    [data-theme="dark"] .saved-node-note {{
      color: #9db3c8;
    }}
    [data-theme="dark"] .saved-node-status {{
      border-color: rgba(124, 161, 190, 0.36);
      background: rgba(121, 192, 255, 0.08);
      color: #cfe4f8;
    }}
    [data-theme="dark"] .saved-node-status.status-online {{
      border-color: rgba(63, 185, 80, 0.7);
      background: rgba(47, 133, 90, 0.3);
      color: #cbf7d8;
    }}
    [data-theme="dark"] .saved-node-status.status-warn {{
      border-color: rgba(234, 179, 8, 0.72);
      background: rgba(161, 98, 7, 0.3);
      color: #ffe9b0;
    }}
    [data-theme="dark"] .saved-node-status.status-stale {{
      border-color: rgba(248, 113, 113, 0.74);
      background: rgba(153, 27, 27, 0.34);
      color: #ffd6d6;
    }}
    [data-theme="dark"] .saved-node-section {{
      border-color: var(--ui-border);
      background: #111823;
    }}
    [data-theme="dark"] .saved-node-stat {{
      border-color: var(--ui-border);
      background: #101722;
    }}
    [data-theme="dark"] .saved-node-stat-v {{
      color: #e6eef8;
    }}
    [data-theme="dark"] .overview-item {{
      border-color: var(--ui-border);
      background: var(--ui-panel-alt);
    }}
    [data-theme="dark"] .network-node-history-host {{
      border-top: none;
    }}
    [data-theme="dark"] .network-node-splitter {{
      border-color: var(--ui-border);
      background: linear-gradient(90deg, #1a2430, #16202c);
    }}
    [data-theme="dark"] .network-node-splitter::before {{
      background: #44566a;
    }}
    [data-theme="dark"] .network-node-splitter:hover::before,
    [data-theme="dark"] .network-node-splitter.active::before {{
      background: #79c0ff;
    }}
    [data-theme="dark"] .network-node-history-host.empty::before {{
      border-color: var(--ui-border);
      background: var(--ui-panel-alt);
      color: var(--ui-text-soft);
    }}
    [data-theme="dark"] .metric-action.active {{
      background: #223447;
      border-color: #4f6d8a;
      box-shadow: inset 0 0 0 1px rgba(121, 192, 255, 0.2);
    }}
    [data-theme="dark"] .activity-legend-nodes {{
      color: #a5d2ff !important;
    }}
    [data-theme="dark"] .theme-btn:hover,
    [data-theme="dark"] .selection-btn:hover,
    [data-theme="dark"] .rail-btn:hover,
    [data-theme="dark"] .chat-channel-item:hover,
    [data-theme="dark"] .chat-member-item:hover,
    [data-theme="dark"] .metric:hover,
    [data-theme="dark"] .chat-feed-item.chat-selectable:hover,
    [data-theme="dark"] .chat-reaction-chip:hover,
    [data-theme="dark"] .chat-reply-btn:hover,
    [data-theme="dark"] .chat-react-btn:hover,
    [data-theme="dark"] .chat-retry-btn:hover,
    [data-theme="dark"] #chat-send-btn:hover,
    [data-theme="dark"] #chat-emoji-btn:hover,
    [data-theme="dark"] .chat-emoji-item:hover,
    [data-theme="dark"] .console-controls button:hover {{
      background: #253140;
      border-color: #43556b !important;
      color: var(--ui-text) !important;
      transform: none;
      box-shadow: none;
    }}
    [data-theme="dark"] .rail-btn.active {{
      background: #1e3342;
      border-color: #3f5b73 !important;
      color: #eef6ff !important;
      box-shadow: inset 0 0 0 1px rgba(121, 192, 255, 0.15);
    }}
    [data-theme="dark"] .rail-btn.has-unread {{
      border-color: #3fb950 !important;
      box-shadow: inset 0 0 0 1px rgba(63, 185, 80, 0.3);
    }}
    [data-theme="dark"] .chat-feed-item.selected-node {{
      background: #1b313f;
      box-shadow: inset 2px 0 0 var(--ui-accent);
    }}
    [data-theme="dark"] .chat-member-item.selected-node {{
      background: #1f3342 !important;
      border-color: #4a6b87 !important;
      color: #eef6ff !important;
      box-shadow: inset 2px 0 0 #79c0ff;
    }}
    [data-theme="dark"] .chat-member-item.selected-node .chat-member-id {{
      color: #bed3e8 !important;
      opacity: 0.9;
    }}
    [data-theme="dark"] #nodes-table tbody tr.selected-node td {{
      background: #243646 !important;
      border-color: #4a617a !important;
      color: #ecf5ff !important;
    }}
    [data-theme="dark"] #nodes-table tbody tr.selected-node td:first-child {{
      box-shadow: inset 3px 0 0 #79c0ff;
    }}
    [data-theme="dark"] .chat-feed-item,
    [data-theme="dark"] .chat-channel-item,
    [data-theme="dark"] .chat-member-item,
    [data-theme="dark"] .rail-btn,
    [data-theme="dark"] .metric,
    [data-theme="dark"] .card {{
      transition: border-color 140ms ease, background 140ms ease, box-shadow 140ms ease;
    }}
    [data-theme="dark"] .list-search-input,
    [data-theme="dark"] #chat-input {{
      background: #07140d;
      border-color: #2b8a59;
      color: #c6ffdb;
      font-size: 11px;
      padding: 5px 7px;
    }}
    [data-theme="dark"] .list-search-input::placeholder,
    [data-theme="dark"] #chat-input::placeholder {{
      color: var(--ui-text-soft);
      opacity: 0.9;
    }}
    [data-theme="dark"] .list-search-input:focus,
    [data-theme="dark"] #chat-input:focus {{
      outline: 2px solid var(--ui-accent);
      outline-offset: 0;
      border-color: var(--ui-accent);
      outline-color: var(--ui-accent);
      background: #0b1e13;
      box-shadow: none;
    }}
    [data-theme="dark"] .chat-member-empty {{
      border-color: var(--ui-border);
      background: var(--ui-panel-alt);
      color: var(--ui-text-soft);
    }}
    [data-theme="dark"] .favorites-clear-btn {{
      border-color: #35556d;
      background: #16273a;
      color: #dbeeff;
    }}
    [data-theme="dark"] .favorites-clear-btn:hover {{
      background: #223448;
      border-color: #4e6a86;
    }}
    [data-theme="dark"] .favorites-empty {{
      border-color: var(--ui-border);
      background: var(--ui-panel-alt);
      color: var(--ui-text-soft);
    }}
    [data-theme="dark"] .favorite-node-item {{
      border-color: #35556d;
      background: #16273a;
      color: #dbeeff;
    }}
    [data-theme="dark"] .favorite-node-item:hover {{
      background: #223448;
      border-color: #4e6a86;
    }}
    [data-theme="dark"] .favorite-node-item.status-warn {{
      background: #40351f;
      color: #ffe4a0;
      border-color: #725f2e;
    }}
    [data-theme="dark"] .favorite-node-item.status-stale {{
      background: #412323;
      color: #ffc5c5;
      border-color: #744040;
    }}
    [data-theme="dark"] .favorite-node-item.status-unknown {{
      background: #222f2a;
      color: #bbcdc4;
      border-color: #3e544c;
    }}
    [data-theme="dark"] .favorite-node-item.selected-node {{
      background: #1f3342 !important;
      border-color: #4a6b87 !important;
      color: #eef6ff !important;
      box-shadow: inset 2px 0 0 #79c0ff;
    }}
    [data-theme="dark"] .favorite-node-id,
    [data-theme="dark"] .favorite-node-meta,
    [data-theme="dark"] .favorites-caption {{
      color: #a9bfd3;
    }}
    [data-theme="dark"] .favorite-toggle-btn {{
      border-color: rgba(124, 161, 190, 0.36);
      background: transparent;
      color: #93abc0;
      opacity: 0.76;
    }}
    [data-theme="dark"] .favorite-toggle-btn:hover {{
      background: rgba(121, 192, 255, 0.08);
      border-color: rgba(121, 192, 255, 0.56);
      color: #dcefff;
      opacity: 1;
    }}
    [data-theme="dark"] .favorite-toggle-btn.active {{
      border-color: rgba(219, 191, 90, 0.86);
      background: rgba(216, 180, 0, 0.16);
      color: #e9cf78;
      opacity: 0.95;
    }}
    [data-theme="dark"] .chat-reaction-popover {{
      box-shadow: var(--ui-shadow);
    }}
    [data-theme="dark"] .disk-track {{
      background: rgba(121, 192, 255, 0.16);
    }}
    [data-theme="dark"] .disk-fill {{
      background: var(--ui-accent-soft);
    }}
    [data-theme="dark"] .leaflet-container {{
      background: #0f141a;
    }}
    [data-theme="dark"] .leaflet-tile {{
      filter: none;
    }}
    [data-theme="dark"] .leaflet-popup-content-wrapper,
    [data-theme="dark"] .leaflet-popup-tip {{
      background: #1b2430;
      color: var(--ui-text);
    }}
    [data-theme="dark"] .chat-compose-shell,
    [data-theme="dark"] .card.chat .chat-compose-shell {{
      background: var(--ui-panel-alt);
      border-color: var(--ui-border);
    }}
    [data-theme="dark"] a {{
      color: var(--ui-link);
    }}
    @media (max-width: 1100px) {{
      .workspace-shell {{
        grid-template-columns: 1fr;
        grid-template-rows: auto auto auto;
        gap: 6px;
        padding: 6px;
      }}
      .teams-rail {{
        position: static;
        height: auto;
        min-height: 0;
        flex-direction: row;
        align-items: center;
        overflow-x: auto;
        overflow-y: hidden;
        padding: 6px;
      }}
      .teams-rail-title {{
        display: none;
      }}
      .rail-btn {{
        min-width: 74px;
      }}
      .workspace-shell.chat-panel-open {{
        grid-template-columns: 1fr;
      }}
      .chat-left-panel {{
        position: static;
        height: auto;
        min-height: 0;
        max-height: 220px;
      }}
      .layout {{
        grid-template-columns: 1fr;
        grid-template-rows: auto;
      }}
      .layout.view-network {{
        height: auto;
        min-height: 0;
      }}
      .layout.view-saved {{
        height: auto;
        min-height: 0;
      }}
      .layout.view-packets {{
        height: auto;
        min-height: 0;
      }}
      .layout.view-data {{
        height: auto;
        min-height: 0;
      }}
      .network-node-splitter {{
        display: none !important;
      }}
      .splitter, .hsplitter {{ display: none; }}
      .summary, .map, .map-data, .nodes, .favorites, .chat, .packets, .raw, .console {{ grid-column: 1; grid-row: auto; }}
      .map-frame {{ max-width: none; }}
      .nodes .scroll {{ max-height: 360px; }}
    }}
    @media (max-width: 760px) {{
      .chat-left-panel {{
        max-height: 180px;
      }}
      .rail-btn {{
        min-width: 68px;
        font-size: 9px;
      }}
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <h1>Meshtastic Deep Dashboard</h1>
    <div class="sub">
      <span id="revision-text" class="sub-text revision-text" title="{revision_title}">{revision_label}</span>
      <span class="pill">{safety_label}</span>
      <span class="pill">Packet buffer: {packet_limit}</span>
      <span class="pill">{history_label}</span>
      <span class="pill">Refresh: {refresh_ms} ms</span>
      <button id="theme-toggle-btn" class="theme-btn" type="button" title="Toggle theme between dark and light">Theme: Dark</button>
      <span class="pill selection-pill" id="selected-node-pill">Selected: none</span>
      <button id="clear-selection-btn" class="selection-btn" type="button" disabled>Clear</button>
      <span id="disk-meter" class="disk-meter" title="Disk free on dashboard host">
        <span id="disk-label" class="disk-label">Disk free: n/a</span>
        <span class="disk-track"><span id="disk-fill" class="disk-fill"></span></span>
      </span>
    </div>
  </div>

  <div class="workspace-shell">
    <aside class="teams-rail" aria-label="Dashboard views">
      <div class="teams-rail-title">Views</div>
      <button class="rail-btn active" data-view="chat" type="button" title="Teams-style chat workspace">Chat</button>
      <button class="rail-btn" data-view="network" type="button" title="Topology, nodes, and links">Network</button>
      <button class="rail-btn" data-view="saved" type="button" title="Saved favorite nodes">Saved</button>
      <button class="rail-btn" data-view="packets" type="button" title="Recent packet stream">Packets</button>
      <button class="rail-btn" data-view="data" type="button" title="Raw node/config views">Data</button>
      <button class="rail-btn" data-view="all" type="button" title="Show every panel">All</button>
    </aside>
    <aside id="chat-left-panel" class="chat-left-panel" hidden aria-label="Chat roster">
      <div class="chat-left-head">
        <div class="chat-left-title">Chat Navigator</div>
        <div id="chat-left-sub" class="chat-left-sub">Loading…</div>
      </div>
      <div class="chat-left-section">
        <div class="chat-left-label">Channels</div>
        <div id="chat-channel-list" class="chat-channel-list"></div>
      </div>
      <div class="chat-left-section chat-users-section">
        <div id="chat-users-title" class="chat-left-label">Users</div>
        <div id="chat-room-list" class="chat-member-list"></div>
        <div class="chat-left-bottom-bar">
          <div class="chat-user-search-wrap">
            <input id="chat-user-search-input" class="list-search-input" type="search" placeholder="Search by ID or name" autocomplete="off" />
          </div>
        </div>
      </div>
    </aside>
    <main class="workspace-main">
  <div id="dashboard-layout" class="layout view-chat">
    <section class="card summary">
      <h2>Summary</h2>
      <div class="body">
        <div class="metrics">
          <div class="metric"><div class="label">Target</div><div class="value" id="m-target">n/a</div></div>
          <div class="metric metric-action" id="metric-known-nodes" role="button" tabindex="0" aria-pressed="false" title="Show online node activity by hour"><div class="label">Known Nodes</div><div class="value" id="m-nodes">0</div></div>
          <div class="metric"><div class="label">Nodes With Position</div><div class="value" id="m-pos-nodes">0</div></div>
          <div class="metric"><div class="label">Live Packets</div><div class="value" id="m-live-packets">0</div></div>
          <div class="metric"><div class="label">Directed Links</div><div class="value" id="m-links">0</div></div>
          <div class="metric"><div class="label">LoRa Preset</div><div class="value" id="m-modem-preset">n/a</div></div>
          <div class="metric"><div class="label">Uptime (s)</div><div class="value" id="m-uptime">0</div></div>
        </div>
        <div style="margin-top:10px; font-size:12px; color:#3e5a46;">
          Updated: <span id="updated-at">n/a</span>
          <span id="local-state-error" class="warn"></span>
        </div>
      </div>
    </section>

    <section class="card chat">
      <div class="chat-card-head">
        <h2>MediumFast Chat</h2>
        <div id="chat-caption">
          Showing decoded text messages from recent packets.
        </div>
      </div>
      <div class="body">
        <div class="chat-shell">
          <div class="chat-main-pane">
            <div class="scroll chat-log-scroll">
              <div id="chat-feed" class="chat-feed"></div>
            </div>
            <div class="chat-compose-shell">
              <div class="chat-composer">
                <div class="chat-composer-top">
                  <div id="chat-reply-context" class="chat-reply-context" hidden>
                    <span id="chat-reply-label" class="chat-reply-label"></span>
                    <button id="chat-reply-clear-btn" class="chat-reply-clear-btn" type="button" title="Cancel reply" aria-label="Cancel reply">&times;</button>
                  </div>
                </div>
                <div class="chat-composer-input-row">
                  <input
                    id="chat-input"
                    class="list-search-input"
                    type="search"
                    maxlength="280"
                    placeholder="Message the room (^all)..."
                    autocomplete="off"
                  />
                  <button id="chat-emoji-btn" type="button" title="Insert emoji" aria-label="Insert emoji" aria-expanded="false">🙂</button>
                  <button id="chat-send-btn" type="button">Send</button>
                </div>
                <div id="chat-emoji-panel" class="chat-emoji-panel" hidden></div>
              </div>
              <div id="chat-send-status" class="chat-send-status"></div>
            </div>
            <div id="chat-reaction-popover" class="chat-reaction-popover" hidden></div>
          </div>
        </div>
      </div>
    </section>

    <section class="card map">
      <h2 id="map-card-title">Network Map</h2>
      <div class="body">
        <div class="map-frame">
          <div id="map"></div>
        </div>
        <div id="saved-node-details" class="saved-node-details" aria-live="polite"></div>
      </div>
    </section>

    <div class="hsplitter" data-target="top" title="Drag to resize top and middle panels"></div>

    <section class="card nodes">
      <h2 id="nodes-card-title">Nodes</h2>
      <div class="body nodes-body">
        <div class="nodes-search-wrap">
          <input id="nodes-search-input" class="list-search-input" type="search" placeholder="Search by ID or name" autocomplete="off" />
        </div>
        <div class="network-node-stack">
          <div class="scroll nodes-table-scroll">
            <table id="nodes-table">
                <thead>
                  <tr>
                  <th>Last Heard</th><th>ID</th><th>Name</th><th>HW</th><th>SNR</th><th>Hops</th><th>Battery</th><th>Saved</th><th>Pos</th><th>★</th>
                  </tr>
                </thead>
              <tbody></tbody>
            </table>
          </div>
          <div id="network-node-splitter" class="network-node-splitter" title="Drag to resize node list and history panel"></div>
          <div id="network-node-history-host" class="network-node-history-host" hidden></div>
        </div>
      </div>
    </section>

    <section class="card favorites">
      <h2>Saved Nodes</h2>
      <div class="body favorites-body">
        <div class="favorites-toolbar">
          <div class="favorites-search-wrap">
            <input id="favorites-search-input" class="list-search-input" type="search" placeholder="Search saved by ID or name" autocomplete="off" />
          </div>
          <button id="favorites-clear-btn" class="favorites-clear-btn" type="button" title="Remove all saved nodes">Clear Saved</button>
        </div>
        <div id="favorites-caption" class="favorites-caption">No saved nodes yet.</div>
        <div id="favorites-list" class="scroll favorites-list"></div>
      </div>
    </section>

    <section class="card map-data">
      <h2 id="map-data-title">Map Data</h2>
      <div id="map-data-body" class="body">
        <div id="map-data-live" class="map-data-live">
          <h3 style="margin:0 0 2px 0;font-size:13px;">Top Ports</h3>
          <div class="scroll" style="max-height:150px;">
            <table id="ports-table">
              <thead><tr><th>Port</th><th>Count</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
          <h3 style="margin:2px 0 2px 0;font-size:13px;">Top Links</h3>
          <div class="scroll" style="max-height:170px;">
            <table id="links-table">
              <thead><tr><th>From</th><th>To</th><th>Count</th><th>Hops</th><th>Status</th><th>Last</th></tr></thead>
              <tbody></tbody>
            </table>
          </div>
        </div>

        <div id="map-data-node" class="map-data-node" hidden>
          <div id="node-history-caption" class="history-caption">Select a node to view historical data.</div>
          <div class="history-tabs">
            <button class="history-tab-btn active" id="tab-btn-signal" data-tab="signal" type="button">Signal</button>
            <button class="history-tab-btn" id="tab-btn-overview" data-tab="overview" type="button">Overview</button>
          </div>
          <div id="tab-panel-signal" class="history-panel">
            <div id="signal-chart-wrap">
              <svg id="signal-chart" viewBox="0 0 900 220" preserveAspectRatio="none" aria-label="Node signal history"></svg>
              <div id="signal-empty" class="signal-empty" hidden>No historical signal points yet for this node.</div>
            </div>
            <div id="signal-timeline" class="signal-timeline" aria-label="Signal timeline"></div>
            <div class="signal-legend">
              <span class="legend-chip" style="color:#1f6f53;">Avg SNR (dB)</span>
              <span class="legend-chip" style="color:#265d7b;">Avg RSSI (dBm)</span>
            </div>
          </div>
          <div id="tab-panel-overview" class="history-panel" hidden>
            <div id="node-history-overview" class="overview-grid"></div>
          </div>
        </div>
        <div id="map-data-activity" class="map-data-activity" hidden>
          <div id="online-activity-caption" class="history-caption">Click Known Nodes to view when nodes are typically online.</div>
          <div id="online-activity-chart-wrap">
            <svg id="online-activity-chart" viewBox="0 0 900 220" preserveAspectRatio="none" aria-label="Online nodes by hour"></svg>
            <div id="online-activity-empty" class="signal-empty" hidden>No historical online-activity points yet.</div>
          </div>
          <div class="signal-legend">
            <span class="legend-chip activity-legend-nodes">Online nodes / hour</span>
          </div>
          <div id="online-activity-overview" class="overview-grid"></div>
        </div>
      </div>
    </section>

    <div class="hsplitter" data-target="mid" title="Drag to resize middle and lower panels"></div>

    <section class="card packets">
      <h2>Recent Packets</h2>
      <div class="body scroll">
        <table id="packets-table">
          <thead>
            <tr>
              <th>Captured</th><th>From</th><th>To</th><th>Port</th><th>SNR</th><th>RSSI</th><th>Text</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </section>

    <div class="splitter" data-row="8" title="Drag to resize side panels"></div>

    <section class="card raw">
      <h2>Raw Data</h2>
      <div class="body">
        <details><summary>my_info</summary><pre id="raw-my-info"></pre></details>
        <details><summary>metadata</summary><pre id="raw-metadata"></pre></details>
        <details><summary>local_config</summary><pre id="raw-local-config"></pre></details>
        <details><summary>module_config</summary><pre id="raw-module-config"></pre></details>
        <details><summary>channels</summary><pre id="raw-channels"></pre></details>
        <details><summary>nodes_full</summary><pre id="raw-nodes-full"></pre></details>
      </div>
    </section>

    <div class="hsplitter" data-target="low" title="Drag to resize lower panels and console"></div>

    <section class="card console">
      <h2>Realtime Console</h2>
      <div class="body">
        <div class="console-controls">
          <button id="console-clear-btn" type="button">Clear</button>
          <label><input id="console-autoscroll" type="checkbox" checked /> Auto-scroll</label>
        </div>
        <pre id="live-console"></pre>
      </div>
    </section>
  </div>
    </main>
  </div>

  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>
  <script>
    const refreshMs = {refresh_ms};
    const nodeHistoryHours = {node_history_hours};
    const nodeHistoryMaxPoints = {node_history_max_points};
    const map = L.map("map", {{
      preferCanvas: true,
      zoomAnimation: false,
      fadeAnimation: false,
      markerZoomAnimation: false,
      inertia: false,
      scrollWheelZoom: false,
    }}).setView([39.5, -98.35], 4);
    const mapTileConfigs = {{
      light: {{
        url: "https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",
        options: {{
          maxZoom: 19,
          attribution: "&copy; OpenStreetMap contributors",
        }},
      }},
      dark: {{
        url: "https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png",
        options: {{
          maxZoom: 20,
          subdomains: "abcd",
          attribution: "&copy; OpenStreetMap contributors &copy; CARTO",
        }},
      }},
    }};

    const mapElement = document.getElementById("map");
    const mapFrameElement = mapElement ? mapElement.closest(".map-frame") : null;
    const nodeLayer = L.layerGroup().addTo(map);
    const edgeLayer = L.layerGroup().addTo(map);
    const trailLayer = L.layerGroup().addTo(map);
    const nodeMarkers = new Map();
    const selectionStorageKey = "meshDashboardSelectedNodeId";
    const favoritesStorageKey = "meshDashboardFavoriteNodeIdsV1";
    const nodeNameCacheStorageKey = "meshDashboardNodeNameCacheV1";
    const splitStorageKey = "meshDashboardLayoutSplitState";
    const networkNodesSplitStorageKey = "meshDashboardNetworkNodesSplitPct";
    const layoutViewStorageKey = "meshDashboardLayoutView";
    const chatChannelStorageKey = "meshDashboardChatChannel";
    const themeStorageKey = "meshDashboardThemePreference";
    const themeAcceptedModes = new Set(["auto", "dark", "light"]);
    const chatBottomStickThresholdPx = 28;
    const chatWarnWindowSeconds = 10 * 60;
    const chatStaleWindowSeconds = 30 * 60;
    const chatRosterMaxEntries = 180;
    const chatEmojiChoices = [
      "😀", "😁", "😂", "🤣", "😊", "😉", "😎", "🤔",
      "👍", "👎", "👏", "🙏", "✅", "❌", "⚠️", "🔥",
      "❤️", "💯", "📡", "📶", "🛰️", "🏠", "🚗", "🎯",
    ];
    const consoleMaxLines = 1200;
    const tableSortState = {{
      "nodes-table": {{ index: 0, dir: "desc" }},
      "links-table": {{ index: 2, dir: "desc" }},
      "ports-table": {{ index: 1, dir: "desc" }},
      "packets-table": {{ index: 0, dir: "desc" }},
    }};
    const wheelActivationLeaseMs = 1400;
    const knownLayoutViews = new Set(["chat", "network", "saved", "packets", "data", "all"]);
    const knownChatChannels = new Set(["all", "direct"]);
    const knownDeliveryStates = new Set(["pending", "sent", "acked", "nak", "timeout", "error"]);
    const reactionPopoverMaxNames = 12;
    const sortableTables = new Set(Object.keys(tableSortState));
    const consoleLines = [];
    const consoleKeyQueue = [];
    const consoleSeen = new Set();
    const wheelPaneSelector = ".scroll, #live-console, details pre";
    let selectedNodeId = null;
    let mapDataFocus = "auto";
    let activeMapDataMode = "live";
    let activeHistoryTab = "signal";
    let pendingSelectionScroll = false;
    let latestState = null;
    let lastMapSignature = "";
    let mapResizeRaf = null;
    let splitPct = 64;
    let splitTopPx = 430;
    let splitMidPx = 250;
    let splitLowPx = 240;
    let networkNodesListPct = 52;
    let consoleAutoscroll = true;
    let fitDone = false;
    let mapResizeObserver = null;
    let activeWheelPane = null;
    let activeWheelPaneLease = null;
    let mapWheelZoomActive = false;
    let mapWheelJustArmed = false;
    let mapWheelLease = null;
    let chatSendInFlight = false;
    let chatStickToBottom = true;
    let activeLayoutView = "chat";
    let activeChatChannel = "all";
    let chatEmojiMode = "compose";
    let chatReactionTargetId = null;
    let chatReplyTargetId = null;
    let chatReplyTargetName = "";
    let chatReplyTargetText = "";
    let chatReactionPopoverAnchor = null;
    let chatReactionPopoverHideTimer = null;
    let nodesSearchQuery = "";
    let chatUserSearchQuery = "";
    let themePreference = "auto";
    let themeMediaQuery = null;
    let mapTileLayer = null;
    let mapTileTheme = "";
    let chatUnreadCount = 0;
    const chatUnreadByChannel = {{ all: 0, direct: 0 }};
    const chatUnreadLatestByChannel = {{ all: "", direct: "" }};
    let chatUnreadInitialized = false;
    const chatSeenMessageKeys = new Set();
    const chatSeenMessageOrder = [];
    const nodeHistoryCache = new Map();
    const onlineActivityCache = new Map();
    const nodeNameCache = new Map();
    const favoriteNodeIds = new Set();
    let favoritesSearchQuery = "";

    function applyMapTiles(themeName) {{
      const nextTheme = themeName === "dark" ? "dark" : "light";
      if (mapTileLayer && mapTileTheme === nextTheme) {{
        return;
      }}
      const cfg = mapTileConfigs[nextTheme] || mapTileConfigs.light;
      if (mapTileLayer) {{
        map.removeLayer(mapTileLayer);
      }}
      mapTileLayer = L.tileLayer(cfg.url, cfg.options).addTo(map);
      mapTileTheme = nextTheme;
    }}

    function requestMapResize() {{
      if (mapResizeRaf !== null) {{
        cancelAnimationFrame(mapResizeRaf);
      }}
      mapResizeRaf = requestAnimationFrame(() => {{
        map.invalidateSize({{ pan: false, animate: false }});
        mapResizeRaf = null;
      }});
    }}

    function syncMapSize() {{
      splitTopPx = clampTopSplitPx(splitTopPx);
      splitMidPx = clampMidSplitPx(splitMidPx);
      splitLowPx = clampLowSplitPx(splitLowPx);
      applySplitState();
      requestMapResize();
    }}

    function bindMapContainerObserver() {{
      if (mapResizeObserver || !mapFrameElement || typeof ResizeObserver === "undefined") {{
        return;
      }}
      mapResizeObserver = new ResizeObserver(() => {{
        requestMapResize();
      }});
      mapResizeObserver.observe(mapFrameElement);
    }}

    function isMapWheelGuardEnabled() {{
      return activeLayoutView !== "network" && activeLayoutView !== "saved";
    }}

    function setMapWheelZoomActive(active) {{
      const guardEnabled = isMapWheelGuardEnabled();
      const next = guardEnabled ? !!active : true;
      if (mapWheelZoomActive === next) {{
        return;
      }}
      mapWheelZoomActive = next;
      if (!mapWheelZoomActive || !guardEnabled) {{
        mapWheelJustArmed = false;
        if (mapWheelLease !== null) {{
          clearTimeout(mapWheelLease);
          mapWheelLease = null;
        }}
      }}
      if (mapWheelZoomActive) {{
        map.scrollWheelZoom.enable();
      }} else {{
        map.scrollWheelZoom.disable();
      }}
      if (mapFrameElement) {{
        if (guardEnabled) {{
          mapFrameElement.classList.toggle("map-wheel-active", mapWheelZoomActive);
          mapFrameElement.setAttribute(
            "title",
            mapWheelZoomActive
              ? "Map wheel zoom active. Click outside map (or press Esc) to return wheel scrolling to page."
              : "Click map to enable wheel zoom."
          );
        }} else {{
          mapFrameElement.classList.remove("map-wheel-active");
          mapFrameElement.setAttribute("title", "Scroll wheel zoom is enabled.");
        }}
      }}
    }}

    function touchMapWheelLease() {{
      if (!mapWheelZoomActive || !isMapWheelGuardEnabled()) {{
        return;
      }}
      if (mapWheelLease !== null) {{
        clearTimeout(mapWheelLease);
      }}
      mapWheelLease = window.setTimeout(() => {{
        setMapWheelZoomActive(false);
      }}, wheelActivationLeaseMs);
    }}

    function bindMapWheelActivation() {{
      if (!mapFrameElement || mapFrameElement.dataset.wheelMapBound === "1") {{
        return;
      }}
      mapFrameElement.dataset.wheelMapBound = "1";
      setMapWheelZoomActive(activeLayoutView === "network" || activeLayoutView === "saved");

      mapFrameElement.addEventListener("pointerdown", (ev) => {{
        if (!isMapWheelGuardEnabled()) {{
          return;
        }}
        if (!(ev.target instanceof Element)) {{
          return;
        }}
        if (ev.target.closest(".leaflet-control")) {{
          return;
        }}
        if (!mapWheelZoomActive) {{
          mapWheelJustArmed = true;
        }}
        setMapWheelZoomActive(true);
        touchMapWheelLease();
      }});

      mapFrameElement.addEventListener("wheel", () => {{
        touchMapWheelLease();
      }}, {{ passive: true }});

      document.addEventListener("pointerdown", (ev) => {{
        if (!isMapWheelGuardEnabled()) {{
          return;
        }}
        if (!(ev.target instanceof Element)) {{
          setMapWheelZoomActive(false);
          return;
        }}
        if (!mapFrameElement.contains(ev.target)) {{
          setMapWheelZoomActive(false);
        }}
      }});
      document.addEventListener("keydown", (ev) => {{
        if (!isMapWheelGuardEnabled()) {{
          return;
        }}
        if (ev.key === "Escape") {{
          setMapWheelZoomActive(false);
        }}
      }});
    }}

    function bindWheelPassthrough() {{
      const isWheelPassthroughEnabled = () => (
        activeLayoutView !== "chat" && activeLayoutView !== "network" && activeLayoutView !== "saved"
      );

      const refreshWheelPaneHints = () => {{
        const enabled = isWheelPassthroughEnabled();
        if (!enabled && activeWheelPane instanceof HTMLElement) {{
          activeWheelPane.classList.remove("wheel-scroll-active");
          activeWheelPane = null;
        }}
        if (!enabled && activeWheelPaneLease !== null) {{
          clearTimeout(activeWheelPaneLease);
          activeWheelPaneLease = null;
        }}
        for (const el of document.querySelectorAll(wheelPaneSelector)) {{
          if (!(el instanceof HTMLElement)) continue;
          if (enabled) {{
            if (!el.getAttribute("title")) {{
              el.setAttribute("title", "Click panel to wheel-scroll inside it. Auto-releases after a brief pause.");
              el.dataset.wheelHintOwned = "1";
            }}
          }} else if (el.dataset.wheelHintOwned === "1") {{
            el.removeAttribute("title");
            delete el.dataset.wheelHintOwned;
          }}
        }}
      }};

      const clearWheelPaneLease = () => {{
        if (activeWheelPaneLease !== null) {{
          clearTimeout(activeWheelPaneLease);
          activeWheelPaneLease = null;
        }}
      }};

      const touchWheelPaneLease = () => {{
        if (!(activeWheelPane instanceof HTMLElement)) {{
          clearWheelPaneLease();
          return;
        }}
        clearWheelPaneLease();
        activeWheelPaneLease = window.setTimeout(() => {{
          setActiveWheelPane(null);
        }}, wheelActivationLeaseMs);
      }};

      const setActiveWheelPane = (next) => {{
        if (activeWheelPane === next) {{
          if (activeWheelPane instanceof HTMLElement) {{
            touchWheelPaneLease();
          }}
          return;
        }}
        if (activeWheelPane instanceof HTMLElement) {{
          activeWheelPane.classList.remove("wheel-scroll-active");
        }}
        activeWheelPane = next instanceof HTMLElement ? next : null;
        if (activeWheelPane) {{
          activeWheelPane.classList.add("wheel-scroll-active");
          if (document.activeElement !== activeWheelPane) {{
            activeWheelPane.focus({{ preventScroll: true }});
          }}
          touchWheelPaneLease();
        }} else {{
          clearWheelPaneLease();
        }}
      }};

      const canScrollInDirection = (el, delta) => {{
        if (!(el instanceof HTMLElement)) {{
          return false;
        }}
        const max = el.scrollHeight - el.clientHeight;
        if (max <= 1) {{
          return false;
        }}
        if (delta > 0) {{
          return el.scrollTop < (max - 1);
        }}
        if (delta < 0) {{
          return el.scrollTop > 1;
        }}
        return false;
      }};

      const routeWheelToPage = (delta) => {{
        window.scrollBy({{ top: delta, behavior: "auto" }});
      }};

      for (const el of document.querySelectorAll(wheelPaneSelector)) {{
        if (!(el instanceof HTMLElement) || el.dataset.wheelPassBound === "1") {{
          continue;
        }}
        el.dataset.wheelPassBound = "1";
        if (!el.hasAttribute("tabindex")) {{
          el.tabIndex = 0;
        }}
        el.addEventListener("pointerdown", () => {{
          if (!isWheelPassthroughEnabled()) {{
            return;
          }}
          setActiveWheelPane(el);
        }});
        el.addEventListener("focusin", () => {{
          if (!isWheelPassthroughEnabled()) {{
            return;
          }}
          setActiveWheelPane(el);
        }});
        el.addEventListener(
          "wheel",
          (ev) => {{
            if (!isWheelPassthroughEnabled()) {{
              return;
            }}
            if (ev.defaultPrevented || ev.ctrlKey || ev.metaKey) {{
              return;
            }}
            const delta = Math.abs(ev.deltaY) >= Math.abs(ev.deltaX) ? ev.deltaY : ev.deltaX;
            if (!Number.isFinite(delta) || delta === 0) {{
              return;
            }}

            const paneIsActive = activeWheelPane === el;
            if (!paneIsActive) {{
              ev.preventDefault();
              routeWheelToPage(delta);
              return;
            }}

            if (canScrollInDirection(el, delta)) {{
              touchWheelPaneLease();
              return;
            }}

            ev.preventDefault();
            routeWheelToPage(delta);
            setActiveWheelPane(null);
          }},
          {{ passive: false }}
        );
      }}
      refreshWheelPaneHints();

      if (document.body.dataset.wheelPassDocBound !== "1") {{
        document.body.dataset.wheelPassDocBound = "1";
        document.addEventListener("pointerdown", (ev) => {{
          if (!(ev.target instanceof Element)) {{
            setActiveWheelPane(null);
            return;
          }}
          if (!ev.target.closest(wheelPaneSelector)) {{
            setActiveWheelPane(null);
          }}
        }});
        document.addEventListener("keydown", (ev) => {{
          if (ev.key === "Escape") {{
            setActiveWheelPane(null);
          }}
        }});
      }}

      // Expose a tiny hook so view changes can toggle wheel hints/behavior.
      window.meshRefreshWheelHints = refreshWheelPaneHints;
    }}

    map.whenReady(() => {{
      requestMapResize();
      bindMapContainerObserver();
      bindMapWheelActivation();
    }});
    window.addEventListener("resize", () => {{
      setTimeout(syncMapSize, 120);
    }});

    function setText(id, value) {{
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = value == null ? "n/a" : String(value);
    }}

    function normalizeThemeMode(raw) {{
      const clean = String(raw || "").trim().toLowerCase();
      return themeAcceptedModes.has(clean) ? clean : "auto";
    }}

    function systemPreferredTheme() {{
      if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {{
        return "dark";
      }}
      return "light";
    }}

    function updateThemeToggleLabel(resolvedTheme) {{
      const btn = document.getElementById("theme-toggle-btn");
      if (!(btn instanceof HTMLButtonElement)) return;
      const resolvedText = resolvedTheme === "dark" ? "Dark" : "Light";
      btn.textContent = `Theme: ${{resolvedText}}`;
      if (themePreference === "auto") {{
        btn.title = `Theme follows system (${{resolvedText}}). Click to lock Light/Dark toggle.`;
      }} else {{
        btn.title = `Theme locked to ${{resolvedText}}. Click to toggle Light/Dark.`;
      }}
      btn.setAttribute("aria-label", btn.title);
    }}

    function applyThemePreference(mode, persist = true) {{
      const normalized = normalizeThemeMode(mode);
      themePreference = normalized;
      const resolvedTheme = normalized === "auto" ? systemPreferredTheme() : normalized;
      document.documentElement.setAttribute("data-theme", resolvedTheme);
      document.documentElement.setAttribute("data-theme-pref", normalized);
      applyMapTiles(resolvedTheme);
      updateThemeToggleLabel(resolvedTheme);
      if (isSelectableNodeId(selectedNodeId)) {{
        const cached = nodeHistoryCache.get(selectedNodeId);
        if (cached && cached.data && Array.isArray(cached.data.points)) {{
          renderSignalChart(cached.data.points);
        }}
      }}
      if (activeMapDataMode === "activity") {{
        const cachedActivity = onlineActivityCache.get(String(nodeHistoryHours));
        if (cachedActivity && cachedActivity.data && Array.isArray(cachedActivity.data.points)) {{
          renderOnlineActivityChart(cachedActivity.data.points);
        }}
      }}

      if (!persist) return;
      try {{
        window.localStorage.setItem(themeStorageKey, normalized);
      }} catch (_err) {{
      }}
    }}

    function bindThemeToggle() {{
      const btn = document.getElementById("theme-toggle-btn");
      if (btn instanceof HTMLButtonElement && btn.dataset.bound !== "1") {{
        btn.dataset.bound = "1";
        btn.addEventListener("click", () => {{
          const resolved = themePreference === "auto" ? systemPreferredTheme() : themePreference;
          const next = resolved === "dark" ? "light" : "dark";
          applyThemePreference(next, true);
        }});
      }}

      if (!themeMediaQuery && window.matchMedia) {{
        themeMediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        const onThemeChange = () => {{
          if (themePreference === "auto") {{
            applyThemePreference("auto", false);
          }}
        }};
        if (typeof themeMediaQuery.addEventListener === "function") {{
          themeMediaQuery.addEventListener("change", onThemeChange);
        }} else if (typeof themeMediaQuery.addListener === "function") {{
          themeMediaQuery.addListener(onThemeChange);
        }}
      }}
    }}

    function loadThemePreference() {{
      let stored = "auto";
      try {{
        stored = window.localStorage.getItem(themeStorageKey) || "auto";
      }} catch (_err) {{
      }}
      applyThemePreference(stored, false);
    }}

    function getChatScroller() {{
      const feed = document.getElementById("chat-feed");
      if (!(feed instanceof HTMLElement)) return null;
      const scroller = feed.closest(".scroll");
      return scroller instanceof HTMLElement ? scroller : null;
    }}

    function isNearBottom(scroller, thresholdPx = chatBottomStickThresholdPx) {{
      if (!(scroller instanceof HTMLElement)) return false;
      const remaining = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
      return remaining <= thresholdPx;
    }}

    function bindChatAutoScroll() {{
      const scroller = getChatScroller();
      if (!(scroller instanceof HTMLElement) || scroller.dataset.chatScrollBound === "1") return;
      scroller.dataset.chatScrollBound = "1";
      chatStickToBottom = true;
      scroller.addEventListener("scroll", () => {{
        chatStickToBottom = isNearBottom(scroller);
      }});
    }}

    function bytesToGiB(value) {{
      const num = Number(value);
      if (!Number.isFinite(num) || num < 0) return null;
      return num / (1024 ** 3);
    }}

    function parseDashboardTimeToUnix(value) {{
      const text = String(value == null ? "" : value).trim();
      if (!text) return null;
      const iso = text.includes("T") ? text : text.replace(" ", "T");
      const parsed = Date.parse(iso);
      if (!Number.isFinite(parsed)) return null;
      return Math.floor(parsed / 1000);
    }}

    function nodeLastHeardUnix(node) {{
      if (!node || typeof node !== "object") return null;
      const raw = Number(node.last_heard_unix);
      if (Number.isFinite(raw) && raw > 0) {{
        return Math.floor(raw);
      }}
      return parseDashboardTimeToUnix(node.last_heard);
    }}

    function freshnessStatus(lastSeenUnix, nowUnix = Math.floor(Date.now() / 1000)) {{
      const ts = Number(lastSeenUnix);
      if (!Number.isFinite(ts) || ts <= 0) return "unknown";
      const age = Math.max(0, nowUnix - ts);
      if (age <= chatWarnWindowSeconds) return "online";
      if (age <= chatStaleWindowSeconds) return "warn";
      return "stale";
    }}

    function statusRank(status) {{
      const key = String(status || "unknown");
      if (key === "online") return 0;
      if (key === "warn") return 1;
      if (key === "stale") return 2;
      return 3;
    }}

    function pickFresherStatus(currentStatus, nextStatus) {{
      return statusRank(nextStatus) < statusRank(currentStatus) ? nextStatus : currentStatus;
    }}

    function normalizeChatChannel(raw) {{
      const clean = String(raw || "").trim().toLowerCase();
      return knownChatChannels.has(clean) ? clean : "all";
    }}

    function channelLabel(key) {{
      return key === "direct" ? "Peer-to-peer" : "Everyone";
    }}

    function normalizeDeliveryState(raw) {{
      const clean = String(raw || "").trim().toLowerCase();
      return knownDeliveryStates.has(clean) ? clean : "";
    }}

    function deliveryStateLabel(state) {{
      const clean = normalizeDeliveryState(state);
      if (clean === "pending") return "Pending";
      if (clean === "acked") return "Delivered";
      if (clean === "nak") return "Failed";
      if (clean === "timeout") return "Timed out";
      if (clean === "error") return "Error";
      if (clean === "sent") return "Sent";
      return "";
    }}

    function deliveryStateTitle(state, errorText = "") {{
      const clean = normalizeDeliveryState(state);
      const detail = String(errorText || "").trim();
      if (!clean) return "";
      if (detail) return `${{deliveryStateLabel(clean)}}. ${{detail}}`;
      if (clean === "pending") return "Awaiting mesh ACK";
      if (clean === "acked") return "ACK received";
      if (clean === "nak") return "NAK received";
      if (clean === "timeout") return "No ACK received before timeout";
      if (clean === "error") return "Delivery status error";
      return "Message sent";
    }}

    function isRetryableDeliveryState(state) {{
      const clean = normalizeDeliveryState(state);
      return clean === "nak" || clean === "timeout" || clean === "error";
    }}

    function reactionPopoverElement() {{
      const popover = document.getElementById("chat-reaction-popover");
      return popover instanceof HTMLElement ? popover : null;
    }}

    function clearReactionPopoverHideTimer() {{
      if (chatReactionPopoverHideTimer !== null) {{
        clearTimeout(chatReactionPopoverHideTimer);
        chatReactionPopoverHideTimer = null;
      }}
    }}

    function scheduleReactionPopoverHide(delayMs = 120) {{
      clearReactionPopoverHideTimer();
      chatReactionPopoverHideTimer = window.setTimeout(() => {{
        closeReactionPopover(true);
      }}, Math.max(0, Number(delayMs) || 0));
    }}

    function normalizeReactionName(value) {{
      const clean = String(value == null ? "" : value).replace(/\\s+/g, " ").trim();
      if (!clean) return "Unknown node";
      return clean;
    }}

    function reactionNameInitials(value) {{
      const clean = normalizeReactionName(value).replace(/[^A-Za-z0-9 ]+/g, " ").trim();
      if (!clean) return "?";
      const parts = clean.split(/\\s+/).filter(Boolean);
      if (parts.length <= 1) {{
        return parts[0].slice(0, 2).toUpperCase();
      }}
      return `${{parts[0][0] || ""}}${{parts[1][0] || ""}}`.toUpperCase() || "?";
    }}

    function parseReactionChipNames(chip) {{
      if (!(chip instanceof HTMLButtonElement)) return [];
      const raw = String(chip.dataset.reactors || "").trim();
      if (!raw) return [];
      try {{
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return [];
        return parsed
          .map((item) => normalizeReactionName(item))
          .filter((name, idx, arr) => !!name && arr.indexOf(name) === idx);
      }} catch (_err) {{
        return [];
      }}
    }}

    function positionReactionPopover(anchor, popover) {{
      if (!(anchor instanceof HTMLElement) || !(popover instanceof HTMLElement) || popover.hidden) {{
        return;
      }}
      const anchorRect = anchor.getBoundingClientRect();
      const margin = 8;
      const width = popover.offsetWidth || 240;
      const height = popover.offsetHeight || 140;
      const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 1280;
      const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 720;

      let left = anchorRect.left + (anchorRect.width / 2) - (width / 2);
      if (left < margin) left = margin;
      if ((left + width) > (viewportWidth - margin)) {{
        left = Math.max(margin, viewportWidth - width - margin);
      }}

      let top = anchorRect.top - height - 10;
      if (top < margin) {{
        top = anchorRect.bottom + 10;
      }}
      if ((top + height) > (viewportHeight - margin)) {{
        top = Math.max(margin, viewportHeight - height - margin);
      }}

      popover.style.left = `${{Math.round(left)}}px`;
      popover.style.top = `${{Math.round(top)}}px`;
    }}

    function openReactionPopoverForChip(chip) {{
      if (!(chip instanceof HTMLButtonElement)) return;
      const popover = reactionPopoverElement();
      if (!(popover instanceof HTMLElement)) return;

      const emoji = String(chip.dataset.emoji || "").trim() || "🙂";
      const names = parseReactionChipNames(chip);
      const rawCount = Number(chip.dataset.reactorCount || "");
      const count = Number.isFinite(rawCount) && rawCount > 0 ? Math.trunc(rawCount) : names.length;
      const shownNames = names.slice(0, reactionPopoverMaxNames);
      const listRows = shownNames.map((name) => (
        `<div class="chat-reaction-popover-row">
          <span class="chat-reaction-popover-avatar">${{escAttr(reactionNameInitials(name))}}</span>
          <span class="chat-reaction-popover-name">${{escAttr(name)}}</span>
        </div>`
      )).join("");
      const unknownCount = Math.max(0, count - shownNames.length);

      popover.innerHTML = `
        <div class="chat-reaction-popover-head">
          <span><span class="chat-reaction-popover-emoji">${{escAttr(emoji)}}</span> Reactions</span>
          <span class="chat-reaction-popover-count">${{count}}</span>
        </div>
        <div class="chat-reaction-popover-list">
          ${{listRows || `<div class="chat-reaction-popover-row"><span class="chat-reaction-popover-name">No named reactors yet</span></div>`}}
        </div>
        ${{unknownCount > 0 ? `<div class="chat-reaction-popover-more">+${{unknownCount}} more</div>` : ""}}
      `;
      popover.hidden = false;
      chatReactionPopoverAnchor = chip;
      positionReactionPopover(chip, popover);
    }}

    function closeReactionPopover(force = false) {{
      const popover = reactionPopoverElement();
      if (!(popover instanceof HTMLElement)) return;
      if (!force && popover.hidden) return;
      clearReactionPopoverHideTimer();
      popover.hidden = true;
      popover.innerHTML = "";
      chatReactionPopoverAnchor = null;
    }}

    function bindReactionPopover() {{
      const popover = reactionPopoverElement();
      if (!(popover instanceof HTMLElement) || popover.dataset.bound === "1") return;
      popover.dataset.bound = "1";

      popover.addEventListener("pointerenter", () => {{
        clearReactionPopoverHideTimer();
      }});
      popover.addEventListener("pointerleave", () => {{
        scheduleReactionPopoverHide(120);
      }});

      document.addEventListener("pointerdown", (ev) => {{
        const target = ev.target;
        if (!(target instanceof Element)) {{
          closeReactionPopover(true);
          return;
        }}
        if (target.closest(".chat-reaction-chip") || target.closest("#chat-reaction-popover")) {{
          return;
        }}
        closeReactionPopover(true);
      }});

      document.addEventListener("keydown", (ev) => {{
        if (ev.key === "Escape") {{
          closeReactionPopover(true);
        }}
      }});

      window.addEventListener("resize", () => {{
        const el = reactionPopoverElement();
        if (!(el instanceof HTMLElement) || el.hidden) return;
        if (!(chatReactionPopoverAnchor instanceof HTMLElement)) {{
          closeReactionPopover(true);
          return;
        }}
        positionReactionPopover(chatReactionPopoverAnchor, el);
      }});
      window.addEventListener("scroll", () => {{
        const el = reactionPopoverElement();
        if (!(el instanceof HTMLElement) || el.hidden) return;
        if (!(chatReactionPopoverAnchor instanceof HTMLElement)) {{
          closeReactionPopover(true);
          return;
        }}
        positionReactionPopover(chatReactionPopoverAnchor, el);
      }}, true);
    }}

    function compactInlineMessage(value, maxLen = 88) {{
      const text = String(value == null ? "" : value).replace(/\\s+/g, " ").trim();
      if (!text) return "(no text)";
      if (text.length <= maxLen) return text;
      return `${{text.slice(0, Math.max(8, maxLen - 1)).trimEnd()}}…`;
    }}

    function renderChatReplyContext() {{
      const context = document.getElementById("chat-reply-context");
      const top = document.querySelector(".chat-composer-top");
      const label = document.getElementById("chat-reply-label");
      if (!(context instanceof HTMLElement) || !(label instanceof HTMLElement)) return;
      const replyId = Number(chatReplyTargetId);
      if (!Number.isInteger(replyId) || replyId <= 0) {{
        context.hidden = true;
        if (top instanceof HTMLElement) {{
          top.classList.remove("has-reply");
        }}
        label.textContent = "";
        return;
      }}
      const fromName = String(chatReplyTargetName || "Unknown node").trim() || "Unknown node";
      const snippet = compactInlineMessage(chatReplyTargetText, 96);
      label.textContent = `Replying to ${{fromName}}: ${{snippet}}`;
      context.hidden = false;
      if (top instanceof HTMLElement) {{
        top.classList.add("has-reply");
      }}
    }}

    function clearChatReplyTarget() {{
      chatReplyTargetId = null;
      chatReplyTargetName = "";
      chatReplyTargetText = "";
      renderChatReplyContext();
    }}

    function setChatReplyTarget(replyId, fromName, text) {{
      const parsed = Number(replyId);
      if (!Number.isInteger(parsed) || parsed <= 0) {{
        setChatSendStatus("Cannot reply: target message id is missing.", true);
        return;
      }}
      chatReplyTargetId = parsed;
      chatReplyTargetName = String(fromName || "Unknown node").trim() || "Unknown node";
      chatReplyTargetText = String(text || "");
      renderChatReplyContext();
      const input = document.getElementById("chat-input");
      if (input instanceof HTMLInputElement) {{
        input.focus({{ preventScroll: true }});
      }}
      setChatSendStatus(`Reply target set: ${{chatReplyTargetName}}`, false);
    }}

    function applyChatChannel(channelKey, persist = true) {{
      const nextChannel = normalizeChatChannel(channelKey);
      const changed = activeChatChannel !== nextChannel;
      activeChatChannel = nextChannel;
      if (activeLayoutView === "chat") {{
        clearChatUnread(activeChatChannel);
      }}
      if (persist) {{
        try {{
          window.localStorage.setItem(chatChannelStorageKey, activeChatChannel);
        }} catch (_err) {{
        }}
      }}
      const usersTitle = document.getElementById("chat-users-title");
      if (usersTitle) {{
        usersTitle.textContent = activeChatChannel === "direct" ? "Users (Peer-to-peer)" : "Users (Everyone)";
      }}
      const input = document.getElementById("chat-input");
      if (input instanceof HTMLInputElement) {{
        if (activeChatChannel === "direct") {{
          input.placeholder = isSelectableNodeId(selectedNodeId)
            ? `Direct message to ${{selectedNodeId}}...`
            : "Select a user to direct message...";
        }} else {{
          input.placeholder = "Message the room (^all)...";
        }}
      }}
      if (changed) {{
        clearChatReplyTarget();
      }} else {{
        renderChatReplyContext();
      }}
      if (latestState) {{
        renderChat(latestState);
      }}
    }}

    function loadChatChannel() {{
      let preferred = "all";
      try {{
        preferred = normalizeChatChannel(window.localStorage.getItem(chatChannelStorageKey) || "all");
      }} catch (_err) {{
      }}
      applyChatChannel(preferred, false);
    }}

    function classifyMessageChannel(msg) {{
      if (!msg || typeof msg !== "object") return "all";
      const toId = normalizeNodeId(msg.to || msg.destination || "");
      if (!toId || toId === "^all" || toId === "all" || toId === "broadcast") {{
        return "all";
      }}
      return "direct";
    }}

    function setChatSendStatus(message, isError = false) {{
      const el = document.getElementById("chat-send-status");
      if (!(el instanceof HTMLElement)) return;
      el.textContent = message ? String(message) : "";
      el.classList.toggle("error", !!isError);
    }}

    function setChatSendBusy(isBusy) {{
      chatSendInFlight = !!isBusy;
      const btn = document.getElementById("chat-send-btn");
      const emojiBtn = document.getElementById("chat-emoji-btn");
      const replyClearBtn = document.getElementById("chat-reply-clear-btn");
      const input = document.getElementById("chat-input");
      if (btn instanceof HTMLButtonElement) {{
        btn.disabled = chatSendInFlight;
        btn.textContent = chatSendInFlight ? "Sending..." : "Send";
      }}
      if (emojiBtn instanceof HTMLButtonElement) {{
        emojiBtn.disabled = chatSendInFlight;
      }}
      if (replyClearBtn instanceof HTMLButtonElement) {{
        replyClearBtn.disabled = chatSendInFlight;
      }}
      if (input instanceof HTMLInputElement) {{
        input.disabled = chatSendInFlight;
      }}
      if (chatSendInFlight) {{
        closeChatEmojiPanel();
      }}
    }}

    async function sendChatPayload(body, successMessage) {{
      if (chatSendInFlight) return null;
      setChatSendBusy(true);
      setChatSendStatus("Sending...");
      try {{
        const resp = await fetch("/api/chat/send", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(body || {{}}),
        }});
        const payload = await resp.json().catch(() => ({{}}));
        if (!resp.ok || !payload.ok) {{
          const msg = payload && payload.error ? payload.error : `send failed (${{resp.status}})`;
          throw new Error(msg);
        }}
        setChatSendStatus(successMessage || `Sent at ${{payload.sent_at || "now"}}`);
        await poll();
        return payload;
      }} catch (err) {{
        setChatSendStatus(`Send error: ${{err.message || err}}`, true);
        return null;
      }} finally {{
        setChatSendBusy(false);
      }}
    }}

    async function sendChatMessage() {{
      const input = document.getElementById("chat-input");
      if (!(input instanceof HTMLInputElement)) return;
      const text = input.value.trim();
      if (!text) {{
        setChatSendStatus("Enter a message before sending.", true);
        return;
      }}
      let destination = "^all";
      if (activeChatChannel === "direct") {{
        if (!isSelectableNodeId(selectedNodeId)) {{
          setChatSendStatus("Select a user before sending a peer-to-peer message.", true);
          return;
        }}
        destination = selectedNodeId;
      }}
      const replyId = Number(chatReplyTargetId);
      const requestBody = {{
        text,
        destination,
        channel_index: 0,
      }};
      if (Number.isInteger(replyId) && replyId > 0) {{
        requestBody.reply_id = replyId;
      }}
      const payload = await sendChatPayload(
        requestBody,
        null
      );
      if (payload && payload.ok) {{
        input.value = "";
        const replied = Number.isInteger(replyId) && replyId > 0;
        clearChatReplyTarget();
        if (destination === "^all") {{
          setChatSendStatus(`${{replied ? "Reply sent" : "Sent"}} to Everyone at ${{payload.sent_at || "now"}}`);
        }} else {{
          const awaitingAck = payload.ack_requested === true && normalizeDeliveryState(payload.delivery_state) === "pending";
          if (awaitingAck) {{
            setChatSendStatus(`${{replied ? "Reply sent direct" : "Sent direct"}} to ${{destination}} at ${{payload.sent_at || "now"}} (awaiting ACK)`);
          }} else {{
            setChatSendStatus(`${{replied ? "Reply sent direct" : "Sent direct"}} to ${{destination}} at ${{payload.sent_at || "now"}}`);
          }}
        }}
      }}
    }}

    async function sendChatReaction(replyId, emoji) {{
      const replyNum = Number(replyId);
      const cleanEmoji = String(emoji || "").trim();
      if (!Number.isInteger(replyNum) || replyNum <= 0) {{
        setChatSendStatus("Cannot react: target message id is missing.", true);
        return;
      }}
      if (!cleanEmoji) {{
        setChatSendStatus("Choose an emoji reaction.", true);
        return;
      }}
      let destination = "^all";
      if (activeChatChannel === "direct" && isSelectableNodeId(selectedNodeId)) {{
        destination = selectedNodeId;
      }}
      const payload = await sendChatPayload(
        {{
          destination,
          channel_index: 0,
          reply_id: replyNum,
          emoji: cleanEmoji,
        }},
        null
      );
      if (payload && payload.ok) {{
        setChatSendStatus(`Reacted ${{cleanEmoji}} at ${{payload.sent_at || "now"}}`);
      }}
    }}

    async function retryChatMessage(options) {{
      const text = String((options && options.text) || "").trim();
      if (!text) {{
        setChatSendStatus("Cannot retry: message text is empty.", true);
        return;
      }}

      let destination = String((options && options.destination) || "^all").trim() || "^all";
      if (destination.toLowerCase() === "all" || destination.toLowerCase() === "broadcast") {{
        destination = "^all";
      }}
      if (!(destination === "^all" || destination.startsWith("!"))) {{
        setChatSendStatus("Cannot retry: destination is invalid.", true);
        return;
      }}

      const channelRaw = Number(options && options.channel_index);
      const channelIndex = Number.isInteger(channelRaw) && channelRaw >= 0 ? channelRaw : 0;
      const replyRaw = Number(options && options.reply_id);
      const retryOfRaw = Number(options && options.retry_of);

      const body = {{
        text,
        destination,
        channel_index: channelIndex,
      }};
      if (Number.isInteger(replyRaw) && replyRaw > 0) {{
        body.reply_id = replyRaw;
      }}
      if (Number.isInteger(retryOfRaw) && retryOfRaw > 0) {{
        body.retry_of = retryOfRaw;
      }}

      const payload = await sendChatPayload(body, null);
      if (payload && payload.ok) {{
        const destLabel = destination === "^all" ? "Everyone" : destination;
        setChatSendStatus(`Retried to ${{destLabel}} at ${{payload.sent_at || "now"}}`);
      }}
    }}

    function openChatEmojiPanel(mode = "compose", reactionTargetId = null) {{
      const panel = document.getElementById("chat-emoji-panel");
      const btn = document.getElementById("chat-emoji-btn");
      if (!(panel instanceof HTMLElement)) return;
      chatEmojiMode = mode === "react" ? "react" : "compose";
      const parsedTarget = Number(reactionTargetId);
      chatReactionTargetId = (
        chatEmojiMode === "react" && Number.isInteger(parsedTarget) && parsedTarget > 0
      ) ? parsedTarget : null;
      panel.hidden = false;
      if (btn instanceof HTMLButtonElement) {{
        btn.setAttribute("aria-expanded", "true");
      }}
      if (chatEmojiMode === "react") {{
        setChatSendStatus("Pick a reaction emoji...");
      }}
    }}

    function closeChatEmojiPanel() {{
      const panel = document.getElementById("chat-emoji-panel");
      const btn = document.getElementById("chat-emoji-btn");
      chatEmojiMode = "compose";
      chatReactionTargetId = null;
      if (panel instanceof HTMLElement) {{
        panel.hidden = true;
      }}
      if (btn instanceof HTMLButtonElement) {{
        btn.setAttribute("aria-expanded", "false");
      }}
    }}

    function insertEmojiAtCursor(emoji) {{
      const input = document.getElementById("chat-input");
      if (!(input instanceof HTMLInputElement)) return;
      const value = input.value || "";
      const start = Number.isFinite(input.selectionStart) ? input.selectionStart : value.length;
      const end = Number.isFinite(input.selectionEnd) ? input.selectionEnd : value.length;
      input.value = value.slice(0, start) + emoji + value.slice(end);
      const next = start + emoji.length;
      input.focus({{ preventScroll: true }});
      input.setSelectionRange(next, next);
    }}

    function bindEmojiPicker() {{
      const panel = document.getElementById("chat-emoji-panel");
      const btn = document.getElementById("chat-emoji-btn");
      if (!(panel instanceof HTMLElement) || !(btn instanceof HTMLButtonElement)) return;

      if (panel.dataset.init !== "1") {{
        panel.innerHTML = `<div class="chat-emoji-grid">${{chatEmojiChoices.map((emoji) => (
          `<button type="button" class="chat-emoji-item" data-emoji="${{escAttr(emoji)}}" title="${{escAttr(emoji)}}">${{escAttr(emoji)}}</button>`
        )).join("")}}</div>`;
        panel.dataset.init = "1";
      }}

      if (btn.dataset.emojiBound !== "1") {{
        btn.dataset.emojiBound = "1";
        btn.addEventListener("click", (ev) => {{
          ev.preventDefault();
          if (chatSendInFlight) return;
          if (panel.hidden) {{
            openChatEmojiPanel("compose", null);
          }} else {{
            closeChatEmojiPanel();
          }}
        }});
      }}

      if (panel.dataset.bound !== "1") {{
        panel.dataset.bound = "1";
        panel.addEventListener("click", (ev) => {{
          const target = ev.target;
          if (!(target instanceof Element)) return;
          const emojiBtn = target.closest(".chat-emoji-item");
          if (!(emojiBtn instanceof HTMLButtonElement)) return;
          const emoji = String(emojiBtn.getAttribute("data-emoji") || emojiBtn.textContent || "").trim();
          if (!emoji) return;
          if (chatEmojiMode === "react" && Number.isInteger(chatReactionTargetId) && chatReactionTargetId > 0) {{
            sendChatReaction(chatReactionTargetId, emoji);
          }} else {{
            insertEmojiAtCursor(emoji);
          }}
          closeChatEmojiPanel();
        }});
      }}

      if (document.body.dataset.chatEmojiCloseBound !== "1") {{
        document.body.dataset.chatEmojiCloseBound = "1";
        document.addEventListener("pointerdown", (ev) => {{
          const target = ev.target;
          if (!(target instanceof Element)) return;
          if (!target.closest("#chat-emoji-panel") && !target.closest("#chat-emoji-btn")) {{
            closeChatEmojiPanel();
          }}
        }});
        document.addEventListener("keydown", (ev) => {{
          if (ev.key === "Escape") {{
            closeChatEmojiPanel();
          }}
        }});
      }}
    }}

    function bindChatComposer() {{
      const btn = document.getElementById("chat-send-btn");
      if (btn instanceof HTMLButtonElement && btn.dataset.bound !== "1") {{
        btn.dataset.bound = "1";
        btn.addEventListener("click", () => {{
          sendChatMessage();
        }});
      }}

      const input = document.getElementById("chat-input");
      if (input instanceof HTMLInputElement && input.dataset.bound !== "1") {{
        input.dataset.bound = "1";
        input.addEventListener("keydown", (ev) => {{
          if (ev.key === "Enter" && !ev.shiftKey) {{
            ev.preventDefault();
            sendChatMessage();
          }}
        }});
      }}

      const replyClearBtn = document.getElementById("chat-reply-clear-btn");
      if (replyClearBtn instanceof HTMLButtonElement && replyClearBtn.dataset.bound !== "1") {{
        replyClearBtn.dataset.bound = "1";
        replyClearBtn.addEventListener("click", () => {{
          clearChatReplyTarget();
        }});
      }}

      renderChatReplyContext();
      bindEmojiPicker();
    }}

    function nodeLabel(node) {{
      return node.long_name || node.short_name || node.id || "unknown";
    }}

    function preferredNodeName(node) {{
      if (!node || typeof node !== "object") return "";
      const longName = String(node.long_name || "").trim();
      if (longName) return longName;
      const shortName = String(node.short_name || "").trim();
      if (shortName) return shortName;
      return "";
    }}

    function markerStyle(isSelected) {{
      if (isSelected) {{
        return {{
          radius: 8,
          color: "#7a0f20",
          fillColor: "#ffd24a",
          fillOpacity: 0.95,
          weight: 2,
          bubblingMouseEvents: false
        }};
      }}
      return {{
        radius: 6,
        color: "#143d2a",
        fillColor: "#34c27f",
        fillOpacity: 0.85,
        weight: 1,
        bubblingMouseEvents: false
      }};
    }}

    function normalizeNodeId(nodeId) {{
      const raw = String(nodeId == null ? "" : nodeId).trim();
      if (!raw) return "";
      const lower = raw.toLowerCase();
      if (lower === "^all" || lower === "all" || lower === "broadcast") return "^all";
      if (lower === "unknown") return "Unknown";
      if (lower === "n/a" || lower === "na") return "n/a";
      if (lower === "local") return "local";

      const hex = raw.startsWith("!") ? raw.slice(1) : raw;
      if (/^[0-9a-f]{8}$/i.test(hex)) {{
        return `!${{hex.toLowerCase()}}`;
      }}
      return raw;
    }}

    function isSelectableNodeId(nodeId) {{
      const normalized = normalizeNodeId(nodeId);
      return !!normalized && normalized !== "^all" && normalized !== "Unknown" && normalized !== "n/a";
    }}

    function normalizeSearchQuery(value) {{
      return String(value == null ? "" : value).trim().toLowerCase();
    }}

    function matchesIdOrNameQuery(nodeId, nodeName, query) {{
      if (!query) return true;
      const idKey = normalizeSearchQuery(nodeId);
      const nameKey = normalizeSearchQuery(nodeName);
      return idKey.includes(query) || nameKey.includes(query);
    }}

    function loadFavoriteNodes() {{
      favoriteNodeIds.clear();
      try {{
        const raw = window.localStorage.getItem(favoritesStorageKey);
        if (!raw) return;
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return;
        for (const entry of parsed) {{
          const nodeId = normalizeNodeId(entry);
          if (isSelectableNodeId(nodeId)) {{
            favoriteNodeIds.add(nodeId);
          }}
        }}
      }} catch (_err) {{
      }}
    }}

    function persistFavoriteNodes() {{
      try {{
        const ids = Array.from(favoriteNodeIds).slice(0, 2000);
        window.localStorage.setItem(favoritesStorageKey, JSON.stringify(ids));
      }} catch (_err) {{
      }}
    }}

    function isFavoriteNode(nodeId) {{
      const normalized = normalizeNodeId(nodeId);
      return isSelectableNodeId(normalized) && favoriteNodeIds.has(normalized);
    }}

    function favoriteToggleButtonHtml(nodeId, extraClass = "") {{
      const normalized = normalizeNodeId(nodeId);
      if (!isSelectableNodeId(normalized)) return "";
      const active = favoriteNodeIds.has(normalized);
      const title = active ? "Remove from saved nodes" : "Save node";
      return `<button type="button" class="favorite-toggle-btn ${{extraClass}}${{active ? " active" : ""}}" data-node-id="${{escAttr(normalized)}}" title="${{title}}" aria-label="${{title}}" aria-pressed="${{active ? "true" : "false"}}"><span class="favorite-toggle-icon">${{active ? "★" : "☆"}}</span></button>`;
    }}

    function renderSavedRailStatus() {{
      const btn = document.querySelector('.teams-rail .rail-btn[data-view="saved"]');
      if (!(btn instanceof HTMLButtonElement)) return;
      if (!btn.dataset.baseTitle) {{
        btn.dataset.baseTitle = btn.getAttribute("title") || "Saved favorite nodes";
      }}
      const count = Math.max(0, favoriteNodeIds.size);
      const shown = count > 99 ? "99+" : String(count);
      btn.textContent = count > 0 ? `Saved (${{shown}})` : "Saved";
      const baseTitle = btn.dataset.baseTitle || "Saved favorite nodes";
      btn.title = count > 0
        ? `${{baseTitle}}. ${{count}} saved node${{count === 1 ? "" : "s"}}.`
        : baseTitle;
      btn.setAttribute("aria-label", btn.title);
    }}

    function refreshFavoriteToggleButtons() {{
      for (const btn of document.querySelectorAll(".favorite-toggle-btn")) {{
        if (!(btn instanceof HTMLButtonElement)) continue;
        const nodeId = normalizeNodeId(btn.dataset.nodeId || "");
        const active = isFavoriteNode(nodeId);
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-pressed", active ? "true" : "false");
        const title = active ? "Remove from saved nodes" : "Save node";
        btn.title = title;
        btn.setAttribute("aria-label", title);
        const icon = btn.querySelector(".favorite-toggle-icon");
        if (icon) {{
          icon.textContent = active ? "★" : "☆";
        }}
      }}
      renderSavedRailStatus();
    }}

    function toggleFavoriteNode(nodeId, forceActive = null) {{
      const normalized = normalizeNodeId(nodeId);
      if (!isSelectableNodeId(normalized)) return;
      const targetActive = forceActive == null ? !favoriteNodeIds.has(normalized) : !!forceActive;
      if (targetActive) {{
        favoriteNodeIds.add(normalized);
      }} else {{
        favoriteNodeIds.delete(normalized);
      }}
      persistFavoriteNodes();
      refreshFavoriteToggleButtons();
      if (latestState) {{
        renderFavorites(latestState);
      }}
    }}

    function loadStoredSelection() {{
      try {{
        const stored = window.localStorage.getItem(selectionStorageKey);
        const normalized = normalizeNodeId(stored);
        if (isSelectableNodeId(normalized)) {{
          selectedNodeId = normalized;
        }}
      }} catch (_err) {{
      }}
    }}

    function loadNodeNameCache() {{
      try {{
        const raw = window.localStorage.getItem(nodeNameCacheStorageKey);
        if (!raw) return;
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return;
        for (const entry of parsed) {{
          if (!Array.isArray(entry) || entry.length < 2) continue;
          const nodeId = normalizeNodeId(entry[0]);
          const name = String(entry[1] || "").trim();
          if (!isSelectableNodeId(nodeId) || !name) continue;
          nodeNameCache.set(nodeId, name);
        }}
      }} catch (_err) {{
      }}
    }}

    function persistNodeNameCache() {{
      try {{
        const entries = Array.from(nodeNameCache.entries()).slice(-2000);
        window.localStorage.setItem(nodeNameCacheStorageKey, JSON.stringify(entries));
      }} catch (_err) {{
      }}
    }}

    function updateNodeNameCache(nodes) {{
      let changed = false;
      for (const node of (nodes || [])) {{
        const nodeId = normalizeNodeId(node.id || "");
        if (!isSelectableNodeId(nodeId)) continue;
        const name = preferredNodeName(node);
        if (!name) continue;
        if (nodeNameCache.get(nodeId) !== name) {{
          nodeNameCache.set(nodeId, name);
          changed = true;
        }}
      }}
      if (changed) {{
        persistNodeNameCache();
      }}
    }}

    function persistSelection() {{
      try {{
        if (isSelectableNodeId(selectedNodeId)) {{
          window.localStorage.setItem(selectionStorageKey, normalizeNodeId(selectedNodeId));
        }} else {{
          window.localStorage.removeItem(selectionStorageKey);
        }}
      }} catch (_err) {{
      }}
    }}

    function renderSelectionStatus() {{
      const pill = document.getElementById("selected-node-pill");
      if (pill) {{
        pill.textContent = selectedNodeId ? `Selected: ${{selectedNodeId}}` : "Selected: none";
      }}
      const btn = document.getElementById("clear-selection-btn");
      if (btn) {{
        btn.disabled = !selectedNodeId;
      }}
    }}

    function escAttr(value) {{
      return String(value)
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }}

    function clampSplitPct(value) {{
      return Math.max(42, Math.min(78, value));
    }}

    function clampTopSplitPx(value) {{
      const max = Math.max(300, Math.min(760, window.innerHeight - 320));
      return Math.max(220, Math.min(max, value));
    }}

    function clampMidSplitPx(value) {{
      const max = Math.max(220, Math.min(620, window.innerHeight - 380));
      return Math.max(160, Math.min(max, value));
    }}

    function clampLowSplitPx(value) {{
      const max = Math.max(220, Math.min(560, window.innerHeight - 320));
      return Math.max(160, Math.min(max, value));
    }}

    function clampNetworkNodesListPct(value) {{
      return Math.max(28, Math.min(78, value));
    }}

    function applySplitState() {{
      const layout = document.querySelector(".layout");
      if (!(layout instanceof HTMLElement)) return;
      layout.style.setProperty("--split-left-pct", `${{splitPct}}%`);
      layout.style.setProperty("--split-top-px", `${{splitTopPx}}px`);
      layout.style.setProperty("--split-mid-px", `${{splitMidPx}}px`);
      layout.style.setProperty("--split-low-px", `${{splitLowPx}}px`);
    }}

    function applyNetworkNodesSplitState() {{
      const layout = document.getElementById("dashboard-layout");
      if (!(layout instanceof HTMLElement)) return;
      layout.style.setProperty("--network-nodes-list-pct", `${{networkNodesListPct}}%`);
    }}

    function loadSplitState() {{
      try {{
        const raw = window.localStorage.getItem(splitStorageKey) || "";
        if (raw) {{
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed === "object") {{
            if (Number.isFinite(parsed.col_pct)) {{
              splitPct = clampSplitPct(Number(parsed.col_pct));
            }}
            if (Number.isFinite(parsed.top_px)) {{
              splitTopPx = clampTopSplitPx(Number(parsed.top_px));
            }}
            if (Number.isFinite(parsed.mid_px)) {{
              splitMidPx = clampMidSplitPx(Number(parsed.mid_px));
            }}
            if (Number.isFinite(parsed.low_px)) {{
              splitLowPx = clampLowSplitPx(Number(parsed.low_px));
            }}
          }} else if (Number.isFinite(parsed)) {{
            splitPct = clampSplitPct(Number(parsed));
          }}
        }}
      }} catch (_err) {{
      }}
      applySplitState();
    }}

    function loadNetworkNodesSplitState() {{
      try {{
        const raw = window.localStorage.getItem(networkNodesSplitStorageKey) || "";
        if (raw) {{
          const parsed = Number(raw);
          if (Number.isFinite(parsed)) {{
            networkNodesListPct = clampNetworkNodesListPct(parsed);
          }}
        }}
      }} catch (_err) {{
      }}
      applyNetworkNodesSplitState();
    }}

    function persistNetworkNodesSplitState() {{
      try {{
        window.localStorage.setItem(networkNodesSplitStorageKey, String(networkNodesListPct));
      }} catch (_err) {{
      }}
    }}

    function chatMessageKey(msg) {{
      if (!msg || typeof msg !== "object") return "";
      const msgId = Number(msg.message_id ?? msg.messageId ?? msg.packet_id ?? msg.packetId);
      if (Number.isInteger(msgId) && msgId > 0) {{
        return `id:${{msgId}}`;
      }}
      const from = normalizeNodeId(msg.from || "");
      const to = normalizeNodeId(msg.to || "");
      const rx = String(msg.rx_time || msg.captured_at || "").trim();
      const text = String(msg.text || "");
      const channel = String(msg.channel ?? "");
      if (!from && !to && !rx && !text) {{
        return "";
      }}
      return `sig:${{from}}|${{to}}|${{rx}}|${{channel}}|${{text}}`;
    }}

    function rememberSeenChatMessage(key) {{
      if (!key || chatSeenMessageKeys.has(key)) return false;
      chatSeenMessageKeys.add(key);
      chatSeenMessageOrder.push(key);
      if (chatSeenMessageOrder.length > 6000) {{
        while (chatSeenMessageOrder.length > 4500) {{
          const stale = chatSeenMessageOrder.shift();
          if (stale) chatSeenMessageKeys.delete(stale);
        }}
      }}
      return true;
    }}

    function setChatChannelUnread(channelKey, count) {{
      const key = normalizeChatChannel(channelKey);
      const safe = Math.max(0, Math.min(999, Math.trunc(Number(count) || 0)));
      chatUnreadByChannel[key] = safe;
    }}

    function setChatChannelUnreadLatest(channelKey, name) {{
      const key = normalizeChatChannel(channelKey);
      const clean = String(name || "").replace(/\\s+/g, " ").trim();
      chatUnreadLatestByChannel[key] = clean;
    }}

    function totalChatUnread() {{
      return Math.max(0, Number(chatUnreadByChannel.all || 0))
        + Math.max(0, Number(chatUnreadByChannel.direct || 0));
    }}

    function syncChatRailUnread() {{
      chatUnreadCount = Math.min(999, totalChatUnread());
      setChatRailUnread(chatUnreadCount);
    }}

    function setChatRailUnread(count) {{
      const btn = document.querySelector('.teams-rail .rail-btn[data-view="chat"]');
      if (!(btn instanceof HTMLButtonElement)) return;
      if (!btn.dataset.baseTitle) {{
        btn.dataset.baseTitle = btn.getAttribute("title") || "Teams-style chat workspace";
      }}
      const safeCount = Math.max(0, Math.trunc(Number(count) || 0));
      const labelCount = safeCount > 99 ? "99+" : String(safeCount);
      btn.textContent = safeCount > 0 ? `Chat (${{labelCount}})` : "Chat";
      btn.classList.toggle("has-unread", safeCount > 0);
      const baseTitle = btn.dataset.baseTitle || "Teams-style chat workspace";
      btn.title = safeCount > 0
        ? `${{baseTitle}}. ${{safeCount}} unread message${{safeCount === 1 ? "" : "s"}}.`
        : baseTitle;
      btn.setAttribute("aria-label", btn.title);
    }}

    function clearChatUnread(channelKey = null) {{
      if (channelKey == null) {{
        setChatChannelUnread("all", 0);
        setChatChannelUnread("direct", 0);
        setChatChannelUnreadLatest("all", "");
        setChatChannelUnreadLatest("direct", "");
      }} else {{
        setChatChannelUnread(channelKey, 0);
        setChatChannelUnreadLatest(channelKey, "");
      }}
      syncChatRailUnread();
    }}

    function persistSplitState() {{
      try {{
        window.localStorage.setItem(
          splitStorageKey,
          JSON.stringify({{
            col_pct: splitPct,
            top_px: splitTopPx,
            mid_px: splitMidPx,
            low_px: splitLowPx,
          }})
        );
      }} catch (_err) {{
      }}
    }}

    function normalizeLayoutView(raw) {{
      const clean = String(raw || "").trim().toLowerCase();
      return knownLayoutViews.has(clean) ? clean : "chat";
    }}

    function syncNodeHistoryDock() {{
      const nodeHistoryPanel = document.getElementById("map-data-node");
      const mapDataBody = document.getElementById("map-data-body");
      const networkHost = document.getElementById("network-node-history-host");
      const nodesTitle = document.getElementById("nodes-card-title");
      if (!(nodeHistoryPanel instanceof HTMLElement)) return;
      if (!(mapDataBody instanceof HTMLElement)) return;
      if (!(networkHost instanceof HTMLElement)) return;

      const dockInNodes = activeLayoutView === "network";
      const target = dockInNodes ? networkHost : mapDataBody;
      if (nodeHistoryPanel.parentElement !== target) {{
        target.appendChild(nodeHistoryPanel);
      }}

      networkHost.hidden = !dockInNodes;
      networkHost.classList.toggle("empty", dockInNodes && nodeHistoryPanel.hidden);
      if (nodesTitle instanceof HTMLElement) {{
        nodesTitle.textContent = dockInNodes ? "Node Explorer" : "Nodes";
      }}
    }}

    function applyLayoutView(viewName, persist = true) {{
      const layout = document.getElementById("dashboard-layout");
      if (!(layout instanceof HTMLElement)) return;
      const shell = document.querySelector(".workspace-shell");
      const chatLeftPanel = document.getElementById("chat-left-panel");
      const next = normalizeLayoutView(viewName);
      activeLayoutView = next;
      for (const name of knownLayoutViews) {{
        layout.classList.remove(`view-${{name}}`);
      }}
      layout.classList.add(`view-${{next}}`);
      const chatPanelOpen = next === "chat";
      if (shell instanceof HTMLElement) {{
        shell.classList.toggle("chat-panel-open", chatPanelOpen);
      }}
      if (chatLeftPanel instanceof HTMLElement) {{
        chatLeftPanel.hidden = !chatPanelOpen;
      }}
      const mapTitle = document.getElementById("map-card-title");
      if (mapTitle) {{
        mapTitle.textContent = next === "saved"
          ? "Saved Node Details"
          : (isSelectableNodeId(selectedNodeId) ? "Selected Node Map" : "Network Map");
      }}
      setMapWheelZoomActive(next === "network" || next === "saved");
      if (chatPanelOpen) {{
        if (activeWheelPane instanceof HTMLElement) {{
          activeWheelPane.classList.remove("wheel-scroll-active");
        }}
        activeWheelPane = null;
        if (activeWheelPaneLease !== null) {{
          clearTimeout(activeWheelPaneLease);
          activeWheelPaneLease = null;
        }}
        clearChatUnread(activeChatChannel);
      }}
      syncChatRailUnread();
      if (typeof window.meshRefreshWheelHints === "function") {{
        window.meshRefreshWheelHints();
      }}

      for (const btn of document.querySelectorAll(".teams-rail .rail-btn")) {{
        if (!(btn instanceof HTMLButtonElement)) continue;
        const isActive = normalizeLayoutView(btn.dataset.view || "") === next;
        btn.classList.toggle("active", isActive);
        btn.setAttribute("aria-current", isActive ? "page" : "false");
      }}

      if (persist) {{
        try {{
          window.localStorage.setItem(layoutViewStorageKey, next);
        }} catch (_err) {{
        }}
      }}

      if (next === "network" && mapDataFocus === "activity") {{
        mapDataFocus = "auto";
      }}
      if (next === "network" && isSelectableNodeId(selectedNodeId)) {{
        pendingSelectionScroll = true;
        highlightNodeSelection();
        window.requestAnimationFrame(() => {{
          scrollSelectionIntoView();
        }});
      }}
      syncNodeHistoryDock();
      if (latestState) {{
        renderTraffic(latestState.traffic || {{}}, latestState.nodes || [], null, null);
        renderSavedNodeDetails(latestState, null);
      }}
      requestMapResize();
    }}

    function loadLayoutView() {{
      let preferred = "chat";
      try {{
        preferred = normalizeLayoutView(window.localStorage.getItem(layoutViewStorageKey) || "chat");
      }} catch (_err) {{
      }}
      applyLayoutView(preferred, false);
    }}

    function bindLayoutNav() {{
      for (const btn of document.querySelectorAll(".teams-rail .rail-btn")) {{
        if (!(btn instanceof HTMLButtonElement) || btn.dataset.bound === "1") continue;
        btn.dataset.bound = "1";
        btn.addEventListener("click", () => {{
          applyLayoutView(btn.dataset.view || "chat", true);
        }});
      }}
    }}

    function bindSplitters() {{
      const layout = document.querySelector(".layout");
      if (!(layout instanceof HTMLElement)) return;

      for (const splitter of document.querySelectorAll(".splitter, .hsplitter")) {{
        if (!(splitter instanceof HTMLElement) || splitter.dataset.bound === "1") continue;
        splitter.dataset.bound = "1";

        splitter.addEventListener("pointerdown", (ev) => {{
          if (window.matchMedia("(max-width: 1100px)").matches) return;
          ev.preventDefault();
          splitter.classList.add("active");
          const isHorizontal = splitter.classList.contains("hsplitter");
          document.body.classList.add(isHorizontal ? "resizing-panels-y" : "resizing-panels-x");
          splitter.setPointerCapture(ev.pointerId);
          const rect = layout.getBoundingClientRect();
          const startY = ev.clientY;
          const target = splitter.dataset.target || "";
          const startTop = splitTopPx;
          const startMid = splitMidPx;
          const startLow = splitLowPx;

          const onMove = (moveEv) => {{
            if (isHorizontal) {{
              const deltaY = moveEv.clientY - startY;
              if (target === "top") {{
                splitTopPx = clampTopSplitPx(startTop + deltaY);
              }} else if (target === "mid") {{
                splitMidPx = clampMidSplitPx(startMid + deltaY);
              }} else if (target === "low") {{
                if (activeLayoutView === "packets" || activeLayoutView === "data") {{
                  splitTopPx = clampTopSplitPx(startTop + deltaY);
                }} else {{
                  splitLowPx = clampLowSplitPx(startLow + deltaY);
                }}
              }}
            }} else {{
              const pct = clampSplitPct(((moveEv.clientX - rect.left) / rect.width) * 100);
              splitPct = pct;
            }}
            applySplitState();
            requestMapResize();
          }};

          const onUp = () => {{
            splitter.classList.remove("active");
            document.body.classList.remove("resizing-panels-x", "resizing-panels-y");
            persistSplitState();
            requestMapResize();
            splitter.removeEventListener("pointermove", onMove);
            splitter.removeEventListener("pointerup", onUp);
            splitter.removeEventListener("pointercancel", onUp);
          }};

          splitter.addEventListener("pointermove", onMove);
          splitter.addEventListener("pointerup", onUp);
          splitter.addEventListener("pointercancel", onUp);
        }});
      }}
    }}

    function bindNetworkNodeSplitter() {{
      const splitter = document.getElementById("network-node-splitter");
      if (!(splitter instanceof HTMLElement) || splitter.dataset.bound === "1") return;
      const stack = splitter.closest(".network-node-stack");
      if (!(stack instanceof HTMLElement)) return;
      splitter.dataset.bound = "1";

      splitter.addEventListener("pointerdown", (ev) => {{
        if (window.matchMedia("(max-width: 1100px)").matches) return;
        ev.preventDefault();
        splitter.classList.add("active");
        document.body.classList.add("resizing-panels-y");
        splitter.setPointerCapture(ev.pointerId);

        const tablePane = stack.querySelector(".nodes-table-scroll");
        if (!(tablePane instanceof HTMLElement)) {{
          splitter.classList.remove("active");
          document.body.classList.remove("resizing-panels-y");
          return;
        }}

        const updateFromClientY = (clientY) => {{
          const rect = stack.getBoundingClientRect();
          if (rect.height < 80) return;
          const relativeY = clientY - rect.top;
          const pct = clampNetworkNodesListPct((relativeY / rect.height) * 100);
          networkNodesListPct = pct;
          applyNetworkNodesSplitState();
        }};

        updateFromClientY(ev.clientY);

        const onMove = (moveEv) => {{
          updateFromClientY(moveEv.clientY);
        }};

        const onUp = () => {{
          splitter.classList.remove("active");
          document.body.classList.remove("resizing-panels-y");
          persistNetworkNodesSplitState();
          splitter.removeEventListener("pointermove", onMove);
          splitter.removeEventListener("pointerup", onUp);
          splitter.removeEventListener("pointercancel", onUp);
        }};

        splitter.addEventListener("pointermove", onMove);
        splitter.addEventListener("pointerup", onUp);
        splitter.addEventListener("pointercancel", onUp);
      }});
    }}

    function normalizeSortValue(raw) {{
      const text = String(raw == null ? "" : raw).trim();
      if (!text) return {{ kind: "empty", value: "" }};

      const numericText = text.replace(/,/g, "");
      if (/^-?\\d+(\\.\\d+)?$/.test(numericText)) {{
        return {{ kind: "num", value: Number.parseFloat(numericText) }};
      }}

      const epoch = Date.parse(text);
      if (!Number.isNaN(epoch)) {{
        return {{ kind: "date", value: epoch }};
      }}

      return {{ kind: "str", value: text.toLowerCase() }};
    }}

    function compareSortValues(a, b) {{
      const priority = {{ empty: 0, num: 1, date: 2, str: 3 }};
      if (a.kind !== b.kind) {{
        return (priority[a.kind] ?? 99) - (priority[b.kind] ?? 99);
      }}
      if (a.value < b.value) return -1;
      if (a.value > b.value) return 1;
      return 0;
    }}

    function cellSortRaw(cell) {{
      if (!cell) return "";
      return cell.getAttribute("data-sort") || cell.textContent || "";
    }}

    function updateSortIndicators(tableId) {{
      const table = document.getElementById(tableId);
      if (!(table instanceof HTMLTableElement)) return;
      const headers = Array.from(table.querySelectorAll("thead th"));
      headers.forEach((th) => {{
        th.classList.remove("sorted-asc", "sorted-desc");
      }});

      const state = tableSortState[tableId];
      if (!state) return;
      const target = headers[state.index];
      if (!target) return;
      target.classList.add(state.dir === "asc" ? "sorted-asc" : "sorted-desc");
    }}

    function bindSortableHeader(tableId) {{
      const table = document.getElementById(tableId);
      if (!(table instanceof HTMLTableElement) || table.dataset.sortBound === "1") return;
      table.dataset.sortBound = "1";

      const headers = Array.from(table.querySelectorAll("thead th"));
      headers.forEach((th, index) => {{
        th.classList.add("sortable");
        th.addEventListener("click", () => {{
          const state = tableSortState[tableId] || {{ index, dir: "asc" }};
          if (state.index === index) {{
            state.dir = state.dir === "asc" ? "desc" : "asc";
          }} else {{
            state.index = index;
            state.dir = index === 0 ? "desc" : "asc";
          }}
          tableSortState[tableId] = state;
          sortTableRows(tableId);
        }});
      }});

      updateSortIndicators(tableId);
    }}

    function sortTableRows(tableId) {{
      const table = document.getElementById(tableId);
      if (!(table instanceof HTMLTableElement)) return;
      const tbody = table.tBodies[0];
      if (!tbody) return;
      const state = tableSortState[tableId];
      if (!state) return;

      const rows = Array.from(tbody.rows);
      rows.sort((aRow, bRow) => {{
        const aCell = aRow.cells[state.index];
        const bCell = bRow.cells[state.index];
        const aValue = normalizeSortValue(cellSortRaw(aCell));
        const bValue = normalizeSortValue(cellSortRaw(bCell));
        const cmp = compareSortValues(aValue, bValue);
        return state.dir === "asc" ? cmp : -cmp;
      }});

      rows.forEach((row) => tbody.appendChild(row));
      updateSortIndicators(tableId);
    }}

    function packetConsoleKey(entry) {{
      const summary = entry.summary || {{}};
      let packetPart = "";
      try {{
        packetPart = JSON.stringify(entry.packet || {{}});
      }} catch (_err) {{
        packetPart = "";
      }}
      return [
        summary.captured_at || "",
        summary.from || "",
        summary.to || "",
        summary.portnum || "",
        summary.rx_time || "",
        String(summary.rx_snr ?? ""),
        String(summary.rx_rssi ?? ""),
        packetPart,
      ].join("|");
    }}

    function formatConsoleLine(entry) {{
      const s = entry.summary || {{}};
      const hops = (s.hop_start != null && s.hop_limit != null)
        ? Number(s.hop_start) - Number(s.hop_limit)
        : "n/a";
      const packetJson = (() => {{
        try {{
          return JSON.stringify(entry.packet || {{}});
        }} catch (_err) {{
          return "{{}}";
        }}
      }})();
      return `[${{s.captured_at || s.rx_time || "n/a"}}] ${{s.from || "n/a"}} -> ${{s.to || "n/a"}} port=${{s.portnum || "n/a"}} snr=${{s.rx_snr ?? "n/a"}} rssi=${{s.rx_rssi ?? "n/a"}} hops=${{hops}} ${{packetJson}}`;
    }}

    function appendConsoleLine(key, line) {{
      if (!key || consoleSeen.has(key)) return;
      consoleSeen.add(key);
      consoleKeyQueue.push(key);
      consoleLines.push(line);

      while (consoleLines.length > consoleMaxLines) {{
        consoleLines.shift();
        const oldKey = consoleKeyQueue.shift();
        if (oldKey) {{
          consoleSeen.delete(oldKey);
        }}
      }}
    }}

    function bindConsoleControls() {{
      const clearBtn = document.getElementById("console-clear-btn");
      if (clearBtn instanceof HTMLButtonElement && clearBtn.dataset.bound !== "1") {{
        clearBtn.dataset.bound = "1";
        clearBtn.addEventListener("click", () => {{
          consoleLines.length = 0;
          consoleKeyQueue.length = 0;
          consoleSeen.clear();
          const pre = document.getElementById("live-console");
          if (pre) {{
            pre.textContent = "";
          }}
        }});
      }}

      const auto = document.getElementById("console-autoscroll");
      if (auto instanceof HTMLInputElement && auto.dataset.bound !== "1") {{
        auto.dataset.bound = "1";
        consoleAutoscroll = auto.checked;
        auto.addEventListener("change", () => {{
          consoleAutoscroll = auto.checked;
        }});
      }}
    }}

    function renderConsole(traffic) {{
      const packets = traffic.recent_packets || [];
      for (const entry of packets) {{
        const key = packetConsoleKey(entry);
        appendConsoleLine(key, formatConsoleLine(entry));
      }}

      const pre = document.getElementById("live-console");
      if (!pre) return;
      pre.textContent = consoleLines.join("\\n");
      if (consoleAutoscroll) {{
        pre.scrollTop = pre.scrollHeight;
      }}
    }}

    function highlightNodeSelection() {{
      for (const row of document.querySelectorAll("#nodes-table tbody tr")) {{
        const nodeId = normalizeNodeId(row.dataset.nodeId || "");
        row.classList.toggle("selected-node", !!selectedNodeId && nodeId === selectedNodeId);
      }}
      for (const item of document.querySelectorAll("#chat-feed .chat-feed-item")) {{
        const nodeId = normalizeNodeId(item.dataset.nodeId || "");
        item.classList.toggle("selected-node", !!selectedNodeId && nodeId === selectedNodeId);
      }}
      for (const member of document.querySelectorAll("#chat-room-list .chat-member-item")) {{
        const nodeId = normalizeNodeId(member.dataset.nodeId || "");
        member.classList.toggle("selected-node", !!selectedNodeId && nodeId === selectedNodeId);
      }}
      for (const item of document.querySelectorAll("#favorites-list .favorite-node-item")) {{
        const nodeId = normalizeNodeId(item.dataset.nodeId || "");
        item.classList.toggle("selected-node", !!selectedNodeId && nodeId === selectedNodeId);
      }}
    }}

    function isVisibleForSelectionScroll(el) {{
      if (!(el instanceof HTMLElement)) return false;
      const rect = el.getBoundingClientRect();
      if (rect.width <= 2 || rect.height <= 2) return false;
      const style = window.getComputedStyle(el);
      if (!style || style.display === "none" || style.visibility === "hidden") return false;
      return true;
    }}

    function scrollSelectionIntoView() {{
      if (!selectedNodeId) {{
        pendingSelectionScroll = false;
        return;
      }}

      let didScroll = false;
      // Keep chat stable; selection auto-scroll only applies to the node list.
      for (const tableId of ["nodes-table"]) {{
        let targetRow = null;
        for (const row of document.querySelectorAll(`#${{tableId}} tbody tr`)) {{
          if (normalizeNodeId(row.dataset.nodeId || "") === selectedNodeId) {{
            targetRow = row;
            break;
          }}
        }}
        if (!targetRow) continue;

        const table = document.getElementById(tableId);
        const scroller = table ? table.closest(".scroll") : null;
        if (!isVisibleForSelectionScroll(scroller)) {{
          continue;
        }}

        const header = table ? table.querySelector("thead") : null;
        const headerHeight = header ? header.getBoundingClientRect().height : 0;
        const scrollerRect = scroller.getBoundingClientRect();
        const rowRect = targetRow.getBoundingClientRect();
        const topSafe = scrollerRect.top + headerHeight + 3;
        const bottomSafe = scrollerRect.bottom - 3;

        if (rowRect.top < topSafe) {{
          const delta = rowRect.top - topSafe;
          scroller.scrollTo({{ top: scroller.scrollTop + delta, behavior: "smooth" }});
        }} else if (rowRect.bottom > bottomSafe) {{
          const delta = rowRect.bottom - bottomSafe;
          scroller.scrollTo({{ top: scroller.scrollTop + delta, behavior: "smooth" }});
        }}
        didScroll = true;
      }}

      const favoritesList = document.getElementById("favorites-list");
      if (isVisibleForSelectionScroll(favoritesList)) {{
        let favoriteItem = null;
        for (const row of favoritesList.querySelectorAll(".favorite-node-item")) {{
          if (normalizeNodeId(row.dataset.nodeId || "") === selectedNodeId) {{
            favoriteItem = row;
            break;
          }}
        }}
        if (favoriteItem instanceof HTMLElement) {{
          const listRect = favoritesList.getBoundingClientRect();
          const rowRect = favoriteItem.getBoundingClientRect();
          const topSafe = listRect.top + 3;
          const bottomSafe = listRect.bottom - 3;
          if (rowRect.top < topSafe) {{
            const delta = rowRect.top - topSafe;
            favoritesList.scrollTo({{ top: favoritesList.scrollTop + delta, behavior: "smooth" }});
          }} else if (rowRect.bottom > bottomSafe) {{
            const delta = rowRect.bottom - bottomSafe;
            favoritesList.scrollTo({{ top: favoritesList.scrollTop + delta, behavior: "smooth" }});
          }}
          didScroll = true;
        }}
      }}

      pendingSelectionScroll = !didScroll;
    }}

    function updateMapSelection(shouldFocus = false) {{
      for (const [nodeId, marker] of nodeMarkers.entries()) {{
        marker.setStyle(markerStyle(!!selectedNodeId && nodeId === selectedNodeId));
      }}
      if (!shouldFocus || !selectedNodeId) return;
      const marker = nodeMarkers.get(selectedNodeId);
      if (!marker) return;
      map.panTo(marker.getLatLng(), {{ animate: true, duration: 0.35 }});
      marker.openPopup();
    }}

    function selectedNodeFrom(nodes) {{
      if (!selectedNodeId) return null;
      for (const node of (nodes || [])) {{
        if (normalizeNodeId(node.id || "") === selectedNodeId) {{
          return node;
        }}
      }}
      return null;
    }}

    function updateKnownNodesMetricState() {{
      const metric = document.getElementById("metric-known-nodes");
      if (!(metric instanceof HTMLElement)) return;
      const active = activeMapDataMode === "activity";
      metric.classList.toggle("active", active);
      metric.setAttribute("aria-pressed", active ? "true" : "false");
    }}

    function setMapDataMode(mode) {{
      const normalized = mode === "node" || mode === "activity" ? mode : "live";
      activeMapDataMode = normalized;
      const live = document.getElementById("map-data-live");
      const node = document.getElementById("map-data-node");
      const activity = document.getElementById("map-data-activity");
      const title = document.getElementById("map-data-title");
      const networkHost = document.getElementById("network-node-history-host");
      if (live) live.hidden = normalized !== "live";
      if (node) node.hidden = normalized !== "node";
      if (activity) activity.hidden = normalized !== "activity";
      if (networkHost instanceof HTMLElement) {{
        networkHost.classList.toggle("empty", normalized !== "node");
      }}
      if (title) {{
        title.textContent = normalized === "node"
          ? "Node History"
          : (normalized === "activity" ? "Online Activity" : "Map Data");
      }}
      updateKnownNodesMetricState();
    }}

    function toggleKnownNodesActivityMode() {{
      if (mapDataFocus === "activity") {{
        mapDataFocus = "auto";
        if (latestState) {{
          let cachedNodeHistory = null;
          if (isSelectableNodeId(selectedNodeId)) {{
            const cached = nodeHistoryCache.get(selectedNodeId);
            if (cached && cached.data) {{
              cachedNodeHistory = cached.data;
            }}
          }}
          renderTraffic(latestState.traffic || {{}}, latestState.nodes || [], cachedNodeHistory, null);
        }} else {{
          setMapDataMode("live");
        }}
        return;
      }}

      mapDataFocus = "activity";
      renderOnlineActivityLoading();
      fetchOnlineActivity(nodeHistoryHours)
        .then((data) => {{
          if (mapDataFocus !== "activity") return;
          renderOnlineActivity(data);
        }})
        .catch((err) => {{
          if (mapDataFocus !== "activity") return;
          renderOnlineActivityError(err instanceof Error ? err.message : String(err || "unknown error"));
        }});
    }}

    function bindKnownNodesMetricControl() {{
      const metric = document.getElementById("metric-known-nodes");
      if (!(metric instanceof HTMLElement) || metric.dataset.bound === "1") return;
      metric.dataset.bound = "1";
      metric.addEventListener("click", () => {{
        toggleKnownNodesActivityMode();
      }});
      metric.addEventListener("keydown", (ev) => {{
        if (ev.key !== "Enter" && ev.key !== " ") return;
        ev.preventDefault();
        toggleKnownNodesActivityMode();
      }});
      updateKnownNodesMetricState();
    }}

    function setHistoryTab(tabName) {{
      activeHistoryTab = tabName === "overview" ? "overview" : "signal";
      for (const btn of document.querySelectorAll(".history-tab-btn")) {{
        const isActive = btn.dataset.tab === activeHistoryTab;
        btn.classList.toggle("active", isActive);
      }}
      const signalPanel = document.getElementById("tab-panel-signal");
      const overviewPanel = document.getElementById("tab-panel-overview");
      if (signalPanel) signalPanel.hidden = activeHistoryTab !== "signal";
      if (overviewPanel) overviewPanel.hidden = activeHistoryTab !== "overview";
    }}

    function bindHistoryTabs() {{
      for (const btn of document.querySelectorAll(".history-tab-btn")) {{
        if (!(btn instanceof HTMLButtonElement) || btn.dataset.bound === "1") continue;
        btn.dataset.bound = "1";
        btn.addEventListener("click", () => {{
          setHistoryTab(btn.dataset.tab || "signal");
        }});
      }}
      setHistoryTab(activeHistoryTab);
    }}

    function renderNodeHistoryLoading(nodeId) {{
      setMapDataMode("node");
      const caption = document.getElementById("node-history-caption");
      if (caption) {{
        caption.textContent = `Loading history for ${{nodeId}}...`;
      }}
      const overview = document.getElementById("node-history-overview");
      if (overview) {{
        overview.innerHTML = "";
      }}
      const svg = document.getElementById("signal-chart");
      if (svg) {{
        svg.innerHTML = "";
      }}
      const empty = document.getElementById("signal-empty");
      if (empty) {{
        empty.hidden = false;
        empty.textContent = "Loading historical signal points...";
      }}
      setSignalTimelineMessage("Loading timeline...");
      renderSavedNodeDetails(latestState || {{}}, null, nodeId);
    }}

    function selectNode(nodeId, shouldFocus = true, toggleIfSelected = true) {{
      const normalized = normalizeNodeId(nodeId);
      if (!isSelectableNodeId(normalized)) return;
      if (toggleIfSelected && selectedNodeId && normalized === selectedNodeId) {{
        clearNodeSelection();
        return;
      }}
      selectedNodeId = normalized;
      mapDataFocus = "auto";
      pendingSelectionScroll = true;
      persistSelection();
      renderSelectionStatus();
      highlightNodeSelection();
      updateMapSelection(shouldFocus);
      scrollSelectionIntoView();
      renderNodeHistoryLoading(selectedNodeId);
      if (latestState) {{
        let cachedNodeHistory = null;
        if (isSelectableNodeId(selectedNodeId)) {{
          const cached = nodeHistoryCache.get(selectedNodeId);
          if (cached && cached.data) {{
            cachedNodeHistory = cached.data;
          }}
        }}
        renderMap(latestState.nodes || [], (latestState.traffic || {{}}).edges || [], cachedNodeHistory);
      }}
      applyChatChannel(activeChatChannel, false);
    }}

    function clearNodeSelection() {{
      selectedNodeId = null;
      pendingSelectionScroll = false;
      persistSelection();
      renderSelectionStatus();
      highlightNodeSelection();
      updateMapSelection(false);
      map.closePopup();
      setMapDataMode(mapDataFocus === "activity" ? "activity" : "live");
      if (latestState) {{
        renderMap(latestState.nodes || [], (latestState.traffic || {{}}).edges || [], null);
        renderTraffic(latestState.traffic || {{}}, latestState.nodes || [], null, null);
        renderSavedNodeDetails(latestState, null);
      }} else {{
        renderSavedNodeDetails({{}}, null);
      }}
      applyChatChannel(activeChatChannel, false);
    }}

    function bindNodeRowClicks() {{
      for (const row of document.querySelectorAll("#nodes-table tbody tr.node-selectable")) {{
        row.addEventListener("click", () => {{
          selectNode(row.dataset.nodeId || "", true);
        }});
      }}
    }}

    function bindChatFeedClicks() {{
      for (const item of document.querySelectorAll("#chat-feed .chat-feed-item")) {{
        if (!(item instanceof HTMLElement)) continue;
        item.addEventListener("click", (ev) => {{
          const target = ev.target;
          if (target instanceof Element && target.closest(".chat-reply-trigger, .chat-reply-btn")) {{
            ev.preventDefault();
            ev.stopPropagation();
            const replyId = Number(item.dataset.messageId || "");
            const replyName = item.dataset.replyName || "Unknown node";
            const replyText = item.dataset.replyText || "";
            if (activeChatChannel === "direct" && item.classList.contains("chat-selectable")) {{
              selectNode(item.dataset.nodeId || "", false, false);
            }}
            setChatReplyTarget(replyId, replyName, replyText);
            return;
          }}
          if (item.classList.contains("chat-selectable")) {{
            selectNode(item.dataset.nodeId || "", true);
          }}
        }});
      }}
    }}

    function bindChatReactionControls() {{
      bindReactionPopover();
      for (const btn of document.querySelectorAll("#chat-feed .chat-react-btn")) {{
        if (!(btn instanceof HTMLButtonElement)) continue;
        btn.addEventListener("click", (ev) => {{
          ev.preventDefault();
          ev.stopPropagation();
          if (chatSendInFlight) return;
          const replyId = Number(btn.dataset.replyId || "");
          if (!Number.isInteger(replyId) || replyId <= 0) {{
            setChatSendStatus("Cannot react: target message id is missing.", true);
            return;
          }}
          openChatEmojiPanel("react", replyId);
        }});
      }}

      for (const chip of document.querySelectorAll("#chat-feed .chat-reaction-chip")) {{
        if (!(chip instanceof HTMLButtonElement)) continue;
        chip.addEventListener("pointerenter", () => {{
          clearReactionPopoverHideTimer();
          openReactionPopoverForChip(chip);
        }});
        chip.addEventListener("pointerleave", (ev) => {{
          const related = ev.relatedTarget;
          const popover = reactionPopoverElement();
          if (
            related instanceof Node
            && popover instanceof HTMLElement
            && popover.contains(related)
          ) {{
            return;
          }}
          scheduleReactionPopoverHide(120);
        }});
        chip.addEventListener("focus", () => {{
          clearReactionPopoverHideTimer();
          openReactionPopoverForChip(chip);
        }});
        chip.addEventListener("blur", () => {{
          scheduleReactionPopoverHide(80);
        }});
        chip.addEventListener("click", (ev) => {{
          ev.preventDefault();
          ev.stopPropagation();
          clearReactionPopoverHideTimer();
          openReactionPopoverForChip(chip);
          if (chatSendInFlight) return;
          const replyId = Number(chip.dataset.replyId || "");
          const emoji = String(chip.dataset.emoji || "").trim();
          if (!Number.isInteger(replyId) || replyId <= 0 || !emoji) return;
          sendChatReaction(replyId, emoji);
        }});
      }}
    }}

    function bindChatRetryControls() {{
      for (const btn of document.querySelectorAll("#chat-feed .chat-retry-btn")) {{
        if (!(btn instanceof HTMLButtonElement)) continue;
        btn.addEventListener("click", (ev) => {{
          ev.preventDefault();
          ev.stopPropagation();
          if (chatSendInFlight) return;
          retryChatMessage({{
            text: btn.dataset.retryText || "",
            destination: btn.dataset.retryDestination || "^all",
            channel_index: Number(btn.dataset.retryChannel || "0"),
            reply_id: Number(btn.dataset.retryReplyId || ""),
            retry_of: Number(btn.dataset.retryOf || ""),
          }});
        }});
      }}
    }}

    function bindSelectionControls() {{
      const btn = document.getElementById("clear-selection-btn");
      if (!btn || btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => {{
        clearNodeSelection();
      }});
    }}

    function bindFavoriteToggleControls() {{
      if (document.body.dataset.favoritesBound === "1") return;
      document.body.dataset.favoritesBound = "1";
      document.addEventListener("click", (ev) => {{
        const target = ev.target;
        if (!(target instanceof Element)) return;
        const btn = target.closest(".favorite-toggle-btn");
        if (!(btn instanceof HTMLButtonElement)) return;
        ev.preventDefault();
        ev.stopPropagation();
        toggleFavoriteNode(btn.dataset.nodeId || "");
      }}, true);
    }}

    function bindFavoritesControls() {{
      const searchInput = document.getElementById("favorites-search-input");
      if (searchInput instanceof HTMLInputElement) {{
        if (searchInput.dataset.bound !== "1") {{
          searchInput.dataset.bound = "1";
          searchInput.addEventListener("input", () => {{
            favoritesSearchQuery = normalizeSearchQuery(searchInput.value);
            if (latestState) {{
              renderFavorites(latestState);
            }}
          }});
        }}
        searchInput.value = favoritesSearchQuery;
      }}

      const clearBtn = document.getElementById("favorites-clear-btn");
      if (clearBtn instanceof HTMLButtonElement && clearBtn.dataset.bound !== "1") {{
        clearBtn.dataset.bound = "1";
        clearBtn.addEventListener("click", () => {{
          if (favoriteNodeIds.size === 0) return;
          if (!window.confirm("Remove all saved nodes?")) return;
          favoriteNodeIds.clear();
          persistFavoriteNodes();
          refreshFavoriteToggleButtons();
          if (latestState) {{
            renderFavorites(latestState);
          }}
        }});
      }}
    }}

    function bindNodeListSearchControls() {{
      const nodesInput = document.getElementById("nodes-search-input");
      if (nodesInput instanceof HTMLInputElement) {{
        if (nodesInput.dataset.bound !== "1") {{
          nodesInput.dataset.bound = "1";
          nodesInput.addEventListener("input", () => {{
            nodesSearchQuery = normalizeSearchQuery(nodesInput.value);
            if (latestState) {{
              renderNodes(latestState.nodes || []);
            }}
          }});
        }}
        nodesInput.value = nodesSearchQuery;
      }}

      const chatInput = document.getElementById("chat-user-search-input");
      if (chatInput instanceof HTMLInputElement) {{
        if (chatInput.dataset.bound !== "1") {{
          chatInput.dataset.bound = "1";
          chatInput.addEventListener("input", () => {{
            chatUserSearchQuery = normalizeSearchQuery(chatInput.value);
            if (latestState) {{
              renderChat(latestState);
            }}
          }});
        }}
        chatInput.value = chatUserSearchQuery;
      }}
    }}

    map.on("click", () => {{
      if (mapWheelJustArmed) {{
        mapWheelJustArmed = false;
        return;
      }}
      clearNodeSelection();
    }});

    function renderSummary(state) {{
      const s = state.summary || {{}};
      setText("m-target", s.target || "n/a");
      setText("m-nodes", s.node_count ?? 0);
      setText("m-pos-nodes", s.nodes_with_position ?? 0);
      setText("m-live-packets", s.live_packet_count ?? 0);
      const realLinks = s.real_edge_count ?? s.edge_count ?? 0;
      setText("m-links", realLinks);
      setText("m-modem-preset", s.modem_preset || "n/a");
      setText("m-uptime", s.uptime_seconds ?? 0);
      setText("updated-at", state.generated_at || "n/a");
      const err = document.getElementById("local-state-error");
      if (err) {{
        err.textContent = state.local_state_error ? `  Local state error: ${{state.local_state_error}}` : "";
      }}

      const revision = s.revision || {{}};
      const revisionText = document.getElementById("revision-text");
      if (revisionText) {{
        const fallbackLabel = String(revision.label || "").trim();
        const version = String(revision.version || "").trim();
        const commit = String(revision.commit || "").trim();
        if (fallbackLabel) {{
          revisionText.textContent = fallbackLabel;
        }} else if (version || commit) {{
          const versionText = version ? `v${{version}}` : "unknown";
          const commitText = commit || "nogit";
          revisionText.textContent = `Rev: ${{versionText}} (${{commitText}})`;
        }}
        const title = String(revision.title || "").trim();
        if (title) {{
          revisionText.title = title;
        }}
      }}

      const disk = s.disk || {{}};
      const diskLabel = document.getElementById("disk-label");
      const diskFill = document.getElementById("disk-fill");
      const diskMeter = document.getElementById("disk-meter");
      const freePctRaw = Number(disk.free_pct);
      if (!Number.isFinite(freePctRaw)) {{
        if (diskLabel) {{
          diskLabel.textContent = "Disk free: n/a";
        }}
        if (diskFill) {{
          diskFill.style.width = "0%";
          diskFill.classList.remove("warn", "danger");
        }}
        if (diskMeter) {{
          const detail = disk.error ? ` (${{disk.error}})` : "";
          diskMeter.title = `Disk free on dashboard host${{detail}}`;
        }}
        return;
      }}

      const freePct = Math.max(0, Math.min(100, freePctRaw));
      if (diskLabel) {{
        diskLabel.textContent = `Disk free: ${{freePct.toFixed(1)}}%`;
      }}
      if (diskFill) {{
        diskFill.style.width = `${{freePct.toFixed(1)}}%`;
        diskFill.classList.remove("warn", "danger");
        if (freePct < 15) {{
          diskFill.classList.add("danger");
        }} else if (freePct < 30) {{
          diskFill.classList.add("warn");
        }}
      }}
      if (diskMeter) {{
        const freeGiB = bytesToGiB(disk.free_bytes);
        const totalGiB = bytesToGiB(disk.total_bytes);
        const freeText = freeGiB == null ? "n/a" : freeGiB.toFixed(1);
        const totalText = totalGiB == null ? "n/a" : totalGiB.toFixed(1);
        diskMeter.title = `Disk free on dashboard host (${{freeText}} GiB / ${{totalText}} GiB, path: ${{disk.path || "n/a"}})`;
      }}
    }}

    function buildMapSignature(nodes, edges, nodeHistory) {{
      const selection = isSelectableNodeId(selectedNodeId) ? normalizeNodeId(selectedNodeId) : "";
      if (selection) {{
        let trailSig = "no-trail";
        const historyNodeId = normalizeNodeId((nodeHistory && nodeHistory.node_id) || "");
        if (historyNodeId && historyNodeId === selection) {{
          const rawTrail = Array.isArray(nodeHistory.positions) ? nodeHistory.positions : [];
          const compact = [];
          for (const point of rawTrail) {{
            const lat = Number(point && point.lat);
            const lon = Number(point && point.lon);
            if (!Number.isFinite(lat) || !Number.isFinite(lon)) continue;
            const when = Number(point && point.time_unix);
            const ts = Number.isFinite(when) ? String(Math.round(when)) : "";
            compact.push(`${{lat.toFixed(5)}},${{lon.toFixed(5)}}@${{ts}}`);
          }}
          trailSig = compact.join("|");
        }}
        const selectedNode = selectedNodeFrom(nodes);
        if (
          selectedNode &&
          typeof selectedNode.lat === "number" &&
          typeof selectedNode.lon === "number"
        ) {{
          return `sel:${{selection}}:${{selectedNode.lat.toFixed(5)}},${{selectedNode.lon.toFixed(5)}}:trail:${{trailSig}}`;
        }}
        return `sel:${{selection}}:no-position:trail:${{trailSig}}`;
      }}
      const nodeSig = (nodes || [])
        .filter((node) => typeof node.lat === "number" && typeof node.lon === "number")
        .map((node) => `${{normalizeNodeId(node.id)}}:${{node.lat.toFixed(5)}},${{node.lon.toFixed(5)}}`)
        .join("|");
      const edgeSig = (edges || [])
        .map((edge) => `${{normalizeNodeId(edge.from)}}>${{normalizeNodeId(edge.to)}}:${{edge.lifetime_count ?? edge.count ?? 0}}:${{edge.last_rx_time || ""}}:${{edge.last_hops ?? ""}}`)
        .join("|");
      return `all#${{nodeSig}}#${{edgeSig}}`;
    }}

    function renderMap(nodes, edges, nodeHistory = null) {{
      const signature = buildMapSignature(nodes, edges, nodeHistory);
      if (signature === lastMapSignature) {{
        updateMapSelection(false);
        return;
      }}
      lastMapSignature = signature;

      nodeLayer.clearLayers();
      edgeLayer.clearLayers();
      trailLayer.clearLayers();
      nodeMarkers.clear();
      const features = [];
      const byId = Object.fromEntries(nodes.map((n) => [normalizeNodeId(n.id), n]));
      const selectionMode = isSelectableNodeId(selectedNodeId);
      const mapTitle = document.getElementById("map-card-title");
      if (mapTitle) {{
        if (activeLayoutView === "saved") {{
          mapTitle.textContent = "Saved Node Details";
        }} else {{
          mapTitle.textContent = selectionMode ? "Selected Node Map" : "Network Map";
        }}
      }}

      if (selectionMode) {{
        const selectedNode = selectedNodeFrom(nodes);
        const selectionId = normalizeNodeId(selectedNodeId || "");
        const selectedNodeIdNormalized = normalizeNodeId((selectedNode && selectedNode.id) || "");
        const hasSelectedPosition = !!selectedNode
          && typeof selectedNode.lat === "number"
          && typeof selectedNode.lon === "number";
        const canUseHistory = !!nodeHistory
          && normalizeNodeId((nodeHistory && nodeHistory.node_id) || "") === selectionId;
        const rawTrail = canUseHistory && Array.isArray(nodeHistory.positions)
          ? nodeHistory.positions
          : [];
        const trailPoints = rawTrail
          .map((point) => {{
            const lat = Number(point && point.lat);
            const lon = Number(point && point.lon);
            const timeUnix = Number(point && point.time_unix);
            if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
            return {{
              lat,
              lon,
              time_unix: Number.isFinite(timeUnix) ? Math.round(timeUnix) : null,
              time: point && point.time ? String(point.time) : null,
            }};
          }})
          .filter((point) => point !== null);

        if (trailPoints.length >= 2) {{
          const line = L.polyline(
            trailPoints.map((point) => [point.lat, point.lon]),
            {{
              color: "#d06a1b",
              opacity: 0.78,
              weight: 4,
              lineCap: "round",
              lineJoin: "round",
            }}
          );
          line.bindTooltip(`Location trail (${{trailPoints.length}} points)`, {{ sticky: true, opacity: 0.9 }});
          line.addTo(trailLayer);
          features.push(line);
        }}
        if (trailPoints.length > 0) {{
          const endPoint = trailPoints[trailPoints.length - 1];
          for (let i = 0; i < trailPoints.length; i += 1) {{
            const point = trailPoints[i];
            const isLatestPoint = i === (trailPoints.length - 1);
            const ratio = trailPoints.length <= 1 ? 1 : (i / (trailPoints.length - 1));
            const marker = L.circleMarker([point.lat, point.lon], {{
              radius: isLatestPoint ? 5.8 : (i === 0 ? 3.6 : 2.6),
              color: isLatestPoint ? "#f97316" : "#2f855a",
              fillColor: isLatestPoint ? "#f97316" : "#63d297",
              fillOpacity: isLatestPoint ? 0.96 : (0.2 + (ratio * 0.5)),
              weight: isLatestPoint ? 2 : 1,
              bubblingMouseEvents: false,
            }});
            const pointTime = point.time || "n/a";
            marker.bindTooltip(
              isLatestPoint
                ? `Newest trail point: ${{pointTime}}`
                : `Trail point ${{i + 1}}/${{trailPoints.length}}: ${{pointTime}}`,
              {{ sticky: true, opacity: 0.88 }}
            );
            marker.addTo(trailLayer);
            features.push(marker);
          }}

          const latestHalo = L.circleMarker([endPoint.lat, endPoint.lon], {{
            radius: 10,
            color: "#f97316",
            fillColor: "#f97316",
            fillOpacity: 0.16,
            weight: 2,
            bubblingMouseEvents: false,
          }});
          latestHalo.bindTooltip(`Newest trail point: ${{endPoint.time || "n/a"}}`, {{ sticky: true, opacity: 0.9 }});
          latestHalo.addTo(trailLayer);
          features.push(latestHalo);
        }}

        if (hasSelectedPosition) {{
          const trailPointsCount = trailPoints.length;
          const trailLast = trailPointsCount > 0
            ? (trailPoints[trailPointsCount - 1].time || "n/a")
            : "n/a";
          const marker = L.circleMarker(
            [selectedNode.lat, selectedNode.lon],
            markerStyle(true)
          );
          marker.bindPopup(`
            <b>${{nodeLabel(selectedNode)}}</b><br/>
            ${{selectedNodeIdNormalized || selectedNode.id}}<br/>
            Num: ${{selectedNode.num ?? "n/a"}}<br/>
            SNR: ${{selectedNode.snr ?? "n/a"}}<br/>
            Last: ${{selectedNode.last_heard || "n/a"}}<br/>
            Trail points: ${{trailPointsCount}}<br/>
            Trail latest: ${{trailLast}}
          `);
          marker.on("click", () => {{
            selectNode(normalizeNodeId(selectedNode.id || ""), false);
          }});
          marker.addTo(nodeLayer);
          nodeMarkers.set(normalizeNodeId(selectedNode.id || ""), marker);
          features.push(marker);
          if (trailPoints.length > 1) {{
            const trailBounds = L.latLngBounds(trailPoints.map((point) => [point.lat, point.lon]));
            trailBounds.extend([selectedNode.lat, selectedNode.lon]);
            if (trailBounds.isValid()) {{
              map.fitBounds(trailBounds.pad(0.2), {{ animate: false, maxZoom: 16 }});
            }}
          }} else {{
            map.setView([selectedNode.lat, selectedNode.lon], Math.max(map.getZoom(), 11), {{ animate: false }});
          }}
          marker.openPopup();
        }} else if (trailPoints.length > 0) {{
          const trailBounds = L.latLngBounds(trailPoints.map((point) => [point.lat, point.lon]));
          if (trailBounds.isValid()) {{
            map.fitBounds(trailBounds.pad(0.2), {{ animate: false, maxZoom: 16 }});
          }}
        }} else {{
          map.closePopup();
        }}
        requestMapResize();
        return;
      }}

      for (const node of nodes) {{
        if (typeof node.lat !== "number" || typeof node.lon !== "number") continue;
        const normalizedId = normalizeNodeId(node.id || "");
        const isSelected = !!selectedNodeId && normalizedId === selectedNodeId;
        const marker = L.circleMarker([node.lat, node.lon], markerStyle(isSelected));
        marker.bindPopup(`
          <b>${{nodeLabel(node)}}</b><br/>
          ${{normalizedId || node.id}}<br/>
          Num: ${{node.num ?? "n/a"}}<br/>
          SNR: ${{node.snr ?? "n/a"}}<br/>
          Last: ${{node.last_heard || "n/a"}}
        `);
        marker.on("click", () => {{
          selectNode(normalizedId, false);
        }});
        marker.addTo(nodeLayer);
        nodeMarkers.set(normalizedId, marker);
        features.push(marker);
      }}

      for (const edge of edges) {{
        const src = byId[normalizeNodeId(edge.from)];
        const dst = byId[normalizeNodeId(edge.to)];
        if (!src || !dst) continue;
        if (typeof src.lat !== "number" || typeof src.lon !== "number") continue;
        if (typeof dst.lat !== "number" || typeof dst.lon !== "number") continue;
        const lifetimeCount = edge.lifetime_count ?? edge.count ?? 0;
        const sessionCount = edge.session_count ?? edge.count ?? 0;
        const isReal = !!edge.is_real;
        const hopsLabel = edge.avg_hops == null
          ? "n/a"
          : `avg ${{edge.avg_hops}}${{edge.last_hops == null ? "" : ` (last ${{edge.last_hops}})`}}`;
        const line = L.polyline([[src.lat, src.lon], [dst.lat, dst.lon]], {{
          color: isReal ? "#bf1f43" : "#b7791f",
          dashArray: isReal ? null : "6 6",
          opacity: isReal ? 0.74 : 0.52,
          weight: Math.min(8, 2 + lifetimeCount),
          bubblingMouseEvents: false,
        }});
        line.bindTooltip(`
          <b>${{edge.from}} -> ${{edge.to}}</b><br/>
          Status: ${{edge.confidence || (isReal ? "confirmed" : "observed")}}<br/>
          Packets: ${{lifetimeCount}}<br/>
          Hops: ${{hopsLabel}}
        `, {{ sticky: true, opacity: 0.92 }});
        line.bindPopup(`
          <b>${{edge.from}} -> ${{edge.to}}</b><br/>
          Status: ${{edge.confidence || (isReal ? "confirmed" : "observed")}}<br/>
          Session packets: ${{sessionCount}}<br/>
          Lifetime packets: ${{lifetimeCount}}<br/>
          First: ${{edge.first_rx_time || "n/a"}}<br/>
          Last: ${{edge.last_rx_time || "n/a"}}<br/>
          Hops: ${{hopsLabel}}<br/>
          Ports: ${{(edge.portnums || []).join(", ") || "n/a"}}
        `);
        line.addTo(edgeLayer);
        features.push(line);
      }}

      if (!fitDone && features.length > 0) {{
        map.fitBounds(L.featureGroup(features).getBounds().pad(0.2));
        fitDone = true;
        requestMapResize();
      }}
      updateMapSelection(false);
    }}

    function fillTable(tableId, rowsHtml) {{
      const tbody = document.querySelector(`#${{tableId}} tbody`);
      if (!tbody) return;
      tbody.innerHTML = rowsHtml.join("");
      if (sortableTables.has(tableId)) {{
        bindSortableHeader(tableId);
        sortTableRows(tableId);
      }}
    }}

    function renderNodes(nodes) {{
      const query = normalizeSearchQuery(nodesSearchQuery);
      const filteredNodes = (nodes || []).filter((node) => {{
        const nodeId = normalizeNodeId(node.id || "");
        const name = nodeLabel(node);
        return matchesIdOrNameQuery(nodeId, name, query);
      }});

      const rows = filteredNodes.map((node) => {{
          const nodeId = normalizeNodeId(node.id || "");
          const selectable = isSelectableNodeId(nodeId);
          const pos = (typeof node.lat === "number" && typeof node.lon === "number")
            ? `${{node.lat.toFixed(5)}}, ${{node.lon.toFixed(5)}}`
            : "n/a";
          const name = nodeLabel(node);
          const savedPackets = Number.isFinite(Number(node.saved_packets))
            ? Number(node.saved_packets)
            : 0;
          const savedPoints = Number.isFinite(Number(node.saved_points))
            ? Number(node.saved_points)
            : 0;
          const savedTitle = savedPoints > 0
            ? `${{savedPackets}} packets across ${{savedPoints}} minute buckets`
            : "No saved history yet";
          return `<tr data-node-id="${{escAttr(nodeId)}}" class="${{selectable ? "node-selectable" : ""}}">
          <td data-sort="${{escAttr(node.last_heard ?? "")}}">${{node.last_heard ?? "n/a"}}</td>
          <td class="mono" data-sort="${{escAttr(nodeId)}}" title="${{escAttr(String(node.id || nodeId || ""))}}">${{nodeId || "n/a"}}</td>
          <td data-sort="${{escAttr(name)}}">
            <span class="node-name-row">
              <span class="node-name-label">${{name}}</span>
            </span>
          </td>
          <td data-sort="${{escAttr(node.hardware_model ?? "")}}">${{node.hardware_model ?? "n/a"}}</td>
          <td data-sort="${{escAttr(node.snr ?? "")}}">${{node.snr ?? "n/a"}}</td>
          <td data-sort="${{escAttr(node.hops_away ?? "")}}">${{node.hops_away ?? "n/a"}}</td>
          <td data-sort="${{escAttr(node.battery_level ?? "")}}">${{node.battery_level ?? "n/a"}}</td>
          <td data-sort="${{escAttr(savedPackets)}}" title="${{escAttr(savedTitle)}}">${{savedPackets}}</td>
          <td data-sort="${{escAttr(pos)}}">${{pos}}</td>
          <td data-sort="${{escAttr(isFavoriteNode(nodeId) ? 1 : 0)}}">${{favoriteToggleButtonHtml(nodeId, "node-favorite-btn")}}</td>
        </tr>`;
      }});
      if (rows.length === 0) {{
        rows.push('<tr><td colspan="10">No nodes match this search.</td></tr>');
      }}
      fillTable("nodes-table", rows);
      bindNodeRowClicks();
      highlightNodeSelection();
      if (pendingSelectionScroll) {{
        scrollSelectionIntoView();
      }}
    }}

    function savedDetailText(value, fallback = "n/a") {{
      const text = String(value == null ? "" : value).trim();
      if (text) return text;
      return String(fallback == null ? "n/a" : fallback);
    }}

    function savedDetailPercent(value, decimals = 1) {{
      const num = Number(value);
      if (!Number.isFinite(num)) return "n/a";
      return `${{num.toFixed(decimals)}}%`;
    }}

    function savedDetailCoord(lat, lon) {{
      const latNum = Number(lat);
      const lonNum = Number(lon);
      if (!Number.isFinite(latNum) || !Number.isFinite(lonNum)) return "n/a";
      return `${{latNum.toFixed(5)}}, ${{lonNum.toFixed(5)}}`;
    }}

    function savedDetailDurationHours(startUnix, endUnix) {{
      const start = Number(startUnix);
      const end = Number(endUnix);
      if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return "n/a";
      const hours = (end - start) / 3600;
      return `${{hours.toFixed(1)}}h`;
    }}

    function savedDetailSectionHtml(title, items, note = "") {{
      const rows = items.map(([label, value]) => (
        `<div class="saved-node-stat">
          <div class="saved-node-stat-k">${{escAttr(label)}}</div>
          <div class="saved-node-stat-v">${{escAttr(savedDetailText(value))}}</div>
        </div>`
      )).join("");
      const noteHtml = note
        ? `<div class="saved-node-note">${{escAttr(note)}}</div>`
        : "";
      return `<section class="saved-node-section">
        <h3 class="saved-node-section-title">${{escAttr(title)}}</h3>
        <div class="saved-node-grid">${{rows}}</div>
        ${{noteHtml}}
      </section>`;
    }}

    function computeSavedChatStats(nodeId, messages) {{
      const stats = {{
        touches: 0,
        sent: 0,
        received: 0,
        broadcastSent: 0,
        directSent: 0,
        reactionsSent: 0,
        peers: new Set(),
        lastChatText: "n/a",
        lastChatUnix: null,
      }};
      for (const msg of (messages || [])) {{
        const fromId = normalizeNodeId(msg && msg.from);
        const toId = normalizeNodeId(msg && msg.to);
        const isTouch = fromId === nodeId || toId === nodeId;
        if (!isTouch) continue;
        stats.touches += 1;

        const timeText = String((msg && (msg.rx_time || msg.captured_at)) || "").trim();
        const timeUnix = parseDashboardTimeToUnix(timeText);
        if (Number.isFinite(timeUnix) && (!Number.isFinite(stats.lastChatUnix) || timeUnix > stats.lastChatUnix)) {{
          stats.lastChatUnix = timeUnix;
          stats.lastChatText = timeText || "n/a";
        }}

        const replyId = Number(msg && (msg.reply_id ?? msg.replyId));
        const emoji = String((msg && msg.emoji) || "").trim();
        const isReaction = msg && msg.is_reaction === true
          ? true
          : (Number.isFinite(replyId) && replyId > 0 && !!emoji);

        if (fromId === nodeId) {{
          stats.sent += 1;
          if (isReaction) stats.reactionsSent += 1;
          if (classifyMessageChannel(msg) === "direct") {{
            stats.directSent += 1;
          }} else {{
            stats.broadcastSent += 1;
          }}
          if (isSelectableNodeId(toId)) {{
            stats.peers.add(toId);
          }}
        }}
        if (toId === nodeId) {{
          stats.received += 1;
          if (isSelectableNodeId(fromId)) {{
            stats.peers.add(fromId);
          }}
        }}
      }}
      return stats;
    }}

    function computeSavedLinkStats(nodeId, edges) {{
      const stats = {{
        links: 0,
        peers: new Set(),
        lifetimePackets: 0,
        sessionPackets: 0,
        hopsWeighted: 0,
        hopsWeight: 0,
        lastSeenText: "n/a",
        lastSeenUnix: null,
        ports: new Set(),
        topPeer: "",
        topPeerPackets: 0,
      }};
      for (const edge of (edges || [])) {{
        const fromId = normalizeNodeId(edge && edge.from);
        const toId = normalizeNodeId(edge && edge.to);
        if (fromId !== nodeId && toId !== nodeId) continue;
        stats.links += 1;

        const peerId = fromId === nodeId ? toId : fromId;
        if (isSelectableNodeId(peerId)) {{
          stats.peers.add(peerId);
        }}

        const lifetimeCount = Number(edge && (edge.lifetime_count ?? edge.count));
        const sessionCount = Number(edge && (edge.session_count ?? edge.count));
        if (Number.isFinite(lifetimeCount) && lifetimeCount > 0) {{
          stats.lifetimePackets += lifetimeCount;
          if (lifetimeCount > stats.topPeerPackets && isSelectableNodeId(peerId)) {{
            stats.topPeerPackets = lifetimeCount;
            stats.topPeer = peerId;
          }}
        }}
        if (Number.isFinite(sessionCount) && sessionCount > 0) {{
          stats.sessionPackets += sessionCount;
        }}

        const avgHops = Number(edge && edge.avg_hops);
        const hopsWeight = Number.isFinite(lifetimeCount) && lifetimeCount > 0 ? lifetimeCount : 1;
        if (Number.isFinite(avgHops)) {{
          stats.hopsWeighted += avgHops * hopsWeight;
          stats.hopsWeight += hopsWeight;
        }}

        const lastText = String((edge && edge.last_rx_time) || "").trim();
        const lastUnix = parseDashboardTimeToUnix(lastText);
        if (Number.isFinite(lastUnix) && (!Number.isFinite(stats.lastSeenUnix) || lastUnix > stats.lastSeenUnix)) {{
          stats.lastSeenUnix = lastUnix;
          stats.lastSeenText = lastText || "n/a";
        }}

        for (const port of (edge && Array.isArray(edge.portnums) ? edge.portnums : [])) {{
          const cleanPort = String(port || "").trim();
          if (cleanPort) stats.ports.add(cleanPort);
        }}
      }}
      return stats;
    }}

    function renderSavedNodeDetails(state, nodeHistory = null, loadingNodeId = "") {{
      const host = document.getElementById("saved-node-details");
      if (!(host instanceof HTMLElement)) return;

      const safeState = (state && typeof state === "object") ? state : {{}};
      const nodeId = normalizeNodeId(selectedNodeId || "");
      const loadingId = normalizeNodeId(loadingNodeId || "");

      if (favoriteNodeIds.size === 0) {{
        host.innerHTML = '<div class="saved-node-details-empty">No saved nodes yet. Star a node in Chat, Network, or Saved list to start tracking it here.</div>';
        return;
      }}

      if (!isSelectableNodeId(nodeId)) {{
        host.innerHTML = '<div class="saved-node-details-empty">Select a saved node to view historical summary, links, and recent chat activity.</div>';
        return;
      }}
      if (!favoriteNodeIds.has(nodeId)) {{
        host.innerHTML = '<div class="saved-node-details-empty">Selected node is not in Saved. Pick a node from the Saved list on the left.</div>';
        return;
      }}

      const nodes = Array.isArray(safeState.nodes) ? safeState.nodes : [];
      const node = nodes.find((entry) => normalizeNodeId(entry.id || "") === nodeId) || null;
      const historyCapsById = new Map(
        Object.entries((safeState.history_caps && typeof safeState.history_caps === "object") ? safeState.history_caps : {{}})
          .map(([rawNodeId, caps]) => [normalizeNodeId(rawNodeId), caps])
          .filter(([entryNodeId, caps]) => isSelectableNodeId(entryNodeId) && caps && typeof caps === "object")
      );
      const caps = historyCapsById.get(nodeId) || null;

      const requestedHistory = (
        nodeHistory
        && typeof nodeHistory === "object"
        && normalizeNodeId(nodeHistory.node_id || "") === nodeId
      ) ? nodeHistory : null;
      const cachedEntry = nodeHistoryCache.get(nodeId);
      const cachedHistory = (
        cachedEntry
        && cachedEntry.data
        && normalizeNodeId(cachedEntry.data.node_id || "") === nodeId
      ) ? cachedEntry.data : null;
      const history = requestedHistory || cachedHistory;
      const historySummary = (history && typeof history.summary === "object") ? history.summary : {{}};
      const historyPoints = Array.isArray(history && history.points) ? history.points : [];
      const historyPositions = Array.isArray(history && history.positions) ? history.positions : [];
      const historyLoading = loadingId === nodeId && !history;

      const nodeName = preferredNodeName(node) || nodeNameCache.get(nodeId) || `Node ${{nodeId}}`;
      const nowUnix = Math.floor(Date.now() / 1000);
      const liveLastSeenUnix = nodeLastHeardUnix(node);
      const capsLastSeenUnix = Number(caps && caps.last_seen_unix);
      const historyLastSeenUnix = parseDashboardTimeToUnix(historySummary.last_seen || "");
      const lastSeenUnix = Number.isFinite(liveLastSeenUnix)
        ? liveLastSeenUnix
        : (Number.isFinite(capsLastSeenUnix)
            ? Math.trunc(capsLastSeenUnix)
            : (Number.isFinite(historyLastSeenUnix) ? historyLastSeenUnix : null));
      const status = freshnessStatus(lastSeenUnix, nowUnix);
      const statusLabel = status === "online"
        ? "Online"
        : (status === "warn" ? "Aging" : (status === "stale" ? "Stale" : "Unknown"));

      const batteryRaw = Number(
        (node && node.battery_level != null)
          ? node.battery_level
          : NaN
      );
      const capsBatteryRaw = Number(caps && caps.battery_level);
      const batteryValue = Number.isFinite(batteryRaw)
        ? batteryRaw
        : (Number.isFinite(capsBatteryRaw) ? capsBatteryRaw : null);
      const batteryText = Number.isFinite(batteryValue)
        ? `${{Math.max(0, Math.min(100, Math.round(batteryValue)))}}%`
        : "n/a";
      const hopsRaw = Number(
        (node && node.hops_away != null)
          ? node.hops_away
          : NaN
      );
      const capsHopsRaw = Number(caps && caps.last_hops);
      const hopsValue = Number.isFinite(hopsRaw)
        ? hopsRaw
        : (Number.isFinite(capsHopsRaw) ? capsHopsRaw : null);
      const hopsText = Number.isFinite(hopsValue) && hopsValue >= 0 ? String(Math.trunc(hopsValue)) : "n/a";

      const livePosText = (
        node
        && Number.isFinite(Number(node.lat))
        && Number.isFinite(Number(node.lon))
      )
        ? savedDetailCoord(node.lat, node.lon)
        : "n/a";
      const voltageValue = (
        node
        && node.voltage != null
        && Number.isFinite(Number(node.voltage))
      ) ? Number(node.voltage) : null;
      const channelUtilValue = (
        node
        && node.channel_utilization != null
        && Number.isFinite(Number(node.channel_utilization))
      ) ? Number(node.channel_utilization) : null;
      const airUtilTxValue = (
        node
        && node.air_util_tx != null
        && Number.isFinite(Number(node.air_util_tx))
      ) ? Number(node.air_util_tx) : null;
      const latestTrail = historyPositions.length
        ? historyPositions[historyPositions.length - 1]
        : null;
      const latestTrailAltitude = (
        latestTrail
        && latestTrail.altitude != null
        && Number.isFinite(Number(latestTrail.altitude))
      ) ? Number(latestTrail.altitude) : null;
      const latestTrailSats = (
        latestTrail
        && latestTrail.sats_in_view != null
        && Number.isFinite(Number(latestTrail.sats_in_view))
      ) ? Number(latestTrail.sats_in_view) : null;
      const latestTrailPos = latestTrail ? savedDetailCoord(latestTrail.lat, latestTrail.lon) : "n/a";
      const latestPosText = livePosText !== "n/a" ? livePosText : latestTrailPos;
      const positionSource = livePosText !== "n/a"
        ? "Live"
        : (latestTrailPos !== "n/a" ? "History" : "n/a");
      const positionCapable = (caps && caps.has_position === true) || latestTrailPos !== "n/a"
        ? "Yes"
        : "No";

      const historyWindowHours = Number(history && history.window_hours);
      const historyWindowText = Number.isFinite(historyWindowHours) && historyWindowHours > 0
        ? `${{Math.round(historyWindowHours)}}h`
        : `${{nodeHistoryHours}}h`;
      const historyPointCount = Number.isFinite(Number(historySummary.points))
        ? Number(historySummary.points)
        : historyPoints.length;
      const historyTotalPackets = Number.isFinite(Number(historySummary.total_packets))
        ? Number(historySummary.total_packets)
        : historyPoints.reduce((sum, point) => sum + Math.max(0, Number(point && point.packet_count) || 0), 0);
      const activeMinutes = historyPoints.reduce((sum, point) => (
        sum + ((Number(point && point.packet_count) || 0) > 0 ? 1 : 0)
      ), 0);
      const activeHoursText = `${{(activeMinutes / 60).toFixed(1)}}h`;
      const firstPointUnix = historyPoints.length
        ? Number(historyPoints[0] && historyPoints[0].bucket_unix)
        : null;
      const lastPointUnix = historyPoints.length
        ? Number(historyPoints[historyPoints.length - 1] && historyPoints[historyPoints.length - 1].bucket_unix)
        : null;
      const coveredHoursText = savedDetailDurationHours(firstPointUnix, lastPointUnix);
      const peakPacketsPerMinute = historyPoints.reduce((peak, point) => {{
        const count = Number(point && point.packet_count);
        if (!Number.isFinite(count)) return peak;
        return Math.max(peak, count);
      }}, 0);

      let snrWeighted = 0;
      let snrWeight = 0;
      let rssiWeighted = 0;
      let rssiWeight = 0;
      let hopsWeighted = 0;
      let hopsWeight = 0;
      for (const point of historyPoints) {{
        const weight = Math.max(1, Number(point && point.packet_count) || 0);
        const snr = Number(point && point.avg_snr);
        const rssi = Number(point && point.avg_rssi);
        const hops = Number(point && point.avg_hops);
        if (Number.isFinite(snr)) {{
          snrWeighted += snr * weight;
          snrWeight += weight;
        }}
        if (Number.isFinite(rssi)) {{
          rssiWeighted += rssi * weight;
          rssiWeight += weight;
        }}
        if (Number.isFinite(hops)) {{
          hopsWeighted += hops * weight;
          hopsWeight += weight;
        }}
      }}
      const snrAvg = snrWeight > 0 ? (snrWeighted / snrWeight) : null;
      const rssiAvg = rssiWeight > 0 ? (rssiWeighted / rssiWeight) : null;
      const hopsAvg = hopsWeight > 0 ? (hopsWeighted / hopsWeight) : null;
      const snrRange = `${{formatMetricValue(historySummary.snr_min, 1)}} to ${{formatMetricValue(historySummary.snr_max, 1)}} dB`;
      const rssiRange = `${{formatMetricValue(historySummary.rssi_min, 0)}} to ${{formatMetricValue(historySummary.rssi_max, 0)}} dBm`;

      const traffic = (safeState.traffic && typeof safeState.traffic === "object") ? safeState.traffic : {{}};
      const chatMessages = Array.isArray(traffic.recent_chat) ? traffic.recent_chat : [];
      const edges = Array.isArray(traffic.edges) ? traffic.edges : [];
      const chatStats = computeSavedChatStats(nodeId, chatMessages);
      const linkStats = computeSavedLinkStats(nodeId, edges);
      const linkAvgHops = linkStats.hopsWeight > 0
        ? formatMetricValue(linkStats.hopsWeighted / linkStats.hopsWeight, 2)
        : "n/a";

      const subtitleBits = [
        nodeId,
        `Last seen: ${{savedDetailText((node && node.last_heard) || (caps && caps.last_seen) || historySummary.last_seen)}}`,
      ];
      if (historyLoading) {{
        subtitleBits.push("Loading historical data...");
      }}

      const nodeSection = savedDetailSectionHtml("Node", [
        ["Node ID", nodeId],
        ["Node Num", node && node.num != null ? String(node.num) : "n/a"],
        ["Hardware", (node && node.hardware_model) || "n/a"],
        ["Role", (node && node.role) || "n/a"],
        ["Status", statusLabel],
        ["Battery", batteryText],
        ["Hops Away", hopsText],
        ["Voltage", Number.isFinite(voltageValue) ? `${{voltageValue.toFixed(2)}}V` : "n/a"],
        ["Channel Util", Number.isFinite(channelUtilValue) ? savedDetailPercent(channelUtilValue) : "n/a"],
        ["Air Util TX", Number.isFinite(airUtilTxValue) ? savedDetailPercent(airUtilTxValue) : "n/a"],
        ["GPS Capable", positionCapable],
        ["Last Position Ping", savedDetailText((caps && caps.last_position_time) || (latestTrail && latestTrail.time))],
      ]);

      const historySection = savedDetailSectionHtml("History", [
        ["Window", historyWindowText],
        ["Samples (1m)", String(historyPointCount)],
        ["Active Hours", activeHoursText],
        ["Covered Range", coveredHoursText],
        ["Total Packets", String(historyTotalPackets)],
        ["Peak Packets/min", String(Math.round(peakPacketsPerMinute || 0))],
        ["First Bucket", savedDetailText(historySummary.first_bucket)],
        ["Last Bucket", savedDetailText(historySummary.last_bucket)],
        ["History Last Seen", savedDetailText(historySummary.last_seen)],
        ["Avg SNR", Number.isFinite(snrAvg) ? `${{formatMetricValue(snrAvg, 2)}} dB` : "n/a"],
        ["SNR Range", snrRange],
        ["Avg RSSI", Number.isFinite(rssiAvg) ? `${{formatMetricValue(rssiAvg, 1)}} dBm` : "n/a"],
        ["RSSI Range", rssiRange],
        ["Avg Hops", Number.isFinite(hopsAvg) ? formatMetricValue(hopsAvg, 2) : "n/a"],
        ["Trail Points", String(Number.isFinite(Number(historySummary.trail_points)) ? Number(historySummary.trail_points) : historyPositions.length)],
      ], historyLoading ? "Historical points are loading for this node." : "");

      const locationSection = savedDetailSectionHtml("Location", [
        ["Current/Latest Position", latestPosText],
        ["Position Source", positionSource],
        ["Latest Position Time", livePosText !== "n/a" ? savedDetailText((node && node.last_heard) || (caps && caps.last_seen)) : savedDetailText(latestTrail && latestTrail.time)],
        ["Altitude", Number.isFinite(latestTrailAltitude) ? `${{formatMetricValue(latestTrailAltitude, 0)}} m` : "n/a"],
        ["Satellites", Number.isFinite(latestTrailSats) ? String(Math.round(latestTrailSats)) : "n/a"],
        ["Trail Start", savedDetailText(historySummary.trail_start)],
        ["Trail End", savedDetailText(historySummary.trail_end)],
      ]);

      const chatSection = savedDetailSectionHtml("Chat (Recent Buffer)", [
        ["Messages Touching Node", String(chatStats.touches)],
        ["Sent", String(chatStats.sent)],
        ["Received", String(chatStats.received)],
        ["Broadcast Sent", String(chatStats.broadcastSent)],
        ["Direct Sent", String(chatStats.directSent)],
        ["Reactions Sent", String(chatStats.reactionsSent)],
        ["Active Peers", String(chatStats.peers.size)],
        ["Last Chat", savedDetailText(chatStats.lastChatText)],
      ], `Based on current in-memory chat buffer (${{chatMessages.length}} messages).`);

      const linksSection = savedDetailSectionHtml("Links", [
        ["Directed Links", String(linkStats.links)],
        ["Linked Peers", String(linkStats.peers.size)],
        ["Lifetime Packets", String(Math.round(linkStats.lifetimePackets))],
        ["Session Packets", String(Math.round(linkStats.sessionPackets))],
        ["Avg Link Hops", linkAvgHops],
        ["Last Link Activity", savedDetailText(linkStats.lastSeenText)],
        ["Top Peer", savedDetailText(linkStats.topPeer)],
        ["Top Peer Packets", linkStats.topPeer ? String(Math.round(linkStats.topPeerPackets)) : "n/a"],
        ["Seen Ports", linkStats.ports.size > 0 ? Array.from(linkStats.ports).slice(0, 10).join(", ") : "n/a"],
      ]);

      host.innerHTML = `
        <div class="saved-node-details-head">
          <div class="saved-node-title-wrap">
            <div class="saved-node-title">${{escAttr(nodeName)}}</div>
            <div class="saved-node-subtitle">${{subtitleBits.map((part) => escAttr(part)).join("<span>•</span>")}}</div>
          </div>
          <span class="saved-node-status status-${{escAttr(status)}}">${{escAttr(statusLabel)}}</span>
        </div>
        <div class="saved-node-sections">
          ${{nodeSection}}
          ${{historySection}}
          ${{locationSection}}
          ${{chatSection}}
          ${{linksSection}}
        </div>
      `;
    }}

    function renderFavorites(state) {{
      const list = document.getElementById("favorites-list");
      const caption = document.getElementById("favorites-caption");
      if (!(list instanceof HTMLElement)) return;

      const safeState = (state && typeof state === "object") ? state : {{}};
      renderSavedNodeDetails(safeState, null);
      const nodes = Array.isArray(safeState.nodes) ? safeState.nodes : [];
      const nodesById = new Map(nodes.map((node) => [normalizeNodeId(node.id || ""), node]));
      const historyCapsById = new Map(
        Object.entries((safeState.history_caps && typeof safeState.history_caps === "object") ? safeState.history_caps : {{}})
          .map(([rawNodeId, caps]) => [normalizeNodeId(rawNodeId), caps])
          .filter(([nodeId, caps]) => isSelectableNodeId(nodeId) && caps && typeof caps === "object")
      );

      const nowUnix = Math.floor(Date.now() / 1000);
      const entries = Array.from(favoriteNodeIds)
        .map((nodeId) => {{
          const node = nodesById.get(nodeId);
          const caps = historyCapsById.get(nodeId);
          const name = preferredNodeName(node) || nodeNameCache.get(nodeId) || `Node ${{nodeId}}`;
          const liveLastSeen = nodeLastHeardUnix(node);
          const capsLastSeen = Number(caps && caps.last_seen_unix);
          const lastSeenUnix = Number.isFinite(liveLastSeen)
            ? liveLastSeen
            : (Number.isFinite(capsLastSeen) ? Math.trunc(capsLastSeen) : null);
          const status = freshnessStatus(lastSeenUnix, nowUnix);
          const lastSeenText = String(
            (node && node.last_heard)
            || (caps && (caps.last_seen || caps.last_position_time))
            || "n/a"
          );
          const batteryRaw = Number(
            (node && node.battery_level != null)
              ? node.battery_level
              : (caps && caps.battery_level)
          );
          const battery = Number.isFinite(batteryRaw) ? `${{Math.max(0, Math.min(100, Math.round(batteryRaw)))}}%` : "n/a";
          const hopsRaw = Number(
            (node && node.hops_away != null)
              ? node.hops_away
              : (caps && caps.last_hops)
          );
          const hops = Number.isFinite(hopsRaw) && hopsRaw >= 0 ? String(Math.trunc(hopsRaw)) : "n/a";
          const pos = (
            node
            && typeof node.lat === "number"
            && Number.isFinite(node.lat)
            && typeof node.lon === "number"
            && Number.isFinite(node.lon)
          )
            ? `${{node.lat.toFixed(5)}}, ${{node.lon.toFixed(5)}}`
            : ((caps && caps.has_position === true) ? "history" : "n/a");
          const searchable = `${{normalizeSearchQuery(nodeId)}} ${{normalizeSearchQuery(name)}}`;
          return {{
            id: nodeId,
            name,
            status,
            lastSeenText,
            battery,
            hops,
            pos,
            searchable,
          }};
        }})
        .sort((a, b) => {{
          const rankDiff = statusRank(a.status) - statusRank(b.status);
          if (rankDiff !== 0) return rankDiff;
          return String(a.name || a.id).localeCompare(String(b.name || b.id));
        }});

      const query = normalizeSearchQuery(favoritesSearchQuery);
      const filtered = query
        ? entries.filter((entry) => entry.searchable.includes(query))
        : entries;
      const onlineCount = entries.filter((entry) => entry.status === "online").length;
      const warnCount = entries.filter((entry) => entry.status === "warn").length;
      const staleCount = entries.filter((entry) => entry.status === "stale").length;
      if (caption) {{
        caption.textContent = `Saved nodes: ${{entries.length}} total (${{onlineCount}} online, ${{warnCount}} aging, ${{staleCount}} stale)`;
      }}

      if (entries.length === 0) {{
        list.innerHTML = '<div class="favorites-empty">No saved nodes yet. Click ☆ next to a node name to save it.</div>';
        return;
      }}
      if (filtered.length === 0) {{
        list.innerHTML = '<div class="favorites-empty">No saved nodes match this search.</div>';
        return;
      }}

      list.innerHTML = filtered.map((entry) => (
        `<div class="favorite-node-item status-${{entry.status}}${{selectedNodeId === entry.id ? " selected-node" : ""}}" data-node-id="${{escAttr(entry.id)}}" title="${{escAttr(`${{entry.name}} (${{entry.id}})` )}}">
          <div class="favorite-node-main">
            <div class="favorite-node-name-row">
              <span class="favorite-node-name">${{escAttr(entry.name)}}</span>
              <span class="favorite-node-id">${{escAttr(entry.id)}}</span>
            </div>
            <div class="favorite-node-meta">
              <span>Last: ${{escAttr(entry.lastSeenText)}}</span>
              <span>Batt: ${{escAttr(entry.battery)}}</span>
              <span>Hops: ${{escAttr(entry.hops)}}</span>
              <span>Pos: ${{escAttr(entry.pos)}}</span>
            </div>
          </div>
          ${{favoriteToggleButtonHtml(entry.id, "favorites-card-star")}}
        </div>`
      )).join("");

      for (const item of list.querySelectorAll(".favorite-node-item")) {{
        if (!(item instanceof HTMLElement)) continue;
        item.addEventListener("click", (ev) => {{
          const target = ev.target;
          if (target instanceof Element && target.closest(".favorite-toggle-btn")) {{
            return;
          }}
          selectNode(item.dataset.nodeId || "", true, false);
        }});
      }}
      refreshFavoriteToggleButtons();
    }}

    function formatMetricValue(value, decimals = 2, suffix = "") {{
      const num = Number(value);
      if (!Number.isFinite(num)) return "n/a";
      return `${{num.toFixed(decimals)}}${{suffix}}`;
    }}

    function setSignalTimelineMessage(message) {{
      const timeline = document.getElementById("signal-timeline");
      if (!(timeline instanceof HTMLElement)) return;
      timeline.innerHTML = "";
      const text = String(message || "").trim();
      if (!text) return;
      const note = document.createElement("div");
      note.className = "signal-timeline-empty";
      note.textContent = text;
      timeline.appendChild(note);
    }}

    function signalPointUnix(point) {{
      const direct = Number(point && point.bucket_unix);
      if (Number.isFinite(direct) && direct > 0) {{
        return Math.trunc(direct);
      }}
      const stamp = String(
        (point && (point.bucket_time || point.bucket_local)) || ""
      ).trim();
      if (!stamp) return null;
      const normalized = stamp.includes("T")
        ? stamp
        : stamp.replace(" ", "T");
      const parsed = Date.parse(normalized);
      if (Number.isFinite(parsed)) {{
        return Math.trunc(parsed / 1000);
      }}
      return null;
    }}

    function formatSignalTimelineLabel(unixTs, includeDate) {{
      if (!Number.isFinite(unixTs)) return "";
      const dt = new Date(unixTs * 1000);
      if (Number.isNaN(dt.getTime())) return "";
      const hh = String(dt.getHours()).padStart(2, "0");
      const mm = String(dt.getMinutes()).padStart(2, "0");
      const timeLabel = `${{hh}}:${{mm}}`;
      if (!includeDate) return timeLabel;
      const mon = String(dt.getMonth() + 1).padStart(2, "0");
      const day = String(dt.getDate()).padStart(2, "0");
      return `${{mon}}/${{day}} ${{timeLabel}}`;
    }}

    function renderSignalTimeline(rows, padLeft, padRight, width) {{
      const timeline = document.getElementById("signal-timeline");
      if (!(timeline instanceof HTMLElement)) return;

      const total = Array.isArray(rows) ? rows.length : 0;
      if (!total) {{
        setSignalTimelineMessage("Timeline available when history points are present.");
        return;
      }}

      const timestamps = rows.map((row) => signalPointUnix(row));
      const valid = timestamps.filter((ts) => Number.isFinite(ts));
      if (!valid.length) {{
        setSignalTimelineMessage("Timeline unavailable (missing timestamps).");
        return;
      }}

      const axisStartPct = Math.max(0, Math.min(100, (padLeft / width) * 100));
      const axisEndPct = Math.max(axisStartPct, Math.min(100, ((width - padRight) / width) * 100));
      const axisWidthPct = axisEndPct - axisStartPct;
      const startUnix = valid[0];
      const endUnix = valid[valid.length - 1];
      const spanCrossesDay = Math.floor(startUnix / 86400) !== Math.floor(endUnix / 86400);

      const maxTicks = 5;
      const desired = Math.max(2, Math.min(maxTicks, total));
      const indexSet = new Set();
      for (let i = 0; i < desired; i += 1) {{
        const idx = Math.round((i * (total - 1)) / Math.max(1, desired - 1));
        indexSet.add(Math.max(0, Math.min(total - 1, idx)));
      }}
      indexSet.add(0);
      indexSet.add(total - 1);
      const indices = Array.from(indexSet).sort((a, b) => a - b);

      timeline.innerHTML = "";
      const track = document.createElement("div");
      track.className = "signal-timeline-track";
      track.style.left = `${{axisStartPct.toFixed(3)}}%`;
      track.style.right = `${{(100 - axisEndPct).toFixed(3)}}%`;
      timeline.appendChild(track);

      for (let i = 0; i < indices.length; i += 1) {{
        const idx = indices[i];
        const pointUnix = timestamps[idx];
        const ratio = (total <= 1) ? 0 : (idx / (total - 1));
        const leftPct = axisStartPct + (ratio * axisWidthPct);
        const mark = document.createElement("div");
        mark.className = "signal-timeline-mark";
        if (i === 0) mark.classList.add("edge-start");
        if (i === indices.length - 1) mark.classList.add("edge-end");
        mark.style.left = `${{leftPct.toFixed(3)}}%`;

        const tick = document.createElement("div");
        tick.className = "signal-timeline-tick";
        mark.appendChild(tick);

        const label = document.createElement("div");
        label.className = "signal-timeline-label";
        const includeDate = spanCrossesDay && (i === 0 || i === indices.length - 1);
        label.textContent = formatSignalTimelineLabel(pointUnix, includeDate);
        if (Number.isFinite(pointUnix)) {{
          label.title = new Date(pointUnix * 1000).toLocaleString();
        }}
        mark.appendChild(label);
        timeline.appendChild(mark);
      }}
    }}

    function renderSignalChart(points) {{
      const svg = document.getElementById("signal-chart");
      const empty = document.getElementById("signal-empty");
      if (!(svg instanceof SVGElement) || !(empty instanceof HTMLElement)) return;

      const rows = Array.isArray(points) ? points : [];
      const width = 900;
      const height = 220;
      const padLeft = 44;
      const padRight = 44;
      const padTop = 12;
      const padBottom = 30;
      const plotW = width - padLeft - padRight;
      const plotH = height - padTop - padBottom;

      const snrVals = rows.map((p) => Number(p.avg_snr)).filter((v) => Number.isFinite(v));
      const rssiVals = rows.map((p) => Number(p.avg_rssi)).filter((v) => Number.isFinite(v));
      if (snrVals.length === 0 && rssiVals.length === 0) {{
        svg.innerHTML = "";
        empty.hidden = false;
        empty.textContent = "No historical signal points yet for this node.";
        renderSignalTimeline(rows, padLeft, padRight, width);
        return;
      }}
      empty.hidden = true;

      const withSpread = (vals, fallbackMin, fallbackMax) => {{
        if (!vals.length) return [fallbackMin, fallbackMax];
        let lo = Math.min(...vals);
        let hi = Math.max(...vals);
        if (Math.abs(hi - lo) < 0.001) {{
          lo -= 1;
          hi += 1;
        }}
        return [lo, hi];
      }};

      const [snrMin, snrMax] = withSpread(snrVals, -20, 20);
      const [rssiMin, rssiMax] = withSpread(rssiVals, -130, -60);
      const xAt = (idx, total) => (
        padLeft + ((Math.max(0, idx) / Math.max(1, total - 1)) * plotW)
      );
      const yFrom = (value, minVal, maxVal) => (
        padTop + ((maxVal - value) / (maxVal - minVal)) * plotH
      );

      const buildPath = (metricKey, minVal, maxVal) => {{
        const n = rows.length;
        let d = "";
        let started = false;
        for (let i = 0; i < n; i += 1) {{
          const raw = Number(rows[i][metricKey]);
          if (!Number.isFinite(raw)) continue;
          const x = xAt(i, n);
          const y = yFrom(raw, minVal, maxVal);
          d += `${{started ? " L " : "M "}}${{x.toFixed(2)}} ${{y.toFixed(2)}}`;
          started = true;
        }}
        return d;
      }};

      const snrPath = buildPath("avg_snr", snrMin, snrMax);
      const rssiPath = buildPath("avg_rssi", rssiMin, rssiMax);
      const midY = padTop + (plotH / 2);
      const darkTheme = document.documentElement.getAttribute("data-theme") === "dark";
      const chartPalette = darkTheme
        ? {{
            grid: "#324152",
            snr: "#58c878",
            rssi: "#79c0ff",
            snrLabel: "#88e8a5",
            rssiLabel: "#a4d0ff",
          }}
        : {{
            grid: "#dce8df",
            snr: "#1f6f53",
            rssi: "#265d7b",
            snrLabel: "#1f6f53",
            rssiLabel: "#265d7b",
          }};

      svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);
      svg.innerHTML = `
        <rect x="0" y="0" width="${{width}}" height="${{height}}" fill="none"></rect>
        <line x1="${{padLeft}}" y1="${{midY.toFixed(2)}}" x2="${{width - padRight}}" y2="${{midY.toFixed(2)}}" stroke="${{chartPalette.grid}}" stroke-width="1"></line>
        <line x1="${{padLeft}}" y1="${{padTop}}" x2="${{padLeft}}" y2="${{height - padBottom}}" stroke="${{chartPalette.grid}}" stroke-width="1"></line>
        <line x1="${{width - padRight}}" y1="${{padTop}}" x2="${{width - padRight}}" y2="${{height - padBottom}}" stroke="${{chartPalette.grid}}" stroke-width="1"></line>
        ${{snrPath ? `<path d="${{snrPath}}" fill="none" stroke="${{chartPalette.snr}}" stroke-width="2"></path>` : ""}}
        ${{rssiPath ? `<path d="${{rssiPath}}" fill="none" stroke="${{chartPalette.rssi}}" stroke-width="2"></path>` : ""}}
        <text x="${{padLeft - 4}}" y="${{padTop + 10}}" font-size="10" text-anchor="end" fill="${{chartPalette.snrLabel}}">${{formatMetricValue(snrMax, 1)}}</text>
        <text x="${{padLeft - 4}}" y="${{height - padBottom + 11}}" font-size="10" text-anchor="end" fill="${{chartPalette.snrLabel}}">${{formatMetricValue(snrMin, 1)}}</text>
        <text x="${{width - padRight + 4}}" y="${{padTop + 10}}" font-size="10" text-anchor="start" fill="${{chartPalette.rssiLabel}}">${{formatMetricValue(rssiMax, 0)}}</text>
        <text x="${{width - padRight + 4}}" y="${{height - padBottom + 11}}" font-size="10" text-anchor="start" fill="${{chartPalette.rssiLabel}}">${{formatMetricValue(rssiMin, 0)}}</text>
      `;
      renderSignalTimeline(rows, padLeft, padRight, width);
    }}

    function renderOnlineActivityLoading() {{
      setMapDataMode("activity");
      const caption = document.getElementById("online-activity-caption");
      if (caption) {{
        caption.textContent = "Loading online-node activity history...";
      }}
      const overview = document.getElementById("online-activity-overview");
      if (overview) {{
        overview.innerHTML = "";
      }}
      const svg = document.getElementById("online-activity-chart");
      if (svg) {{
        svg.innerHTML = "";
      }}
      const empty = document.getElementById("online-activity-empty");
      if (empty) {{
        empty.hidden = false;
        empty.textContent = "Loading historical online activity...";
      }}
    }}

    function renderOnlineActivityError(message) {{
      setMapDataMode("activity");
      const caption = document.getElementById("online-activity-caption");
      if (caption) {{
        caption.textContent = `Online activity error: ${{message || "unknown error"}}`;
      }}
      const overview = document.getElementById("online-activity-overview");
      if (overview) {{
        overview.innerHTML = "";
      }}
      const svg = document.getElementById("online-activity-chart");
      if (svg) {{
        svg.innerHTML = "";
      }}
      const empty = document.getElementById("online-activity-empty");
      if (empty) {{
        empty.hidden = false;
        empty.textContent = "Unable to load online-activity history.";
      }}
    }}

    function renderOnlineActivityChart(points) {{
      const svg = document.getElementById("online-activity-chart");
      const empty = document.getElementById("online-activity-empty");
      if (!(svg instanceof SVGElement) || !(empty instanceof HTMLElement)) return;

      const rows = Array.isArray(points) ? points : [];
      const values = rows.map((p) => Number(p.online_nodes)).filter((v) => Number.isFinite(v));
      if (values.length === 0) {{
        svg.innerHTML = "";
        empty.hidden = false;
        empty.textContent = "No historical online-activity points yet.";
        return;
      }}
      empty.hidden = true;

      const width = 900;
      const height = 220;
      const padLeft = 46;
      const padRight = 10;
      const padTop = 12;
      const padBottom = 24;
      const plotW = width - padLeft - padRight;
      const plotH = height - padTop - padBottom;

      let minVal = Math.min(0, ...values);
      let maxVal = Math.max(...values);
      if ((maxVal - minVal) < 1) {{
        maxVal = minVal + 1;
      }}

      const xAt = (idx, total) => (
        padLeft + ((Math.max(0, idx) / Math.max(1, total - 1)) * plotW)
      );
      const yFrom = (value, minValue, maxValue) => (
        padTop + ((maxValue - value) / (maxValue - minValue)) * plotH
      );

      const n = rows.length;
      const pointsXY = [];
      for (let i = 0; i < n; i += 1) {{
        const raw = Number(rows[i].online_nodes);
        if (!Number.isFinite(raw)) continue;
        pointsXY.push({{
          x: xAt(i, n),
          y: yFrom(raw, minVal, maxVal),
        }});
      }}
      if (!pointsXY.length) {{
        svg.innerHTML = "";
        empty.hidden = false;
        empty.textContent = "No historical online-activity points yet.";
        return;
      }}

      const path = pointsXY.map((pt, idx) => (
        `${{idx === 0 ? "M" : "L"}} ${{pt.x.toFixed(2)}} ${{pt.y.toFixed(2)}}`
      )).join(" ");

      const darkTheme = document.documentElement.getAttribute("data-theme") === "dark";
      const chartPalette = darkTheme
        ? {{
            grid: "#324152",
            line: "#79c0ff",
            label: "#a4d0ff",
          }}
        : {{
            grid: "#dce8df",
            line: "#1f6f53",
            label: "#1f6f53",
          }};

      const startLabel = rows[0] && (rows[0].bucket_local || rows[0].bucket_time || "");
      const endLabel = rows[rows.length - 1] && (rows[rows.length - 1].bucket_local || rows[rows.length - 1].bucket_time || "");
      const midY = padTop + (plotH / 2);

      svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);
      svg.innerHTML = `
        <rect x="0" y="0" width="${{width}}" height="${{height}}" fill="none"></rect>
        <line x1="${{padLeft}}" y1="${{padTop}}" x2="${{padLeft}}" y2="${{height - padBottom}}" stroke="${{chartPalette.grid}}" stroke-width="1"></line>
        <line x1="${{padLeft}}" y1="${{midY.toFixed(2)}}" x2="${{width - padRight}}" y2="${{midY.toFixed(2)}}" stroke="${{chartPalette.grid}}" stroke-width="1"></line>
        <line x1="${{padLeft}}" y1="${{height - padBottom}}" x2="${{width - padRight}}" y2="${{height - padBottom}}" stroke="${{chartPalette.grid}}" stroke-width="1"></line>
        <path d="${{path}}" fill="none" stroke="${{chartPalette.line}}" stroke-width="2.3"></path>
        <text x="${{padLeft - 4}}" y="${{padTop + 10}}" font-size="10" text-anchor="end" fill="${{chartPalette.label}}">${{formatMetricValue(maxVal, 0)}}</text>
        <text x="${{padLeft - 4}}" y="${{height - padBottom}}" font-size="10" text-anchor="end" fill="${{chartPalette.label}}">${{formatMetricValue(minVal, 0)}}</text>
        <text x="${{padLeft}}" y="${{height - 6}}" font-size="10" text-anchor="start" fill="${{chartPalette.label}}">${{escAttr(startLabel || "")}}</text>
        <text x="${{width - padRight}}" y="${{height - 6}}" font-size="10" text-anchor="end" fill="${{chartPalette.label}}">${{escAttr(endLabel || "")}}</text>
      `;
    }}

    function renderOnlineActivityOverview(activity) {{
      const summary = activity.summary || {{}};
      const target = document.getElementById("online-activity-overview");
      if (!target) return;
      const profile = Array.isArray(activity.hourly_profile) ? activity.hourly_profile : [];
      const topHours = profile
        .filter((row) => Number.isFinite(Number(row.avg_online_nodes)))
        .sort((a, b) => Number(b.avg_online_nodes) - Number(a.avg_online_nodes))
        .slice(0, 3);
      const topHoursText = topHours.length
        ? topHours.map((row) => `${{row.label}} (${{formatMetricValue(row.avg_online_nodes, 1)}})`).join(", ")
        : "n/a";
      const bestHourLabel = summary.best_hour_label || "n/a";
      const bestHourAvgText = Number.isFinite(Number(summary.best_hour_avg_online_nodes))
        ? ` (${{formatMetricValue(summary.best_hour_avg_online_nodes, 1)}} avg)`
        : "";
      const items = [
        ["Window", `${{activity.window_hours ?? nodeHistoryHours}}h (${{activity.timezone_label || "local"}})`],
        ["Samples", `${{summary.sample_hours ?? (activity.points || []).length ?? 0}}`],
        ["Distinct Nodes", `${{summary.distinct_nodes ?? 0}}`],
        ["Peak Online", `${{summary.max_online_nodes ?? 0}}`],
        ["Average Online", `${{formatMetricValue(summary.avg_online_nodes, 1)}}`],
        ["Best Hour", `${{bestHourLabel}}${{bestHourAvgText}}`],
        ["Top Hours", `${{topHoursText}}`],
        ["Range", `${{summary.window_start || "n/a"}} to ${{summary.window_end || "n/a"}}`],
      ];
      target.innerHTML = items.map(([k, v]) => (
        `<div class="overview-item"><div class="k">${{k}}</div><div class="v">${{v}}</div></div>`
      )).join("");
    }}

    function renderOnlineActivity(activity) {{
      setMapDataMode("activity");
      const summary = activity.summary || {{}};
      const bestHourLabel = summary.best_hour_label || null;
      const bestHourAvgText = Number.isFinite(Number(summary.best_hour_avg_online_nodes))
        ? `${{formatMetricValue(summary.best_hour_avg_online_nodes, 1)}} avg nodes`
        : "n/a avg nodes";
      const caption = document.getElementById("online-activity-caption");
      if (caption) {{
        if (bestHourLabel) {{
          caption.textContent = `Last ${{activity.window_hours || nodeHistoryHours}}h. Most common online time: ${{bestHourLabel}} (${{activity.timezone_label || "local"}}), ${{bestHourAvgText}}.`;
        }} else {{
          caption.textContent = `Last ${{activity.window_hours || nodeHistoryHours}}h. No saved online-activity history yet.`;
        }}
      }}
      renderOnlineActivityChart(activity.points || []);
      renderOnlineActivityOverview(activity);
    }}

    function renderNodeHistoryOverview(history, node) {{
      const summary = history.summary || {{}};
      const target = document.getElementById("node-history-overview");
      if (!target) return;
      const historyNodeId = normalizeNodeId(history.node_id || "");
      const label = node ? nodeLabel(node) : (historyNodeId || selectedNodeId || "node");
      const items = [
        ["Node", `${{label}}`],
        ["Node ID", `${{historyNodeId || selectedNodeId || "n/a"}}`],
        ["Points", `${{summary.points ?? (history.points || []).length ?? 0}}`],
        ["Trail Points", `${{summary.trail_points ?? (history.positions || []).length ?? 0}}`],
        ["Packets", `${{summary.total_packets ?? 0}}`],
        ["Window", `${{history.window_hours ?? nodeHistoryHours}}h`],
        ["Last Seen", `${{summary.last_seen || "n/a"}}`],
        ["Trail Range", `${{summary.trail_start || "n/a"}} to ${{summary.trail_end || "n/a"}}`],
        ["SNR Range", `${{formatMetricValue(summary.snr_min, 1)}} to ${{formatMetricValue(summary.snr_max, 1)}} dB`],
        ["RSSI Range", `${{formatMetricValue(summary.rssi_min, 0)}} to ${{formatMetricValue(summary.rssi_max, 0)}} dBm`],
      ];
      target.innerHTML = items.map(([k, v]) => (
        `<div class="overview-item"><div class="k">${{k}}</div><div class="v">${{v}}</div></div>`
      )).join("");
    }}

    function renderNodeHistory(history, nodes) {{
      setMapDataMode("node");
      const node = selectedNodeFrom(nodes);
      const historyNodeId = normalizeNodeId(history.node_id || "");
      const caption = document.getElementById("node-history-caption");
      if (caption) {{
        const name = node ? nodeLabel(node) : (historyNodeId || selectedNodeId || "node");
        const span = history.summary || {{}};
        const trailPoints = Number.isFinite(Number(span.trail_points))
          ? Number(span.trail_points)
          : (Array.isArray(history.positions) ? history.positions.length : 0);
        const loc = (node && typeof node.lat === "number" && typeof node.lon === "number")
          ? `Current location: ${{node.lat.toFixed(5)}}, ${{node.lon.toFixed(5)}}.`
          : "No current location available from live node state.";
        caption.textContent = `${{name}} (${{historyNodeId || selectedNodeId || "n/a"}}). ${{loc}} History window: ${{history.window_hours || nodeHistoryHours}}h, packets: ${{span.total_packets ?? 0}}, trail points: ${{trailPoints}}.`;
      }}
      renderSignalChart(history.points || []);
      renderNodeHistoryOverview(history, node);
      setHistoryTab(activeHistoryTab);
    }}

    async function fetchNodeHistory(nodeId) {{
      if (!isSelectableNodeId(nodeId)) return null;
      const cached = nodeHistoryCache.get(nodeId);
      const nowMs = Date.now();
      if (cached && (nowMs - (cached.fetchedAt || 0)) < Math.max(refreshMs, 2500)) {{
        return cached.data;
      }}
      const url = `/api/history/node?node_id=${{encodeURIComponent(nodeId)}}&hours=${{nodeHistoryHours}}&points=${{nodeHistoryMaxPoints}}`;
      const resp = await fetch(url, {{ cache: "no-store" }});
      if (!resp.ok) throw new Error(`history API ${{resp.status}}`);
      const data = await resp.json();
      nodeHistoryCache.set(nodeId, {{ fetchedAt: nowMs, data }});
      return data;
    }}

    async function fetchOnlineActivity(hoursOverride = nodeHistoryHours) {{
      const cleanHours = Math.max(1, Math.round(Number(hoursOverride) || nodeHistoryHours));
      const cacheKey = String(cleanHours);
      const cached = onlineActivityCache.get(cacheKey);
      const nowMs = Date.now();
      if (cached && (nowMs - (cached.fetchedAt || 0)) < Math.max(refreshMs, 2500)) {{
        return cached.data;
      }}
      const url = `/api/history/online?hours=${{encodeURIComponent(cleanHours)}}`;
      const resp = await fetch(url, {{ cache: "no-store" }});
      if (!resp.ok) throw new Error(`online activity API ${{resp.status}}`);
      const data = await resp.json();
      onlineActivityCache.set(cacheKey, {{ fetchedAt: nowMs, data }});
      return data;
    }}

    function renderTraffic(traffic, nodes, nodeHistory, onlineActivity) {{
      if (mapDataFocus === "activity") {{
        if (onlineActivity && !onlineActivity.error) {{
          renderOnlineActivity(onlineActivity);
        }} else if (onlineActivity && onlineActivity.error) {{
          renderOnlineActivityError(onlineActivity.error);
        }} else {{
          renderOnlineActivityLoading();
        }}
        return;
      }}

      if (isSelectableNodeId(selectedNodeId)) {{
        if (nodeHistory && normalizeNodeId(nodeHistory.node_id) === selectedNodeId) {{
          renderNodeHistory(nodeHistory, nodes);
        }} else {{
          renderNodeHistoryLoading(selectedNodeId);
        }}
        return;
      }}

      setMapDataMode("live");
      const ports = (traffic.port_counts || []).slice(0, 30).map((item) => (
        `<tr><td data-sort="${{escAttr(item.portnum ?? "")}}">${{item.portnum}}</td><td data-sort="${{escAttr(item.count ?? "")}}">${{item.count}}</td></tr>`
      ));
      fillTable("ports-table", ports);

      const links = (traffic.edges || []).slice(0, 60).map((edge) => (
        `<tr>
          <td data-sort="${{escAttr(edge.from ?? "")}}">${{edge.from}}</td>
          <td data-sort="${{escAttr(edge.to ?? "")}}">${{edge.to}}</td>
          <td data-sort="${{escAttr(edge.lifetime_count ?? edge.count ?? 0)}}">${{edge.lifetime_count ?? edge.count ?? 0}}</td>
          <td data-sort="${{escAttr(edge.avg_hops ?? "")}}">${{edge.avg_hops == null ? "n/a" : edge.avg_hops}}</td>
          <td data-sort="${{escAttr(edge.confidence || (edge.is_real ? "confirmed" : "observed"))}}">${{edge.confidence || (edge.is_real ? "confirmed" : "observed")}}</td>
          <td data-sort="${{escAttr(edge.last_rx_time ?? "")}}">${{edge.last_rx_time || "n/a"}}</td>
        </tr>`
      ));
      fillTable("links-table", links);
    }}

    function renderChat(state) {{
      const traffic = state.traffic || {{}};
      const s = state.summary || {{}};
      const chatScroller = getChatScroller();
      const shouldStickBottom = !!(chatScroller && (chatStickToBottom || isNearBottom(chatScroller)));
      updateNodeNameCache(state.nodes || []);
      const nowUnix = Math.floor(Date.now() / 1000);
      const nodesById = new Map(
        (state.nodes || []).map((node) => [normalizeNodeId(node.id || ""), node])
      );
      const historyCapsById = new Map(
        Object.entries((state && state.history_caps && typeof state.history_caps === "object") ? state.history_caps : {{}})
          .map(([rawNodeId, caps]) => [normalizeNodeId(rawNodeId), caps])
          .filter(([nodeId, caps]) => isSelectableNodeId(nodeId) && caps && typeof caps === "object")
      );

      const nodeIdentityMeta = (nodeId) => {{
        const clean = normalizeNodeId(nodeId);
        if (!clean || !isSelectableNodeId(clean)) {{
          return {{ html: "", title: "" }};
        }}
        const node = nodesById.get(clean);
        const historyCaps = historyCapsById.get(clean);
        if ((!node || typeof node !== "object") && (!historyCaps || typeof historyCaps !== "object")) {{
          return {{ html: "", title: "" }};
        }}

        const liveLastSeen = nodeLastHeardUnix(node);
        const capsLastSeen = Number(historyCaps && historyCaps.last_seen_unix);
        const lastSeenUnix = Number.isFinite(liveLastSeen)
          ? liveLastSeen
          : (Number.isFinite(capsLastSeen) ? Math.trunc(capsLastSeen) : null);
        const freshness = freshnessStatus(lastSeenUnix, nowUnix);
        const chipStateClass = freshness === "online" ? "online" : "offline";

        const chips = [];
        const titleParts = [];
        const liveHasPosition = !!node
          && typeof node.lat === "number"
          && Number.isFinite(node.lat)
          && typeof node.lon === "number"
          && Number.isFinite(node.lon);
        const historyHasPosition = !!historyCaps && historyCaps.has_position === true;
        if (liveHasPosition || historyHasPosition) {{
          chips.push(`<span class="chat-name-chip gps ${{chipStateClass}}" title="GPS position available">&#x1F4CD;</span>`);
          titleParts.push(liveHasPosition ? "GPS available" : "GPS last known");
        }}

        const batteryRaw = Number(
          (node && node.battery_level != null)
            ? node.battery_level
            : (historyCaps && historyCaps.battery_level)
        );
        if (Number.isFinite(batteryRaw)) {{
          const batteryPct = Math.max(0, Math.min(100, Math.round(batteryRaw)));
          chips.push(`<span class="chat-name-chip battery ${{chipStateClass}}" title="Battery level">${{batteryPct}}%</span>`);
          titleParts.push(
            (node && node.battery_level != null)
              ? `Battery ${{batteryPct}}%`
              : `Battery last known ${{batteryPct}}%`
          );
        }}

        const hopsRaw = Number(
          (node && node.hops_away != null)
            ? node.hops_away
          : (historyCaps && historyCaps.last_hops)
        );
        if (Number.isFinite(hopsRaw) && hopsRaw >= 0) {{
          const hops = Math.trunc(hopsRaw);
          chips.push(`<span class="chat-name-chip hops ${{chipStateClass}}" title="Hops away">${{hops}}h</span>`);
          titleParts.push(
            (node && node.hops_away != null)
              ? `${{hops}} hop${{hops === 1 ? "" : "s"}} away`
              : `${{hops}} hop${{hops === 1 ? "" : "s"}} last known`
          );
        }}

        return {{
          html: chips.join(""),
          title: titleParts.join(", "),
        }};
      }};

      const chatEndpointParts = (nodeId) => {{
        const clean = normalizeNodeId(nodeId);
        if (!clean) {{
          return {{ label: "n/a", idTag: "", title: "n/a", status: "unknown", metaHtml: "" }};
        }}
        if (clean === "^all") {{
          return {{ label: "All", idTag: "", title: "^all", status: "unknown", metaHtml: "" }};
        }}
        if (clean === "local") {{
          return {{ label: "Local", idTag: "", title: "local", status: "online", metaHtml: "" }};
        }}
        const node = nodesById.get(clean);
        const name = preferredNodeName(node) || nodeNameCache.get(clean) || "Unknown node";
        const lastHeard = nodeLastHeardUnix(node);
        const status = freshnessStatus(lastHeard, nowUnix);
        const meta = nodeIdentityMeta(clean);
        return {{
          label: name,
          idTag: clean,
          title: `${{name}} (${{clean}})${{meta.title ? ` - ${{meta.title}}` : ""}}`,
          status,
          metaHtml: meta.html,
        }};
      }};

      const participants = new Map();
      const channelCounts = {{ all: 0, direct: 0 }};
      const touchParticipant = (meta, msgTimeUnix) => {{
        if (!meta || !meta.idTag || !isSelectableNodeId(meta.idTag)) return;
        const existing = participants.get(meta.idTag);
        if (!existing) {{
          participants.set(meta.idTag, {{
            id: meta.idTag,
            name: meta.label || meta.idTag,
            status: String(meta.status || "unknown"),
            lastMessageUnix: msgTimeUnix || null,
          }});
          return;
        }}
        if (meta.label && meta.label !== "Unknown node") {{
          existing.name = meta.label;
        }}
        existing.status = pickFresherStatus(existing.status, String(meta.status || "unknown"));
        if (msgTimeUnix && (!existing.lastMessageUnix || msgTimeUnix > existing.lastMessageUnix)) {{
          existing.lastMessageUnix = msgTimeUnix;
        }}
      }};

      const touchNodeById = (nodeId, msgTimeUnix = null) => {{
        const clean = normalizeNodeId(nodeId);
        if (!isSelectableNodeId(clean)) return;
        const node = nodesById.get(clean);
        const name = preferredNodeName(node) || nodeNameCache.get(clean) || clean;
        const lastHeard = nodeLastHeardUnix(node);
        const status = freshnessStatus(lastHeard, nowUnix);
        const existing = participants.get(clean);
        if (!existing) {{
          participants.set(clean, {{
            id: clean,
            name,
            status,
            lastMessageUnix: msgTimeUnix || lastHeard || null,
          }});
          return;
        }}
        if (name && name !== "Unknown node") {{
          existing.name = name;
        }}
        existing.status = pickFresherStatus(existing.status, status);
        const recent = msgTimeUnix || lastHeard || null;
        if (recent && (!existing.lastMessageUnix || recent > existing.lastMessageUnix)) {{
          existing.lastMessageUnix = recent;
        }}
      }};

      const escapeChatText = (value) => {{
        const clean = String(value == null ? "" : value);
        const escaped = escAttr(clean);
        return escaped.replace(/\\n/g, "<br/>");
      }};

      const parseMessageId = (value) => {{
        const num = Number(value);
        if (!Number.isFinite(num) || num <= 0) return null;
        return Math.trunc(num);
      }};

      const messageIdOf = (msg) => {{
        if (!msg || typeof msg !== "object") return null;
        return parseMessageId(msg.message_id ?? msg.messageId ?? msg.packet_id ?? msg.packetId);
      }};

      const replyIdOf = (msg) => {{
        if (!msg || typeof msg !== "object") return null;
        return parseMessageId(msg.reply_id ?? msg.replyId);
      }};

      const emojiOf = (msg) => {{
        if (!msg || typeof msg !== "object") return "";
        const direct = String(msg.emoji || "").trim();
        if (direct) return direct;
        const codepoint = Number(msg.emoji_codepoint ?? msg.emojiCodepoint);
        if (Number.isInteger(codepoint) && codepoint > 0) {{
          try {{
            return String.fromCodePoint(codepoint);
          }} catch (_err) {{
            return "";
          }}
        }}
        return "";
      }};

      const isReactionMessage = (msg) => {{
        if (!msg || typeof msg !== "object") return false;
        if (msg.is_reaction === true) return true;
        const replyId = replyIdOf(msg);
        const emoji = emojiOf(msg);
        return !!(replyId && emoji);
      }};

      const rawMessages = traffic.recent_chat || [];
      const reactionBuckets = new Map();
      for (const msg of rawMessages) {{
        if (!isReactionMessage(msg)) continue;
        const replyId = replyIdOf(msg);
        const emoji = emojiOf(msg);
        if (!replyId || !emoji) continue;

        const key = String(replyId);
        let perMessage = reactionBuckets.get(key);
        if (!(perMessage instanceof Map)) {{
          perMessage = new Map();
          reactionBuckets.set(key, perMessage);
        }}

        let bucket = perMessage.get(emoji);
        if (!bucket) {{
          bucket = {{
            emoji,
            count: 0,
            reactors: new Set(),
            names: [],
            lastUnix: 0,
          }};
          perMessage.set(emoji, bucket);
        }}

        const reactorId = normalizeNodeId(msg.from || "");
        const reactorMeta = chatEndpointParts(reactorId);
        const reactorName = reactorMeta.label || reactorId || "Unknown node";
        const dedupeKey = reactorId || `${{reactorName}}:${{msg.rx_time || msg.captured_at || bucket.count}}`;
        if (!bucket.reactors.has(dedupeKey)) {{
          bucket.reactors.add(dedupeKey);
          bucket.count += 1;
          bucket.names.push(reactorName);
        }}
        const reactionTime = parseDashboardTimeToUnix(msg.rx_time || msg.captured_at || "");
        if (reactionTime && reactionTime > bucket.lastUnix) {{
          bucket.lastUnix = reactionTime;
        }}
      }}

      const baseMessages = rawMessages.filter((msg) => !isReactionMessage(msg));
      const keyedMessages = baseMessages
        .map((msg) => ({{
          key: chatMessageKey(msg),
          channel: classifyMessageChannel(msg),
          sender: chatEndpointParts(normalizeNodeId(msg.from || "")).label || "Unknown node",
        }}))
        .filter((entry) => !!entry.key);
      if (!chatUnreadInitialized) {{
        for (const entry of keyedMessages) {{
          rememberSeenChatMessage(entry.key);
        }}
        chatUnreadInitialized = true;
      }} else {{
        const freshByChannel = {{ all: 0, direct: 0 }};
        const latestSenderByChannel = {{ all: "", direct: "" }};
        for (const entry of keyedMessages) {{
          if (rememberSeenChatMessage(entry.key)) {{
            const key = entry.channel === "direct" ? "direct" : "all";
            freshByChannel[key] += 1;
            latestSenderByChannel[key] = String(entry.sender || "").trim();
          }}
        }}
        if (activeLayoutView === "chat") {{
          const otherKey = activeChatChannel === "direct" ? "all" : "direct";
          if (freshByChannel[otherKey] > 0) {{
            setChatChannelUnread(otherKey, Number(chatUnreadByChannel[otherKey] || 0) + freshByChannel[otherKey]);
            setChatChannelUnreadLatest(otherKey, latestSenderByChannel[otherKey] || chatUnreadLatestByChannel[otherKey] || "");
          }}
          setChatChannelUnread(activeChatChannel, 0);
          setChatChannelUnreadLatest(activeChatChannel, "");
        }} else {{
          if (freshByChannel.all > 0) {{
            setChatChannelUnread("all", Number(chatUnreadByChannel.all || 0) + freshByChannel.all);
            setChatChannelUnreadLatest("all", latestSenderByChannel.all || chatUnreadLatestByChannel.all || "");
          }}
          if (freshByChannel.direct > 0) {{
            setChatChannelUnread("direct", Number(chatUnreadByChannel.direct || 0) + freshByChannel.direct);
            setChatChannelUnreadLatest("direct", latestSenderByChannel.direct || chatUnreadLatestByChannel.direct || "");
          }}
        }}
      }}
      syncChatRailUnread();

      const messageIndex = new Map();
      for (const msg of baseMessages) {{
        const msgId = messageIdOf(msg);
        if (msgId) {{
          messageIndex.set(String(msgId), msg);
        }}
      }}
      for (const msg of baseMessages) {{
        const key = classifyMessageChannel(msg);
        if (key === "direct") {{
          channelCounts.direct += 1;
        }} else {{
          channelCounts.all += 1;
        }}
      }}

      const channelList = document.getElementById("chat-channel-list");
      if (channelList) {{
        channelList.innerHTML = [
          {{ key: "all", label: "Everyone", count: channelCounts.all }},
          {{ key: "direct", label: "Peer-to-peer", count: channelCounts.direct }},
        ].map((entry) => {{
          const unread = Math.max(0, Number(chatUnreadByChannel[entry.key] || 0));
          const unreadLabel = unread > 99 ? "99+" : String(unread);
          const unreadFrom = String(chatUnreadLatestByChannel[entry.key] || "").trim();
          const unreadFromLine = (unread > 0 && unreadFrom)
            ? `<span class="chat-channel-unread-from" title="Latest unread from ${{escAttr(unreadFrom)}}">new: ${{escAttr(unreadFrom)}}</span>`
            : "";
          return `<button type="button" class="chat-channel-item${{activeChatChannel === entry.key ? " active" : ""}}" data-channel="${{entry.key}}">
            <span class="chat-channel-main">
              <span class="chat-channel-name">${{entry.label}}</span>
              ${{unreadFromLine}}
            </span>
            <span class="chat-channel-meta-wrap">
              <span class="chat-channel-meta">${{entry.count}}</span>
              ${{unread > 0 ? `<span class="chat-channel-unread" title="${{unread}} unread">${{unreadLabel}}</span>` : ""}}
            </span>
          </button>`;
        }}).join("");
        for (const btn of channelList.querySelectorAll(".chat-channel-item")) {{
          if (!(btn instanceof HTMLButtonElement)) continue;
          btn.addEventListener("click", () => {{
            applyChatChannel(btn.dataset.channel || "all", true);
          }});
        }}
      }}

      const messages = baseMessages.filter((msg) => classifyMessageChannel(msg) === activeChatChannel);
      const feedItems = messages.map((msg) => {{
        const sourceNode = normalizeNodeId(msg.from);
        const fallbackNode = normalizeNodeId(msg.to);
        const primarySelectable = isSelectableNodeId(sourceNode) ? sourceNode : "";
        const fallbackSelectable = isSelectableNodeId(fallbackNode) ? fallbackNode : "";
        const nodeId = primarySelectable || fallbackSelectable;
        const selectableClass = nodeId ? "chat-selectable" : "";
        const fromMeta = chatEndpointParts(sourceNode);
        const toMeta = chatEndpointParts(fallbackNode);
        const msgTimeUnix = parseDashboardTimeToUnix(msg.rx_time || msg.captured_at || "");
        touchParticipant(fromMeta, msgTimeUnix);
        if (activeChatChannel === "direct") {{
          touchParticipant(toMeta, msgTimeUnix);
          touchNodeById(sourceNode, msgTimeUnix);
          touchNodeById(fallbackNode, msgTimeUnix);
        }}
        const timeText = msg.rx_time || msg.captured_at || "n/a";
        const textHtml = escapeChatText(msg.text || "");
        const textCompact = compactInlineMessage(msg.text || "", 140);
        const hopNum = Number(msg.hops);
        const hasHop = Number.isFinite(hopNum) && hopNum >= 0;
        const hopStart = Number(msg.hop_start ?? msg.hopStart);
        const hopLimit = Number(msg.hop_limit ?? msg.hopLimit);
        const hopLabel = hasHop
          ? `${{Math.trunc(hopNum)}} hop${{Math.trunc(hopNum) === 1 ? "" : "s"}}`
          : "";
        const hopTitle = (
          Number.isFinite(hopStart) && Number.isFinite(hopLimit)
            ? `hopStart=${{Math.trunc(hopStart)}}, hopLimit=${{Math.trunc(hopLimit)}}`
            : "Hop count"
        );
        const messageId = messageIdOf(msg);
        const canReply = Number.isInteger(messageId) && messageId > 0;
        const replyToId = replyIdOf(msg);
        let replyPreview = "";
        if (Number.isInteger(replyToId) && replyToId > 0) {{
          const parentMsg = messageIndex.get(String(replyToId));
          if (parentMsg) {{
            const parentFromMeta = chatEndpointParts(normalizeNodeId(parentMsg.from || ""));
            const parentText = compactInlineMessage(parentMsg.text || "", 110);
            replyPreview = `<div class="chat-reply-inline" title="Reply to packet #${{replyToId}}">
              <span class="chat-reply-inline-label">Replying to ${{escAttr(parentFromMeta.label || "Unknown node")}}</span>
              <span class="chat-reply-inline-text">${{escAttr(parentText)}}</span>
            </div>`;
          }} else {{
            replyPreview = `<div class="chat-reply-inline missing" title="Reply to packet #${{replyToId}}">
              <span class="chat-reply-inline-label">Replying to packet #${{replyToId}}</span>
            </div>`;
          }}
        }}
        const messageReactions = messageId ? reactionBuckets.get(String(messageId)) : null;
        const reactionChips = messageReactions
          ? Array.from(messageReactions.values())
              .sort((a, b) => (b.count - a.count) || String(a.emoji).localeCompare(String(b.emoji)))
              .map((bucket) => {{
                const reactorNames = Array.from(new Set(bucket.names)).slice(0, 40);
                const aria = `${{bucket.emoji}} reaction, ${{bucket.count}} total`;
                return `<button type="button" class="chat-reaction-chip" data-reply-id="${{escAttr(messageId)}}" data-emoji="${{escAttr(bucket.emoji)}}" data-reactor-count="${{escAttr(bucket.count)}}" data-reactors="${{escAttr(JSON.stringify(reactorNames))}}" aria-label="${{escAttr(aria)}}">
                  <span class="chat-reaction-emoji">${{escAttr(bucket.emoji)}}</span><span class="chat-reaction-count">${{bucket.count}}</span>
                </button>`;
              }})
              .join("")
          : "";
        const isLocalEcho = msg.local_echo === true || msg.localEcho === true;
        const deliveryState = normalizeDeliveryState(msg.delivery_state ?? msg.deliveryState);
        const deliveryError = String(msg.delivery_error ?? msg.deliveryError ?? "").trim();
        const deliveryLabel = isLocalEcho ? deliveryStateLabel(deliveryState) : "";
        const deliveryTitle = isLocalEcho ? deliveryStateTitle(deliveryState, deliveryError) : "";
        const deliveryChip = (isLocalEcho && deliveryLabel)
          ? `<span class="chat-delivery-pill state-${{escAttr(deliveryState)}}" title="${{escAttr(deliveryTitle)}}">${{escAttr(deliveryLabel)}}</span>`
          : "";
        const retryReplyId = Number.isInteger(replyToId) && replyToId > 0 ? replyToId : "";
        const replyButton = canReply
          ? `<button type="button" class="chat-reply-btn" data-message-id="${{escAttr(messageId)}}" title="Reply to this message">Reply</button>`
          : "";
        const reactButton = messageId
          ? `<button type="button" class="chat-react-btn" data-reply-id="${{escAttr(messageId)}}" title="React to this message">😊+</button>`
          : "";
        const retryButton = (
          isLocalEcho
          && isRetryableDeliveryState(deliveryState)
          && String(msg.text || "").trim()
        )
          ? `<button type="button" class="chat-retry-btn" data-retry-text="${{escAttr(String(msg.text || ""))}}" data-retry-destination="${{escAttr(String(msg.to || "^all"))}}" data-retry-channel="${{escAttr(msg.channel ?? 0)}}" data-retry-reply-id="${{escAttr(retryReplyId)}}" data-retry-of="${{escAttr(messageId || "")}}" title="Retry this message">Retry</button>`
          : "";
        const reactionRow = reactionChips
          ? `<div class="chat-reaction-row">${{reactionChips}}</div>`
          : "";
        return `<div data-node-id="${{escAttr(nodeId)}}" data-message-id="${{escAttr(messageId || "")}}" data-reply-name="${{escAttr(fromMeta.label || "Unknown node")}}" data-reply-text="${{escAttr(textCompact)}}" class="chat-feed-item ${{selectableClass}}">
          <div class="chat-feed-meta">
            <span class="chat-endpoint" title="${{escAttr(fromMeta.title)}}">
              <span class="chat-name status-${{fromMeta.status}}">${{escAttr(fromMeta.label)}}</span>
              ${{fromMeta.metaHtml ? `<span class="chat-name-meta">${{fromMeta.metaHtml}}</span>` : ""}}
              ${{fromMeta.idTag ? `<span class="chat-id-bg status-${{fromMeta.status}}">${{escAttr(fromMeta.idTag)}}</span>` : ""}}
            </span>
            <span class="chat-feed-arrow">&rarr;</span>
            <span class="chat-endpoint" title="${{escAttr(toMeta.title)}}">
              <span class="chat-name status-${{toMeta.status}}">${{escAttr(toMeta.label)}}</span>
              ${{toMeta.metaHtml ? `<span class="chat-name-meta">${{toMeta.metaHtml}}</span>` : ""}}
              ${{toMeta.idTag ? `<span class="chat-id-bg status-${{toMeta.status}}">${{escAttr(toMeta.idTag)}}</span>` : ""}}
            </span>
            ${{hasHop ? `<span class="chat-feed-hops" title="${{escAttr(hopTitle)}}">${{escAttr(hopLabel)}}</span>` : ""}}
            <span class="chat-feed-actions">${{replyButton}}${{reactButton}}${{retryButton}}</span>
            ${{deliveryChip}}
            <span class="chat-feed-time">${{escAttr(timeText)}}</span>
          </div>
          ${{replyPreview}}
          <div class="chat-feed-text${{canReply ? " chat-reply-trigger" : ""}}"${{canReply ? ` title="Click to reply to this message"` : ""}}>${{textHtml || "&nbsp;"}}</div>
          ${{reactionRow}}
        </div>`;
      }});
      if (activeChatChannel === "all" && participants.size === 0) {{
        for (const msg of baseMessages) {{
          if (classifyMessageChannel(msg) !== "all") continue;
          touchNodeById(msg.from, parseDashboardTimeToUnix(msg.rx_time || msg.captured_at || ""));
        }}
      }}
      if (activeChatChannel === "direct" && isSelectableNodeId(selectedNodeId)) {{
        touchNodeById(selectedNodeId);
      }}
      const feed = document.getElementById("chat-feed");
      if (feed) {{
        closeReactionPopover(true);
        feed.innerHTML = feedItems.length > 0
          ? feedItems.join("")
          : `<div class="chat-feed-empty">No ${{channelLabel(activeChatChannel).toLowerCase()}} messages yet.</div>`;
      }}

      const roomList = document.getElementById("chat-room-list");
      const roster = Array.from(participants.values())
        .sort((a, b) => {{
          const rankDiff = statusRank(a.status) - statusRank(b.status);
          if (rankDiff !== 0) return rankDiff;
          const aTime = a.lastMessageUnix || 0;
          const bTime = b.lastMessageUnix || 0;
          if (aTime !== bTime) return bTime - aTime;
          return String(a.name || a.id).localeCompare(String(b.name || b.id));
        }})
        .slice(0, chatRosterMaxEntries);
      const rosterQuery = normalizeSearchQuery(chatUserSearchQuery);
      const rosterFiltered = roster.filter((item) => (
        matchesIdOrNameQuery(item.id, item.name, rosterQuery)
      ));
      const onlineCount = roster.filter((item) => item.status === "online").length;
      const warnCount = roster.filter((item) => item.status === "warn").length;
      const staleCount = roster.filter((item) => item.status === "stale").length;
      if (roomList) {{
        roomList.innerHTML = rosterFiltered.length > 0
          ? rosterFiltered.map((item) => (
              (() => {{
                const meta = nodeIdentityMeta(item.id);
                const memberTitle = `${{item.name}} (${{item.id}})${{meta.title ? ` - ${{meta.title}}` : ""}}`;
                return `<div class="chat-member-item status-${{item.status}}${{selectedNodeId === item.id ? " selected-node" : ""}}" data-node-id="${{escAttr(item.id)}}" title="${{escAttr(memberTitle)}}">
                <span class="chat-member-status status-${{item.status}}">●</span>
                <span class="chat-member-main">
                  <span class="chat-member-name-row">
                    <span class="chat-member-name-left">
                      <span class="chat-member-name status-${{item.status}}">${{escAttr(item.name)}}</span>
                      ${{meta.html ? `<span class="chat-name-meta">${{meta.html}}</span>` : ""}}
                    </span>
                    ${{favoriteToggleButtonHtml(item.id, "chat-favorite-btn")}}
                  </span>
                  <span class="chat-member-id">${{escAttr(item.id)}}</span>
                </span>
              </div>`;
              }})()
            )).join("")
          : (rosterQuery
              ? '<div class="chat-member-empty">No users match this search.</div>'
              : "");
        for (const member of roomList.querySelectorAll(".chat-member-item")) {{
          member.addEventListener("click", () => {{
            selectNode(member.dataset.nodeId || "", true);
          }});
        }}
      }}
      const leftSub = document.getElementById("chat-left-sub");
      if (leftSub) {{
        leftSub.textContent = `${{channelLabel(activeChatChannel)}}: ${{onlineCount}} online, ${{warnCount}} aging, ${{staleCount}} stale`;
      }}

      renderChatReplyContext();
      bindChatAutoScroll();
      bindChatFeedClicks();
      bindChatReactionControls();
      bindChatRetryControls();
      highlightNodeSelection();
      if (pendingSelectionScroll) {{
        scrollSelectionIntoView();
      }} else if (chatScroller instanceof HTMLElement && shouldStickBottom) {{
        requestAnimationFrame(() => {{
          chatScroller.scrollTop = chatScroller.scrollHeight;
          chatStickToBottom = true;
        }});
      }}

      const caption = document.getElementById("chat-caption");
      if (caption) {{
        const preset = s.modem_preset || "unknown";
        caption.textContent = `LoRa preset: ${{preset}}. Channel: ${{channelLabel(activeChatChannel)}}. ${{onlineCount}} online, ${{warnCount}} aging, ${{staleCount}} stale.`;
      }}
    }}

    function renderPackets(traffic) {{
      const packets = (traffic.recent_packets || []).slice().reverse().slice(0, 120);
      const rows = packets.map((entry) => {{
        const s = entry.summary || {{}};
        const text = s.decoded_text == null ? "" : String(s.decoded_text);
        return `<tr>
          <td data-sort="${{escAttr(s.captured_at || "")}}">${{s.captured_at || "n/a"}}</td>
          <td data-sort="${{escAttr(s.from || "")}}">${{s.from || "n/a"}}</td>
          <td data-sort="${{escAttr(s.to || "")}}">${{s.to || "n/a"}}</td>
          <td data-sort="${{escAttr(s.portnum || "")}}">${{s.portnum || "n/a"}}</td>
          <td data-sort="${{escAttr(s.rx_snr ?? "")}}">${{s.rx_snr ?? "n/a"}}</td>
          <td data-sort="${{escAttr(s.rx_rssi ?? "")}}">${{s.rx_rssi ?? "n/a"}}</td>
          <td data-sort="${{escAttr(text)}}">${{text}}</td>
        </tr>`;
      }});
      fillTable("packets-table", rows);
    }}

    function setRaw(id, value) {{
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = JSON.stringify(value, null, 2);
    }}

    function renderRaw(state) {{
      setRaw("raw-my-info", state.my_info);
      setRaw("raw-metadata", state.metadata);
      setRaw("raw-local-config", (state.local_state || {{}}).local_config);
      setRaw("raw-module-config", (state.local_state || {{}}).module_config);
      setRaw("raw-channels", (state.local_state || {{}}).channels);
      setRaw("raw-nodes-full", state.nodes_full);
    }}

    async function poll() {{
      try {{
        const resp = await fetch("/api/state", {{ cache: "no-store" }});
        if (!resp.ok) throw new Error(`API ${{resp.status}}`);
        const state = await resp.json();
        latestState = state;
        let nodeHistory = null;
        if (mapDataFocus !== "activity" && isSelectableNodeId(selectedNodeId)) {{
          try {{
            nodeHistory = await fetchNodeHistory(selectedNodeId);
          }} catch (historyErr) {{
            renderNodeHistoryLoading(selectedNodeId);
            const caption = document.getElementById("node-history-caption");
            const historyErrorText = historyErr instanceof Error
              ? historyErr.message
              : String(historyErr || "unknown error");
            if (caption) {{
              caption.textContent = `History error for ${{selectedNodeId}}: ${{historyErrorText}}`;
            }}
          }}
        }}
        let onlineActivity = null;
        if (mapDataFocus === "activity") {{
          try {{
            onlineActivity = await fetchOnlineActivity(nodeHistoryHours);
          }} catch (activityErr) {{
            onlineActivity = {{
              error: activityErr instanceof Error
                ? activityErr.message
                : String(activityErr || "unknown error"),
            }};
          }}
        }}
        renderSummary(state);
        renderMap(state.nodes || [], (state.traffic || {{}}).edges || [], nodeHistory);
        renderNodes(state.nodes || []);
        renderTraffic(state.traffic || {{}}, state.nodes || [], nodeHistory, onlineActivity);
        renderChat(state);
        renderFavorites(state);
        renderSavedNodeDetails(state, nodeHistory);
        renderPackets(state.traffic || {{}});
        renderConsole(state.traffic || {{}});
        renderRaw(state);
      }} catch (err) {{
        setText("updated-at", `error: ${{err.message}}`);
        appendConsoleLine(`error|${{Date.now()}}|${{err.message}}`, `[poll error] ${{err.message}}`);
      }}
    }}

    loadStoredSelection();
    loadNodeNameCache();
    loadFavoriteNodes();
    loadSplitState();
    loadNetworkNodesSplitState();
    loadLayoutView();
    loadChatChannel();
    loadThemePreference();
    bindLayoutNav();
    renderSavedRailStatus();
    bindSplitters();
    bindNetworkNodeSplitter();
    bindSelectionControls();
    bindFavoriteToggleControls();
    bindFavoritesControls();
    bindNodeListSearchControls();
    bindConsoleControls();
    bindChatComposer();
    bindThemeToggle();
    bindKnownNodesMetricControl();
    bindChatAutoScroll();
    bindHistoryTabs();
    bindWheelPassthrough();
    renderSelectionStatus();
    if (isSelectableNodeId(selectedNodeId)) {{
      renderNodeHistoryLoading(selectedNodeId);
    }} else {{
      setMapDataMode("live");
    }}
    renderFavorites({{}});
    requestMapResize();

    poll();
    setInterval(poll, refreshMs);
  </script>
</body>
</html>
"""

