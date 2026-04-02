# Public Release Workflow

Doc status: active-runtime
Last reviewed: 2026-04-02

This repo stays private for development while publishing curated snapshots to a
separate public repo.

Use:

- release branch in private repo: `release/public-v0`
- publish script: `scripts/release_public.sh`
- profile allowlists: `.public-release/allowlists/*.allowlist`

## One-time setup

1. Keep development on private branches in `mesh_py` (for example
   `meshyface-alpha`).
2. Create a release-prep branch from dev when you want to curate a public cut:

   ```bash
   git checkout -b release/public-v0 meshyface-alpha
   ```

   In this branch, keep public-facing feature gates/cleanup commits. For v0,
   the rail is intentionally clamped to `chat`, `network`, `console`,
   `settings`.
3. Ensure public target remote exists (this project uses `meshyface`):

   ```bash
   git remote -v
   ```

## Default config

Default release config lives in `.public-release/config.env`:

```bash
PUBLIC_RELEASE_REMOTE=meshyface
PUBLIC_RELEASE_BRANCH=release-candidate
PUBLIC_RELEASE_PROFILE=core-ui
```

That means plain runs publish from your chosen source branch to
`meshyface/release-candidate`.

## Curate what can go public

Profile allowlists live in `.public-release/allowlists/`.

Current profiles:

- `core-ui`: first release surface (chat/network/console/settings)
- `sdk`: SDK/docs-only export

List profiles:

```bash
./scripts/release_public.sh --list-profiles
```

Allowlist rules:

- one repo-root-relative path per line
- blank lines and `# comments` are ignored
- keep list explicit and minimal

## Publish flow

Dry-run first:

```bash
./scripts/release_public.sh --source-branch release/public-v0 --dry-run
```

Publish:

```bash
./scripts/release_public.sh --source-branch release/public-v0
```

Defaults:

- target remote: from `.public-release/config.env` (default `meshyface`)
- target branch: from `.public-release/config.env` (default `release-candidate`)
- profile: from `.public-release/config.env` (default `core-ui`)

Optional overrides:

```bash
./scripts/release_public.sh \
  --source-branch release/public-v0 \
  --profile sdk \
  --target-branch release-sdk \
  --message "Public v0.1 snapshot"
```

After publishing to `release-candidate`, open and merge PR in `meshyface`:

- base: `main`
- compare: `release-candidate`

## Safety notes

- The script refuses to run if the source repo has uncommitted changes
  (unless `--allow-dirty` is set).
- On first publish to a new public branch, it creates an orphan release branch
  so private commit history is not pushed.
- It prints the exact file list queued for release before pushing.
- Path-based allowlists control files, not sections inside a file. If a release
  needs feature-level pruning inside shared templates, do that on
  `release/public-v0` before publishing.
