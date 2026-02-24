from functools import lru_cache
from pathlib import Path


_ASSETS_DIR = Path(__file__).with_name("assets")


@lru_cache(maxsize=None)
def _load_asset_template(filename: str) -> str:
    return (_ASSETS_DIR / filename).read_text(encoding="utf-8")


def render_asset_template(filename: str, **values: object) -> str:
    rendered = _load_asset_template(filename)
    for key, value in values.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))
    # Asset templates were extracted from f-strings and still carry doubled
    # braces used for escaping in Python source. Collapse them back to the
    # literal single-brace form expected by CSS/JS/HTML.
    rendered = rendered.replace("{{", "{").replace("}}", "}")
    return rendered
