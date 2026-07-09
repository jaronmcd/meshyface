import re
from pathlib import Path


def test_readme_local_docs_and_screenshots_exist() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    paths = set(re.findall(r"\]\((docs/(?:install|screenshots)/[^)#]+)\)", readme))

    assert paths
    missing = sorted(path for path in paths if not Path(path).exists())
    assert missing == []
