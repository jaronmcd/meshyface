#!/usr/bin/env python3
"""Simulate the dashboard on phone/tablet screens and audit each view for mobile layout problems.

Drives Chromium through Playwright with a real device profile (viewport, device pixel ratio,
touch, mobile user agent), walks the requested views through the normal view menu, saves a
screenshot per view, and records an audit: horizontal page overflow, elements poking past the
viewport edge, content clipped by ``overflow: hidden``, tap targets under 32 px, text under 11 px,
and how much of the screen the fixed chrome (topbar) consumes.

Examples::

    # Live host, iPhone + Pixel, every view, screenshots + report under benchmarks/mobile_preview/out
    .venv/bin/python scripts/mobile_preview.py --url http://dashboard-host:8877/

    # Local code (server on :8899) rendered with the live host's data
    .venv/bin/python scripts/mobile_preview.py --url http://127.0.0.1:8899/ --api-from http://dashboard-host:8877/

    # Poke at it yourself in a phone-sized window with touch emulation
    .venv/bin/python scripts/mobile_preview.py --url http://dashboard-host:8877/ --headed --device "iPhone 14"

Requires ``pip install playwright``; uses the system Chromium (``--browser``) or Playwright's own
bundled build when that is installed (``playwright install chromium``).
"""

from __future__ import annotations

import argparse
from html import escape
import json
import math
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeout
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - guidance only
    sys.stderr.write("playwright is not installed: run `.venv/bin/pip install playwright`\n")
    raise SystemExit(2)

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT_DIR / "benchmarks" / "mobile_preview" / "out"
DEFAULT_DEVICES = ("iPhone 14", "Pixel 7")
DEFAULT_VIEWS = (
    "chat",
    "network:map",
    "network:overview",
    "network:graph",
    "network:top10",
    "network:sensors",
    "console",
    "games",
    "files",
    "scripts",
    "settings",
)
NETWORK_VIEWS = {"map", "overview", "graph", "routes", "top10", "sensors", "diagnostics"}
MAIN_VIEWS = {"chat", "network", "console", "settings"}
APP_VIEWS = {"games", "files", "scripts"}
BROWSER_CANDIDATES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome")

AUDIT_JS = r"""
() => {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const doc = document.documentElement;
  const describe = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += "#" + el.id;
    else if (el.classList.length) s += "." + Array.from(el.classList).slice(0, 2).join(".");
    return s;
  };
  const textOf = (el) => (el.textContent || "").replace(/\s+/g, " ").trim().slice(0, 40);
  const hidden = (el, cs) => cs.display === "none" || cs.visibility === "hidden" || el.closest("[hidden]");
  const overflowRaw = [];
  const smallTargets = [];
  const smallText = [];
  const clippedX = [];
  const hScrollers = [];
  let elementCount = 0;
  for (const el of document.body.querySelectorAll("*")) {
    if (el instanceof SVGElement && !(el instanceof SVGSVGElement)) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.bottom < 0 || r.top > vh) continue;
    const cs = getComputedStyle(el);
    if (hidden(el, cs)) continue;
    // Ancestor scrollers and clipping containers can intentionally hide off-screen content.
    const visible = { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
    for (let parent = el.parentElement; parent; parent = parent.parentElement) {
      const pcs = getComputedStyle(parent);
      const pr = parent.getBoundingClientRect();
      if (["hidden", "clip", "auto", "scroll"].includes(pcs.overflowX)) {
        visible.left = Math.max(visible.left, pr.left);
        visible.right = Math.min(visible.right, pr.right);
      }
      if (["hidden", "clip", "auto", "scroll"].includes(pcs.overflowY)) {
        visible.top = Math.max(visible.top, pr.top);
        visible.bottom = Math.min(visible.bottom, pr.bottom);
      }
    }
    if (visible.right <= visible.left || visible.bottom <= visible.top) continue;
    elementCount += 1;
    if (visible.right > vw + 1 || visible.left < -1) {
      overflowRaw.push({ el, sel: describe(el), left: Math.round(r.left), right: Math.round(r.right), width: Math.round(r.width) });
    }
    if (el.matches("button, a[href], input:not([type=hidden]), select, textarea, [role=button], [role=tab], [role=menuitem], [role=menuitemradio]")) {
      const w = Math.round(r.width);
      const h = Math.round(r.height);
      if (w < 32 || h < 32) smallTargets.push({ sel: describe(el), w, h, text: textOf(el) || el.getAttribute("aria-label") || el.getAttribute("title") || "" });
    }
    const fs = parseFloat(cs.fontSize);
    if (fs && fs < 11) {
      const hasText = Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim());
      if (hasText) smallText.push({ sel: describe(el), px: Math.round(fs * 10) / 10, text: textOf(el) });
    }
    if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0) {
      const ox = cs.overflowX;
      const entry = { sel: describe(el), clientWidth: el.clientWidth, scrollWidth: el.scrollWidth };
      if (ox === "auto" || ox === "scroll") hScrollers.push(entry);
      else if (ox === "hidden" || ox === "clip") clippedX.push(entry);
    }
  }
  // Report only the outermost overflowing elements: a child of a flagged element adds no information.
  const flagged = new Set(overflowRaw.map((o) => o.el));
  const overflow = overflowRaw
    .filter((o) => { let p = o.el.parentElement; while (p) { if (flagged.has(p)) return false; p = p.parentElement; } return true; })
    .map(({ el, ...rest }) => rest);
  const topbar = document.querySelector(".topbar");
  const layout = document.getElementById("dashboard-layout");
  const topbarRect = topbar ? topbar.getBoundingClientRect() : null;
  const layoutRect = layout ? layout.getBoundingClientRect() : null;
  const fontSizes = {};
  for (const item of smallText) fontSizes[item.px] = (fontSizes[item.px] || 0) + 1;
  return {
    viewport: { width: vw, height: vh, dpr: window.devicePixelRatio },
    documentScrollWidth: doc.scrollWidth,
    documentScrollHeight: doc.scrollHeight,
    horizontalPageOverflow: doc.scrollWidth > vw + 1,
    topbarHeight: topbarRect ? Math.round(topbarRect.height) : null,
    topbarFraction: topbarRect ? Math.round((topbarRect.height / vh) * 1000) / 1000 : null,
    layoutTop: layoutRect ? Math.round(layoutRect.top) : null,
    layoutHeight: layoutRect ? Math.round(layoutRect.height) : null,
    layoutWidth: layoutRect ? Math.round(layoutRect.width) : null,
    visibleElements: elementCount,
    overflowCount: overflow.length,
    overflow: overflow.slice(0, 25),
    clippedXCount: clippedX.length,
    clippedX: clippedX.slice(0, 25),
    hScrollerCount: hScrollers.length,
    hScrollers: hScrollers.slice(0, 25),
    smallTargetCount: smallTargets.length,
    smallTargets: smallTargets.slice(0, 40),
    smallTextCount: smallText.length,
    smallTextSizes: fontSizes,
    smallText: smallText.slice(0, 25),
  };
}
"""


@dataclass
class ViewResult:
    device: str
    view: str
    screenshot: str | None = None
    ok: bool = False
    error: str | None = None
    switch_ms: float | None = None
    audit: dict = field(default_factory=dict)
    console_errors: list[str] = field(default_factory=list)


@dataclass
class ViewSpec:
    raw: str
    main: str
    sub: str | None

    @classmethod
    def parse(cls, raw: str) -> "ViewSpec":
        clean = raw.strip().lower()
        main, _, sub = clean.partition(":")
        if sub and (main != "network" or sub not in NETWORK_VIEWS):
            raise ValueError(f"unknown subview in {raw!r}")
        if main in APP_VIEWS:
            return cls(raw=clean, main=main, sub=None)
        if main not in MAIN_VIEWS:
            raise ValueError(f"unknown view {raw!r}; use one of {sorted(MAIN_VIEWS | APP_VIEWS)} or network:<subview>")
        if main == "network" and not sub:
            sub = "map"
        return cls(raw=clean, main=main, sub=sub or None)

    @property
    def layout_class(self) -> str:
        return f"view-{self.main}"

    @property
    def file_stem(self) -> str:
        return self.raw.replace(":", "-")


def find_browser(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    for name in BROWSER_CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


def parse_device(playwright, spec: str, *, landscape: bool) -> tuple[str, dict]:
    """Return (label, context kwargs) for a Playwright device name or WxH[@dpr]."""
    if spec in playwright.devices:
        descriptor = dict(playwright.devices[spec])
        if landscape and f"{spec} landscape" in playwright.devices:
            descriptor = dict(playwright.devices[f"{spec} landscape"])
        elif landscape:
            vp = descriptor["viewport"]
            descriptor["viewport"] = {"width": vp["height"], "height": vp["width"]}
        return spec, descriptor
    size, _, dpr = spec.partition("@")
    width, _, height = size.lower().partition("x")
    if not (width.isdigit() and height.isdigit()):
        raise ValueError(f"unknown device {spec!r}; use a Playwright device name (e.g. 'iPhone 14', 'Pixel 7', 'iPad Mini') or WxH[@dpr]")
    w, h = int(width), int(height)
    scale = float(dpr) if dpr else 2.0
    if w <= 0 or h <= 0 or not math.isfinite(scale) or scale <= 0:
        raise ValueError("viewport dimensions and device scale must be positive and finite")
    if landscape:
        w, h = h, w
    return spec, {
        "viewport": {"width": w, "height": h},
        "device_scale_factor": scale,
        "is_mobile": True,
        "has_touch": True,
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Mobile Safari/537.36"
        ),
    }


def slug(text: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")


def context_options(args, descriptor: dict) -> dict:
    options = dict(descriptor)
    if args.color_scheme:
        options["color_scheme"] = args.color_scheme
    return options


def preset_local_storage(context, args) -> None:
    """Seed the dashboard's persisted preferences so a run matches a particular phone's state.

    The node roster, for example, starts collapsed on narrow screens only when nothing is stored;
    a phone whose user once tapped the expand toggle keeps it open, which changes the whole layout.
    """
    presets: dict[str, str] = {}
    if args.node_list == "collapsed":
        presets["meshDashboardChatPanelCollapsedV1"] = "1"
    elif args.node_list == "expanded":
        presets["meshDashboardChatPanelCollapsedV1"] = "0"
    for item in args.local_storage:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"--local-storage expects KEY=VALUE, got {item!r}")
        presets[key.strip()] = value
    if not presets:
        return
    context.add_init_script(
        "(() => { const presets = " + json.dumps(presets) + "; try { for (const [key, value] of Object.entries(presets)) "
        "window.localStorage.setItem(key, value); } catch (err) {} })();"
    )


def install_api_proxy(context, api_from: str) -> None:
    """Answer the page's ``/api/*`` reads from another running dashboard.

    Only GET/HEAD requests are forwarded, so a preview can never change the other dashboard's
    settings; writes (theme saves, sends, restarts) still go to the server under test. Conditional
    headers are dropped because Chromium cannot replay a 304 through request interception.
    """
    base = api_from.rstrip("/")
    conditional = {"if-none-match", "if-modified-since"}

    def handle(route, request):
        if request.method not in {"GET", "HEAD"}:
            route.continue_()
            return
        parts = urlsplit(request.url)
        target = base + parts.path + (f"?{parts.query}" if parts.query else "")
        headers = {k: v for k, v in request.headers.items() if k.lower() not in conditional}
        try:
            response = route.fetch(url=target, headers=headers)
            route.fulfill(response=response)
        except PlaywrightError as err:
            try:
                route.abort("failed")
            except PlaywrightError:
                pass
            if "disposed" not in str(err):  # an in-flight poll when the context closes is expected
                sys.stderr.write(f"api proxy failed for {parts.path}: {str(err).splitlines()[0]}\n")

    context.route("**/api/**", handle)


def wait_for_boot(page, timeout_ms: int) -> None:
    page.wait_for_function("() => window.__meshDashboardBootComplete === true", timeout=timeout_ms)
    page.wait_for_function(
        "() => !!document.getElementById('dashboard-layout')",
        timeout=timeout_ms,
    )


def click_reliably(page, selector: str, timeout_ms: int = 4000) -> None:
    """Click like a user would; fall back to a DOM click when Playwright's actionability check stalls.

    The topbar view menu animates and re-layouts while open, which can keep the native click
    waiting for the element to be "stable" until it times out, so the native attempt is capped.
    """
    locator = page.locator(selector).first
    locator.wait_for(state="attached", timeout=timeout_ms)
    try:
        locator.click(timeout=min(timeout_ms, 2500))
    except (PlaywrightTimeout, PlaywrightError):
        locator.evaluate("el => el.click()")


def require_rendered(page, selector: str, what: str) -> None:
    """Raise immediately when a menu entry exists but is not rendered (feature disabled on this server)."""
    rendered = page.locator(selector).first.evaluate("el => !el.hidden && el.offsetWidth > 0 && el.offsetHeight > 0")
    if not rendered:
        raise ValueError(f"{what} is not available on this server (feature disabled?)")


def switch_view(page, spec: ViewSpec, *, timeout_ms: int) -> None:
    layout = page.locator("#dashboard-layout")
    already_there = spec.layout_class in (layout.get_attribute("class") or "").split()
    if not already_there:
        click_reliably(page, "#layout-view-menu-btn", timeout_ms)
        try:
            page.locator("#layout-view-menu").wait_for(state="visible", timeout=timeout_ms)
        except PlaywrightTimeout:
            pass
        if spec.main in APP_VIEWS:
            # Hovering the Apps entry opens its submenu (which then covers the entry, so a native
            # click can never complete); the entry itself is a toggle, so click it only if hover failed.
            apps_trigger = page.locator('#layout-view-menu .topbar-view-menu-item[data-submenu="apps"]').first
            submenu = page.locator("#layout-view-menu-apps-submenu")
            if not submenu.is_visible():
                try:
                    apps_trigger.hover(timeout=2500)
                    submenu.wait_for(state="visible", timeout=1000)
                except (PlaywrightTimeout, PlaywrightError):
                    pass
            if not submenu.is_visible():
                apps_trigger.evaluate("el => el.click()")
                try:
                    submenu.wait_for(state="visible", timeout=1500)
                except PlaywrightTimeout:
                    pass
            item = f'#layout-view-menu-apps-submenu .topbar-view-submenu-item[data-app-view="{spec.main}"]'
            if submenu.is_visible():
                require_rendered(page, item, f"the {spec.main} view")
            page.locator(item).first.evaluate("el => el.click()")
        else:
            item = f'#layout-view-menu .topbar-view-menu-item[data-view="{spec.main}"]'
            require_rendered(page, item, f"the {spec.main} view")
            click_reliably(page, item, timeout_ms)
        page.wait_for_function(
            "cls => document.getElementById('dashboard-layout')?.classList.contains(cls)",
            arg=spec.layout_class,
            timeout=timeout_ms,
        )
    if spec.main == "network" and spec.sub:
        click_reliably(page, f'.network-map-subview-tab[data-network-subview="{spec.sub}"]', timeout_ms)
        page.wait_for_function(
            "sub => document.querySelector(`.network-map-subview-tab[data-network-subview='${sub}']`)?.classList.contains('is-active')",
            arg=spec.sub,
            timeout=timeout_ms,
        )
    # Dismiss the launcher menu if it stayed open (it overlays the view in the screenshot).
    page.evaluate("() => { const m = document.getElementById('layout-view-menu'); if (m && !m.hidden) document.body.click(); }")


def run_headed(playwright, args, browser_path: str | None) -> int:
    label, descriptor = parse_device(playwright, args.device[0], landscape=args.landscape)
    launch_kwargs = {"headless": False, "args": list(args.browser_arg)}
    if browser_path:
        launch_kwargs["executable_path"] = browser_path
    browser = playwright.chromium.launch(**launch_kwargs)
    try:
        context = browser.new_context(**context_options(args, descriptor))
        preset_local_storage(context, args)
        if args.api_from:
            install_api_proxy(context, args.api_from)
        page = context.new_page()
        if args.cpu_throttle and args.cpu_throttle > 1:
            context.new_cdp_session(page).send("Emulation.setCPUThrottlingRate", {"rate": args.cpu_throttle})
        page.goto(args.url, timeout=args.timeout * 1000)
        vp = descriptor["viewport"]
        print(f"{label}: {vp['width']}x{vp['height']} @{descriptor.get('device_scale_factor', 1)}x, touch on. Close the browser window or press Ctrl-C to stop.")
        try:
            while not page.is_closed():
                page.wait_for_timeout(500)
        except (KeyboardInterrupt, PlaywrightError):
            pass
    finally:
        browser.close()
    return 0


def audit_device(playwright, args, browser_path: str | None, device_spec: str, views: list[ViewSpec], out_dir: Path) -> list[ViewResult]:
    label, descriptor = parse_device(playwright, device_spec, landscape=args.landscape)
    device_slug = slug(label + ("-landscape" if args.landscape else ""))
    launch_kwargs = {"headless": True, "args": list(args.browser_arg)}
    if browser_path:
        launch_kwargs["executable_path"] = browser_path
    browser = playwright.chromium.launch(**launch_kwargs)
    results: list[ViewResult] = []
    try:
        context = browser.new_context(**context_options(args, descriptor))
        preset_local_storage(context, args)
        if args.api_from:
            install_api_proxy(context, args.api_from)
        page = context.new_page()
        if args.cpu_throttle and args.cpu_throttle > 1:
            context.new_cdp_session(page).send("Emulation.setCPUThrottlingRate", {"rate": args.cpu_throttle})
        console_errors: list[str] = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(f"pageerror: {err}"))
        page.on(
            "response",
            lambda resp: console_errors.append(f"HTTP {resp.status} {resp.request.method} {urlsplit(resp.url).path}")
            if resp.status >= 400
            else None,
        )
        try:
            page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
            wait_for_boot(page, args.timeout * 1000)
            page.wait_for_timeout(args.settle_ms)
        except PlaywrightError as err:
            return [ViewResult(device=label, view="boot", error=str(err).splitlines()[0][:300],
                               console_errors=list(dict.fromkeys(console_errors))[:10])]
        vp = descriptor["viewport"]
        print(f"[{label}] {vp['width']}x{vp['height']} @{descriptor.get('device_scale_factor', 1)}x booted")
        for spec in views:
            result = ViewResult(device=label, view=spec.raw)
            started = time.perf_counter()
            try:
                switch_view(page, spec, timeout_ms=args.timeout * 1000)
                result.switch_ms = round((time.perf_counter() - started) * 1000, 1)
                page.wait_for_timeout(args.settle_ms)
                shot = out_dir / f"{device_slug}--{spec.file_stem}.png"
                page.screenshot(path=str(shot), full_page=args.full_page)
                result.screenshot = str(shot.relative_to(out_dir))
                result.audit = page.evaluate(AUDIT_JS)
                result.ok = True
            except (PlaywrightTimeout, PlaywrightError, ValueError) as err:
                result.error = str(err).splitlines()[0][:300]
                try:
                    shot = out_dir / f"{device_slug}--{spec.file_stem}--error.png"
                    page.screenshot(path=str(shot))
                    result.screenshot = str(shot.relative_to(out_dir))
                except PlaywrightError:
                    pass
            result.console_errors = list(dict.fromkeys(console_errors))[:10]
            results.append(result)
            console_errors.clear()
            elapsed = time.perf_counter() - started
            print(f"  {spec.raw:<18} {'ok ' if result.ok else 'ERR'} {elapsed:5.1f}s  {summarize(result)}")
    finally:
        browser.close()
    return results


def summarize(result: ViewResult) -> str:
    if not result.ok:
        return result.error or "failed"
    a = result.audit
    bits = []
    if a.get("horizontalPageOverflow"):
        bits.append(f"PAGE OVERFLOW {a['documentScrollWidth']}px")
    if a.get("overflowCount"):
        bits.append(f"{a['overflowCount']} past edge")
    if a.get("clippedXCount"):
        bits.append(f"{a['clippedXCount']} clipped")
    if a.get("hScrollerCount"):
        bits.append(f"{a['hScrollerCount']} h-scroll")
    if a.get("smallTargetCount"):
        bits.append(f"{a['smallTargetCount']} small taps")
    if a.get("smallTextCount"):
        bits.append(f"{a['smallTextCount']} tiny text")
    if a.get("topbarFraction") is not None:
        bits.append(f"topbar {a['topbarHeight']}px ({round(a['topbarFraction'] * 100)}%)")
    if result.console_errors:
        bits.append(f"{len(result.console_errors)} console errors")
    return ", ".join(bits) or "clean"


def write_contact_sheet(out_dir: Path, results: list[ViewResult], args) -> Path:
    devices = list(dict.fromkeys(r.device for r in results))
    views = list(dict.fromkeys(r.view for r in results))
    by_key = {(r.device, r.view): r for r in results}
    rows = []
    for view in views:
        cells = []
        for device in devices:
            r = by_key.get((device, view))
            if r is None:
                cells.append("<td></td>")
                continue
            img = f'<a href="{escape(r.screenshot, quote=True)}"><img src="{escape(r.screenshot, quote=True)}" loading="lazy"></a>' if r.screenshot else ""
            status = "ok" if r.ok else "err"
            cells.append(f'<td class="{status}">{img}<div class="meta">{escape(summarize(r))}</div></td>')
        rows.append(f"<tr><th>{escape(view)}</th>{''.join(cells)}</tr>")
    html = f"""<!doctype html><meta charset="utf-8"><title>Mobile preview</title>
<style>
body{{font:13px system-ui,sans-serif;margin:16px;background:#f4f4f4;color:#111}}
table{{border-collapse:collapse}} th,td{{vertical-align:top;padding:8px;border:1px solid #ddd;background:#fff}}
th{{text-align:left;white-space:nowrap}} img{{width:300px;border:1px solid #999;display:block}}
td.err{{background:#fee}} .meta{{max-width:300px;margin-top:6px;color:#444}}
</style>
<h1>Mobile preview</h1>
<p>{escape(args.url)}{escape(' (API from ' + args.api_from + ')') if args.api_from else ''} · {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
<table><tr><th>view</th>{''.join(f'<th>{escape(d)}</th>' for d in devices)}</tr>{''.join(rows)}</table>
"""
    path = out_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    return path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8877/", help="Dashboard URL (default: local server on 8877).")
    parser.add_argument("--api-from", default=None, help="Proxy /api/* to this origin (e.g. the live host) so local code renders real data.")
    parser.add_argument("--device", action="append", default=None, help="Playwright device name or WxH[@dpr]; repeatable (default: iPhone 14 and Pixel 7).")
    parser.add_argument("--landscape", action="store_true", help="Rotate the device profile.")
    parser.add_argument("--color-scheme", choices=("light", "dark"), default=None, help="Emulate the phone's system theme (the dashboard follows it by default).")
    parser.add_argument("--node-list", choices=("default", "collapsed", "expanded"), default="default", help="Start with the chat node roster collapsed or expanded (default: whatever a fresh phone gets, collapsed at 760 px and under).")
    parser.add_argument("--local-storage", action="append", default=[], metavar="KEY=VALUE", help="Seed any other persisted dashboard preference; repeatable.")
    parser.add_argument("--views", default=",".join(DEFAULT_VIEWS), help="Comma-separated views; network subviews as network:<map|overview|graph|routes|top10|sensors>.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"Output directory (default: {DEFAULT_OUT.relative_to(ROOT_DIR)}).")
    parser.add_argument("--settle-ms", type=int, default=2500, help="Wait after boot and after each view switch before capturing.")
    parser.add_argument("--timeout", type=int, default=45, help="Seconds to wait for boot and view switches.")
    parser.add_argument("--full-page", action="store_true", help="Capture the whole scrollable page instead of the viewport.")
    parser.add_argument("--cpu-throttle", type=float, default=None, help="Chromium CPU throttle multiplier (4 ≈ mid-range phone).")
    parser.add_argument("--headed", action="store_true", help="Open a visible phone-sized browser for manual testing instead of auditing.")
    parser.add_argument("--browser", default=None, help="Chromium executable (default: system chromium, else Playwright's bundled build).")
    parser.add_argument("--browser-arg", action="append", default=["--no-sandbox"], help="Extra Chromium flag; repeatable.")
    args = parser.parse_args(argv)
    if args.timeout <= 0 or args.settle_ms < 0:
        parser.error("--timeout must be positive and --settle-ms must be nonnegative")
    if args.cpu_throttle is not None and (not math.isfinite(args.cpu_throttle) or args.cpu_throttle < 1):
        parser.error("--cpu-throttle must be finite and at least 1")
    if not any(view.strip() for view in args.views.split(",")):
        parser.error("--views must contain at least one view")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    args.device = args.device or list(DEFAULT_DEVICES)
    browser_path = find_browser(args.browser)
    views = [ViewSpec.parse(v) for v in args.views.split(",") if v.strip()]
    with sync_playwright() as playwright:
        if args.headed:
            return run_headed(playwright, args, browser_path)
        out_dir = args.out
        out_dir.mkdir(parents=True, exist_ok=True)
        results: list[ViewResult] = []
        for device_spec in args.device:
            results.extend(audit_device(playwright, args, browser_path, device_spec, views, out_dir))
    report = {
        "url": args.url,
        "api_from": args.api_from,
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": [
            {
                "device": r.device,
                "view": r.view,
                "ok": r.ok,
                "error": r.error,
                "switch_ms": r.switch_ms,
                "screenshot": r.screenshot,
                "console_errors": r.console_errors,
                "audit": r.audit,
            }
            for r in results
        ],
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    sheet = write_contact_sheet(out_dir, results, args)
    failures = [r for r in results if not r.ok]
    print(f"\nreport: {out_dir / 'report.json'}\ncontact sheet: {sheet}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
