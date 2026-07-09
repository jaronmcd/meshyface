from pathlib import Path


def test_console_output_uses_syntax_highlighting() -> None:
    js_src = Path(
        "meshdash/assets/dashboard.js.chat.events.console.session.core.tmpl"
    ).read_text(encoding="utf-8")
    helpers_src = Path(
        "meshdash/assets/dashboard.js.chat.events.console.commands.helpers.tmpl"
    ).read_text(encoding="utf-8")
    ui_src = Path("meshdash/assets/dashboard.js.chat.events.console.ui.tmpl").read_text(
        encoding="utf-8"
    )
    poll_src = Path("meshdash/assets/dashboard.js.runtime.poll.tmpl").read_text(
        encoding="utf-8"
    )
    css_src = Path("meshdash/assets/dashboard.css.components.tmpl").read_text(
        encoding="utf-8"
    )

    assert "function consoleSyntaxHighlightLineHtml" in js_src
    assert "function consoleSyntaxKeyValueSegmentHtml" in js_src
    assert "function consoleSyntaxStatusTone" in js_src
    assert "function consoleSyntaxNodeTooltipText(rawNodeId)" in js_src
    assert "function consoleSyntaxEndpointKey(rawKey)" in js_src
    assert "function consoleSyntaxNodeIdFromEndpointValue(rawValue)" in js_src
    assert "function consoleSyntaxBroadcastSpan(rawValue)" in js_src
    assert "function consoleSyntaxSelfNodeId(state = latestState)" in js_src
    assert "function consoleSyntaxNodeTagEntry(nodeId)" in js_src
    assert "function consoleSyntaxNodeTagStyle(tagEntry)" in js_src
    assert "function consoleSyntaxNodeSpan(rawValue)" in js_src
    assert "function consoleSyntaxEndpointValueHtml(rawValue)" in js_src
    assert "function consoleSyntaxQuotedValueHtml(rawValue)" in js_src
    assert "function consoleSyntaxJsonKeyHtml(rawValue)" in js_src
    assert "function consoleSyntaxNodeTooltipStateSignature(state = latestState)" in js_src
    assert "function consoleSyntaxLooksLikeJsonSegment(rawValue)" in js_src
    assert "function consoleSyntaxLooksLikeNestedKeyValue(rawValue)" in js_src
    assert "function consoleSyntaxJsonLikeSegmentHtml(segment, depth = 0)" in js_src
    assert "function consoleSyntaxValueEndIndex(text, startIndex)" in js_src
    assert "function consoleSyntaxNextKeyValueMatch(text, startIndex = 0)" in js_src
    assert "function resolveConsolePromptRunningHint()" in js_src
    assert '" Ctrl+C or q to stop"' in js_src
    assert '" Ctrl+C to stop"' in js_src
    assert 'class="console-running-hint console-completion-ghost"' in js_src
    assert "resolveConsoleCachedNodeRow(nodeId, latestState)" in js_src
    assert "consoleNodeRowsCacheVersion" in js_src
    assert "visibleLines.map((line) => consoleSyntaxHighlightLineHtml(line))" in js_src
    assert "console-syntax-tag-${{tone}}" in js_src
    assert "console-syntax-node" in js_src
    assert "console-syntax-node-self" in js_src
    assert "console-syntax-node-tagged" in js_src
    assert "console-syntax-broadcast" in js_src
    assert "console-syntax-json-key console-syntax-key" in js_src
    assert "console-syntax-json-punct" in js_src
    assert "console-syntax-json-colon" in js_src
    assert 'data-node-id="${{escAttr(nodeId)}}"' in js_src
    assert 'class="${{escAttr(className)}}"' in js_src
    assert 'style="${{escAttr(tagStyle)}}"' in js_src
    assert 'resolveLocalNodeId(state || {{}})' in js_src
    assert 'classNames.push("console-syntax-node-self")' in js_src
    assert 'classNames.push("console-syntax-node-tagged")' in js_src
    assert 'nodeTagEntryForNode(cleanNodeId)' in js_src
    assert "nodeTagStyleVars(tagEntry)" in js_src
    assert 'title="${{escAttr(tooltip)}}"' in js_src
    assert 'return `!${{numeric.toString(16).padStart(8, "0").slice(-8)}}`;' in js_src
    assert 'if (numeric === 0xffffffff) return "^all";' in js_src
    assert "Broadcast target: all nodes" in js_src
    assert "hex: !ffffffff" in js_src
    assert "uint32: 4294967295" in js_src
    assert "formatConsoleNodeLookupDetails(row, 2)" in js_src
    assert "consoleSyntaxNodeTooltipCache = new Map();" in js_src
    assert "console-syntax-key" in js_src
    assert "console-syntax-status-${{statusTone}}" in js_src
    assert "consoleSyntaxNodeSpan(parts.inner)" in js_src
    assert "consoleSyntaxJsonLikeSegmentHtml(value, depth + 1)" in js_src
    assert "consoleSyntaxKeyValueSegmentHtml(value, depth + 1)" in js_src
    assert "consoleSyntaxValueHtml(token, depth + 1, jsonValueKey)" in js_src
    assert "consoleSyntaxValueHtml(match.value, depth + 1, match.key)" in js_src
    assert "consoleSyntaxJsonLikeSegmentHtml(text, depth + 1)" in js_src
    assert "consoleSyntaxValueEndIndex(text, valueStart)" in js_src

    assert "function refreshConsoleNodeRowsCache(state = latestState)" in helpers_src
    assert "function resolveConsoleCachedNodeRow(rawNodeId, state = latestState)" in helpers_src
    assert "consoleNodeRowsByIdCache.set(nodeId, merged);" in helpers_src
    assert "refreshConsoleNodeRowsCache(rawState);" in poll_src
    assert "refreshConsoleNodeRowsCache(state);" in poll_src

    assert "function selectConsoleNodeFromSyntax(rawNodeId)" in ui_src
    assert 'target.closest(".console-syntax-node[data-node-id]")' in ui_src
    assert "selectNode(nodeId, true, false);" in ui_src
    assert "chatNodeNavigatorFindRowForNodeId(nodeId)" in ui_src
    assert 'located.rowEl.scrollIntoView({{ block: "nearest", inline: "nearest" }});' in ui_src

    assert "#live-console .console-syntax-command" in css_src
    assert "#live-console .console-syntax-tag-mesh" in css_src
    assert "#live-console .console-syntax-node" in css_src
    assert "#live-console .console-syntax-node.console-syntax-node-self" in css_src
    assert "#live-console .console-syntax-node.console-syntax-node-tagged" in css_src
    assert "#live-console .console-syntax-broadcast" in css_src
    assert "cursor: pointer;" in css_src
    assert "text-decoration: underline dotted" in css_src
    assert "#live-console .console-syntax-key" in css_src
    assert "#live-console .console-syntax-status-ok" in css_src
    assert "#live-console .console-syntax-json-punct" in css_src
    assert "#live-console .console-syntax-json-colon" in css_src
    assert ".console-completion-ghost" in css_src
    assert "[data-theme=\"dark\"] .console-completion-ghost" in css_src
    assert ".console-autocomplete-menu" in css_src
    assert ".console-autocomplete-item.is-selected" in css_src
    assert ".console-autocomplete-item.is-node" in css_src
    assert ".console-autocomplete-node-icon" in css_src
    assert ".console-autocomplete-node-id" in css_src
    assert "[data-theme=\"dark\"] .console-autocomplete-menu" in css_src
    assert "[data-theme=\"dark\"] .console-autocomplete-node-icon" in css_src
    assert "[data-theme=\"dark\"] #live-console .console-syntax-command" in css_src
    assert (
        '[data-theme="dark"] #live-console '
        ".console-syntax-node.console-syntax-node-self"
    ) in css_src
    assert (
        '[data-theme="dark"] #live-console '
        ".console-syntax-node.console-syntax-node-tagged"
    ) in css_src
    assert '[data-theme="dark"] #live-console .console-syntax-broadcast' in css_src
    assert '[data-theme="dark"] #live-console .console-syntax-json-punct' in css_src
    assert '[data-theme="dark"] #live-console .console-syntax-json-colon' in css_src
    autocomplete_menu_style = css_src.split(".console-autocomplete-menu {{", 1)[
        1
    ].split("}}", 1)[0]
    dark_autocomplete_menu_style = css_src.split(
        '[data-theme="dark"] .console-autocomplete-menu {{', 1
    )[1].split("}}", 1)[0]
    assert "0 1px 2px rgba(0, 0, 0, 0.18)" in autocomplete_menu_style
    assert "0 1px 2px rgba(0, 0, 0, 0.24)" in dark_autocomplete_menu_style
    assert "var(--surface-tint-color)" not in autocomplete_menu_style
    assert "var(--surface-tint-color)" not in dark_autocomplete_menu_style
    assert "0 8px 18px" not in dark_autocomplete_menu_style
    assert "0 14px 30px" not in dark_autocomplete_menu_style
    mesh_tag_style = css_src.split("#live-console .console-syntax-tag-mesh {{", 1)[
        1
    ].split("}}", 1)[0]
    node_style = css_src.split("#live-console .console-syntax-node {{", 1)[1].split(
        "}}", 1
    )[0]
    self_node_style = css_src.split(
        "#live-console .console-syntax-node.console-syntax-node-self {{", 1
    )[1].split("}}", 1)[0]
    tagged_node_style = css_src.split(
        "#live-console .console-syntax-node.console-syntax-node-tagged {{", 1
    )[1].split("}}", 1)[0]
    broadcast_style = css_src.split("#live-console .console-syntax-broadcast {{", 1)[
        1
    ].split("}}", 1)[0]
    dark_mesh_tag_style = css_src.split(
        '[data-theme="dark"] #live-console .console-syntax-tag-mesh {{', 1
    )[1].split("}}", 1)[0]
    dark_node_style = css_src.split(
        '[data-theme="dark"] #live-console .console-syntax-node {{', 1
    )[1].split("}}", 1)[0]
    dark_self_node_style = css_src.split(
        '[data-theme="dark"] #live-console '
        ".console-syntax-node.console-syntax-node-self {{",
        1,
    )[1].split("}}", 1)[0]
    dark_tagged_node_style = css_src.split(
        '[data-theme="dark"] #live-console '
        ".console-syntax-node.console-syntax-node-tagged {{",
        1,
    )[1].split("}}", 1)[0]
    dark_broadcast_style = css_src.split(
        '[data-theme="dark"] #live-console .console-syntax-broadcast {{', 1
    )[1].split("}}", 1)[0]
    assert "#a21caf" in mesh_tag_style
    assert "#2563eb" in node_style
    assert "#db2777" in self_node_style
    assert "var(--node-tag-color, var(--accent))" in tagged_node_style
    assert "#0f766e" in broadcast_style
    assert "#f0abfc" in dark_mesh_tag_style
    assert "#93c5fd" in dark_node_style
    assert "#f9a8d4" in dark_self_node_style
    assert "var(--node-tag-color, var(--ui-accent))" in dark_tagged_node_style
    assert "#5eead4" in dark_broadcast_style
    assert "#2563eb" not in mesh_tag_style
    assert "#93c5fd" not in dark_mesh_tag_style
