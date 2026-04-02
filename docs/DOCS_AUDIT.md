# Docs Audit

Doc status: active-doc-ops
Last reviewed: 2026-03-14

Last audit: 2026-03-14

Scope:

1. `docs/*.md` except `docs/IDEAS.md` (treated as personal notes backlog).
2. Checked docs claims against current `meshdash/` code structure and active branch state.

## Status Summary

| Document | Status | Notes |
|---|---|---|
| `docs/ROADMAP.md` | Active | Rooms roadmap is still valid as future work; milestone status note added. |
| `docs/ROOMS_SPEC.md` | Active (spec) | Protocol/design spec remains relevant; no current implementation yet. |
| `docs/PROJECT_PLAN.md` | Active | Product direction still aligns with current goals. |
| `docs/CHANNELS.md` | Active | Updated for current `View Ch` / `Send Ch` behavior. |
| `docs/REPO_STRUCTURE.md` | Active | Reflects modular template assembly and current architecture entry points. |
| `docs/REFACTOR_ROADMAP.md` | Historical but useful | Kept as engineering log; updated stale template references. |
| `docs/MULTI_RADIO_INGEST_PLAN.md` | Proposal (not implemented) | Now explicitly labeled as planned V2 design. |
| `docs/MULTI_RADIO_EXECUTION_PLAN.md` | Proposal (historical branch context) | Added status note and fixed stale ZIP artifact wording. |
| `docs/MULTI_RADIO_V2_1_FROZEN_SPEC.md` | Normative spec (future) | Explicitly marked as not implemented in current branch. |
| `docs/MULTI_RADIO_GPT_REVIEW_HANDOFF.md` | Review helper (future) | Explicitly marked as proposal/review aid only. |
| `docs/README.md` | Active | Canonical docs index with lifecycle/status map. |

## Stale Items Fixed In This Audit

1. `docs/ROADMAP.md` no longer points Rooms UI edits at monolithic `dashboard.js.tmpl`; now points to active chat partials.
2. `docs/CHANNELS.md` updated from outdated single `Msg Ch` wording to current split `View Ch` / `Send Ch` model.
3. `docs/REFACTOR_ROADMAP.md` template references updated from monolithic CSS/JS files to current partial assembly + compatibility stubs.
4. Multi-radio docs now clearly state they are planning/spec artifacts and not implemented behavior in this branch.
5. Removed stale in-repo implication of `MULTI_RADIO_V2_CODEX_HANDOFF.md` by clarifying it was an external ZIP artifact.

## Triage Guidance

Use this quick rule when editing docs:

1. If a doc describes current runtime behavior, verify against code before merging.
2. If a doc is speculative/planning, add a clear status banner (`proposal`, `historical`, `active`).
3. Keep one active feature roadmap (`docs/ROADMAP.md`) and treat others as scoped specs or archives.
4. Keep `docs/README.md` updated whenever docs are added or doc status/lifecycle changes.
