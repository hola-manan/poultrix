# `docs/` — Documentation & agent contracts

Reference material for humans + AI agents working on this repo. Two distinct concerns share this folder:

1. **Technical / architecture docs** — how the system actually works (architecture, integration, known issues).
2. **Clean-room agent contracts** — formal role definitions for the agent pipeline that reconstructs and reimplements the system from scratch. Not part of the runtime; they describe a process, not the code.

## Files

### [`known_issues.md`](known_issues.md)
The **single place to check** when you hit something weird before assuming you broke it. Two sections: `## Open` and `## Resolved`. Resolved entries carry a date + short note describing the fix shape. As of 2026-05-21 the suite was green and there are no open entries.

## `architecture/`

### [`architecture/agricultural_system.md`](architecture/agricultural_system.md)
Long-form description of the agricultural advisory subsystem — the FAO-56 ET0 math, Kc adjustment, soil water deficit, nutrient gap calculations, pest/disease risk scoring, yield projection, and the report orchestration done by `report_generator.py` (now [src/jeevn/application/advisory_service.py](../src/jeevn/application/advisory_service.py)). Includes example API request/response shapes and a list of data sources. Some module names in this doc are pre-rename — the current canonical names are in [../ARCHITECTURE.md](../ARCHITECTURE.md).

## `integration/`

### [`integration/agricultural_integration.md`](integration/agricultural_integration.md)
"Quickstart for the advisory layer" — Python and `curl` snippets for the `POST /advisory/agricultural` endpoint, list of new modules, mention of the test script. Pitched at someone who wants to *use* the advisory layer rather than modify it.

## `agents/` — clean-room reimplementation pipeline

These describe a three-stage agent pipeline for reconstructing the repo from scratch in a clean-room (no original-source copying) fashion. Not invoked by any runtime code; they're prompt material + role contracts for whoever runs the rebuild.

### [`agents/pipeline.json`](agents/pipeline.json)
The handoff contract. Defines the three agents (`ReconAndEvidenceCollector → BehaviorModeler → ReimplementationAndTestHarness`), their inputs/outputs, stop rules, drift-detection rules, and artifact inventory (`evidence_catalog.json`, `spec.json`, `interop_tests/`, etc.).

### [`agents/recon_and_evidence_collector.md`](agents/recon_and_evidence_collector.md)
Role spec for the first agent — forensic analyst that traces every code path, captures behaviour as-is (including quirks), and writes `evidence_catalog.json`.

### [`agents/behavior_modeler.md`](agents/behavior_modeler.md)
Role spec for the middle agent — translates evidence into a formal `spec.json` plus `interop_tests/`. Must be **descriptive**, not prescriptive (specify what the system does, not how to rebuild it).

### [`agents/reimplementation_and_test_harness.md`](agents/reimplementation_and_test_harness.md)
Role spec for the last agent — builds a clean-room implementation against the spec without referring to original source, validates 100% pass on `interop_tests/`.

### [`agents/decoupler.md`](agents/decoupler.md) / [`agents/decoupler_pro.md`](agents/decoupler_pro.md)
Companion agent specs focused on the refactor pattern: take a tangled module, identify seams, extract pure interfaces. The `_pro` variant is the more rigorous / interview-loop version.

## Conventions

- **`known_issues.md` is the source of truth for "is this a known bug?"** — check it first; add new entries when you find something; move to Resolved when fixed (with date + fix shape).
- **Long-form architecture lives in this folder.** Short summaries and folder-by-folder maps live in `OVERVIEW.md` files inside each folder + [../ARCHITECTURE.md](../ARCHITECTURE.md) at the repo root.
- **Agent role contracts are stable.** They describe a *process* the team has agreed on; treat them like API contracts — versioned changes with intent in the commit message.

## Related (outside this folder)

- [../README.md](../README.md) — setup + run instructions.
- [../QUICKSTART.md](../QUICKSTART.md) — step-by-step local-dev walkthrough.
- [../TASKS.md](../TASKS.md) — shared task list (read first when starting work; both humans and agents edit it).
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — high-level repo architecture index.
