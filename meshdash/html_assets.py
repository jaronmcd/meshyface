from pathlib import Path


_ASSETS_DIR = Path(__file__).with_name("assets")
_ASSET_TEMPLATE_CACHE: dict[str, tuple[int, str]] = {}


def _load_asset_template(filename: str) -> str:
    path = _ASSETS_DIR / filename
    stamp = path.stat().st_mtime_ns
    cached = _ASSET_TEMPLATE_CACHE.get(filename)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    content = path.read_text(encoding="utf-8")
    _ASSET_TEMPLATE_CACHE[filename] = (stamp, content)
    return content


def clear_asset_template_cache() -> None:
    _ASSET_TEMPLATE_CACHE.clear()


def render_asset_template(filename: str, **values: object) -> str:
    rendered = _load_asset_template(filename)
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))
    # Asset templates were extracted from f-strings and still carry doubled
    # braces used for escaping in Python source. Collapse them back to the
    # literal single-brace form expected by CSS/JS/HTML.
    rendered = rendered.replace("{{", "{").replace("}}", "}")
    return rendered
