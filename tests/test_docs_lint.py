import re
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_DOCS_DIR = _REPO_ROOT / "docs"
_DOC_FILES = sorted(path for path in _DOCS_DIR.glob("*.md") if path.name != "IDEAS.md")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\n]+)\)")
_DOC_STATUS_RE = re.compile(r"^Doc status:\s*[a-z0-9][a-z0-9-]*\s*$", re.MULTILINE)
_LAST_REVIEWED_RE = re.compile(r"^Last reviewed:\s*\d{4}-\d{2}-\d{2}\s*$", re.MULTILINE)
_TOP_LEVEL_PATH_TOKENS = {
    "README.md",
    "mesh_connection.py",
    "mesh_dashboard.py",
    "meshtastic-dashboard.service",
    "requirements-dev.txt",
}
_IN_REPO_PATH_PREFIXES = (
    ".github/",
    "archive/",
    "docs/",
    "meshdash/",
    "tests/",
)


def _normalize_token(raw_token: str) -> str:
    return raw_token.strip().strip(".,:;)")


def _candidate_repo_path(raw_token: str) -> str | None:
    token = _normalize_token(raw_token)
    if not token:
        return None
    if "*" in token:
        return None
    if "://" in token:
        return None
    if token.startswith(("/", "^", "!", "~")):
        return None
    if token.startswith(("<", "(")):
        return None
    if token in _TOP_LEVEL_PATH_TOKENS:
        return token
    for prefix in _IN_REPO_PATH_PREFIXES:
        if token.startswith(prefix):
            return token
    return None


def _iter_doc_reference_candidates(content: str):
    for raw in _INLINE_CODE_RE.findall(content):
        candidate = _candidate_repo_path(raw)
        if candidate is not None:
            yield candidate
    for raw in _MARKDOWN_LINK_RE.findall(content):
        candidate = _candidate_repo_path(raw)
        if candidate is not None:
            yield candidate


def test_docs_have_status_and_last_reviewed_headers():
    for path in _DOC_FILES:
        raw = path.read_text(encoding="utf-8")
        header = "\n".join(raw.splitlines()[:16])
        assert _DOC_STATUS_RE.search(header), f"{path} missing 'Doc status:' header"
        assert _LAST_REVIEWED_RE.search(header), f"{path} missing 'Last reviewed:' header"


def test_docs_in_repo_references_resolve():
    missing: list[tuple[str, str]] = []
    for doc_path in _DOC_FILES:
        raw = doc_path.read_text(encoding="utf-8")
        for token in _iter_doc_reference_candidates(raw):
            if not (_REPO_ROOT / token).exists():
                missing.append((str(doc_path), token))

    assert not missing, "Missing in-repo path references:\n" + "\n".join(
        f"{doc}: {token}" for doc, token in missing
    )
