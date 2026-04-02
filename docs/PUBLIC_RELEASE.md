# Public Release Workflow

Doc status: active-runtime
Last reviewed: 2026-04-02

This repo can stay private for development while publishing a curated snapshot
to a separate public repo.

Use `scripts/release_public.sh` plus `.public-release-allowlist` to export only
approved files.

## One-time setup

1. Create your public GitHub repo.
2. Add it as a remote (recommended name: `public`):

```bash
git remote add public https://github.com/<you>/<public-repo>.git
```

## Curate what can go public

Edit `.public-release-allowlist` at repo root.

Rules:

- One repo-root-relative path per line.
- Blank lines and `# comments` are ignored.
- Keep this list explicit and minimal.

## Publish flow

Dry-run first:

```bash
./scripts/release_public.sh --source-branch meshyface-alpha --dry-run
```

Publish:

```bash
./scripts/release_public.sh --source-branch meshyface-alpha
```

Defaults:

- target remote: `public` (or `$PUBLIC_RELEASE_REMOTE`)
- target branch: `main` (or `$PUBLIC_RELEASE_BRANCH`)
- allowlist file: `.public-release-allowlist`

Optional overrides:

```bash
./scripts/release_public.sh \
  --source-branch meshyface-alpha \
  --target-remote public \
  --target-branch main \
  --message "Public v0.1 snapshot"
```

## Safety notes

- The script refuses to run if the source repo has uncommitted changes
  (unless `--allow-dirty` is set).
- On first publish to a new public branch, it creates an orphan release branch
  so private commit history is not pushed.
- It prints the exact file list queued for release before pushing.
