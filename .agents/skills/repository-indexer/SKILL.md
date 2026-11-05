---
name: repository-indexer
description: >-
  Senior codebase analysis and repository indexing engine. Performs parallel structure scanning,
  dependency graphing, entry-point and service boundary mapping, git churn and hotspot detection,
  and generates token-efficient PROJECT_INDEX.md and PROJECT_INDEX.json artifacts with staleness tracking.
---

# Repository Indexer Skill

This skill guides the agent in systematically analyzing, structural mapping, dependency graphing, and generating token-efficient index documents for any software repository.

## When to Use This Skill
- When onboarding to a new codebase to orient downstream agents and human developers.
- When generating or refreshing `PROJECT_INDEX.md` and `PROJECT_INDEX.json`.
- When assessing codebase risk surfaces, maintenance debt, or single-author bus-factor risks.
- When mapping entry points, module interfaces, and internal/external dependency graphs.
- When compressing repository context into a token-efficient summary (<2000 tokens).

## Core Execution Pipeline

### 1. Freshness & Staleness Detection
1. Check for existing `PROJECT_INDEX.md` and `PROJECT_INDEX.json` in the repository root.
2. Compare the `updated_at` timestamp and indexed commit hash against `git rev-parse HEAD`.
3. Gauge drift magnitude:
   - Commits since last index (`git rev-list --count <indexed-hash>..HEAD`).
   - Days elapsed since last update (staleness threshold: 7 days).
   - Structural churn: check if files or directories were added, removed, or moved.
4. If fresh and drift is 0, confirm validity and exit; otherwise proceed to re-indexing.

### 2. Comprehensive Structure Scan
1. Categorize all repository paths into 5 focus areas:
   - **Source Code**: Core domain logic, UI adapters, calculation engines.
   - **Tests**: Unit tests, integration tests, property-based tests, benchmarks.
   - **Configuration**: Build configurations, linters, packaging specs, CI/CD pipelines.
   - **Documentation**: README, release notes, changelogs, architecture notes.
   - **Scripts / Tools**: Build scripts, migration tools, database seeding, locale compilers.
2. Record total files, total lines of code, and extension distribution.
3. Detect project manifests (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, etc.) to determine build toolchain and runtime requirements.

### 3. Entry Points & Service Boundary Mapping
1. Identify primary execution entry points:
   - GUI launchers, Web UI runners, CLI binaries, server bootstrap files, worker daemons.
2. Trace public API surfaces and module boundaries.
3. Map shared utilities, cross-cutting concerns, and multiplatform abstraction layers.

### 4. Dependency Graphing & Risk Analysis
1. Parse AST imports to build an internal dependency graph (adjacency list).
2. Calculate dependency metrics:
   - **Fan-in ($C_a$)**: Number of internal modules that depend on this module.
   - **Fan-out ($C_e$)**: Number of internal modules this module depends on.
   - **Instability ($I$)**: $I = \frac{C_e}{C_a + C_e}$ ($0 = \text{maximally stable}$, $1 = \text{maximally unstable}$).
3. Audit external dependencies: version constraints, licensing compatibility, and maintenance status.
4. Check for circular dependencies and architectural layer violations.
5. Identify change hotspots via git log churn and bug-fix commit frequency.
6. Assess knowledge silo and bus-factor risk based on git author concentration.

### 5. Generate Index Artifacts
1. **`PROJECT_INDEX.md`**: Human- and LLM-readable Markdown overview with module catalogs, dependency tables, entry points, and recent changes.
2. **`PROJECT_INDEX.json`**: Machine-parseable JSON schema adhering to standard agent indexing schemas.
3. Calculate token savings: compare full codebase raw context size against the compressed index size (target >90% savings).

### 6. Validation & Quality Checklist
- [ ] All file paths in the index resolve to existing repository files.
- [ ] JSON index parses cleanly without syntax or schema errors.
- [ ] Markdown index is clear, structured, and includes clickable file links.
- [ ] No secrets, credentials, or private internal URLs are exposed.
- [ ] Freshness metadata (timestamp, commit hash, staleness threshold) is accurate.
