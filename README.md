# University Exam Timetabling and Hall Allocation Engine (`AI-040-PS-067`)

> [!IMPORTANT]
> **Current Milestone Status: WEEK 1 — UNDERSTAND AND DESIGN (Documentation Only)**
> This repository is currently in the **Week 1 Architecture & Specification Phase**.
> - **No application code, executable tests, or deployment artifacts** exist in this phase by strict capstone requirement.
> - **Pending Reviews:** Language selection, provisional data contracts, assumption resolutions, and module ownership allocations are **proposed** and require **Team Confirmation** and **Official Mentor Approval** before Week 2 implementation begins.

---

## 1. Project Metadata

| Attribute | Details |
| :--- | :--- |
| **Project Title** | University Exam Timetabling and Hall Allocation Engine |
| **Problem Statement** | PS-067 (University Examinations — High Difficulty) |
| **Team ID** | AI-040 |
| **Repository** | [`https://github.com/stevezone17-ops/AI-040-PS-067`](https://github.com/stevezone17-ops/AI-040-PS-067) |
| **Institution** | CHRIST University |
| **Class / Section** | 6BTCSAIML A |
| **Capstone Provider** | 10 SECONDS |
| **Proposed Runtime** | Python 3.10+ (Standard Library core; `pytest` & `ruff` for dev — *Pending Team Confirmation*) |
| **Operation Mode** | Deterministic, command-file driven CLI backend engine (No UI, no external DB, no ML) |

### Team Roster & Proposed Leadership

| Member Name | Register Number | Proposed Primary Role | Implementation Coordination |
| :--- | :--- | :--- | :--- |
| **Mishael Julian** | `2462184` | Architecture, Validation & Integration Lead | Week 1 Design Lead; Invigilation Engine, Independent Validator, Orchestrator |
| **Steven Mathew Binu** | `2462157` | Scheduling & Conflict Resolution Lead | Week 2 Implementation Coordinator; Timetable Engine, Conflict & Gap Rules |
| **Tanisha Chhetri** | `2462160` | Spatial Allocation & Change Management Lead | Week 3 Implementation Coordinator; Hall/Seat/Accessibility & Incremental Changes |

*(All three team members contribute production code, unit/integration tests, and verified Git commits across Weeks 2 and 3. See [`docs/12_MODULE_OWNERSHIP.md`](docs/12_MODULE_OWNERSHIP.md).)*

---

## 2. Problem Summary

University examination sections must schedule hundreds of end-semester courses across fixed morning (`FN: 09:30–12:30`) and afternoon (`AN: 14:00–17:00`) sessions without student clashes, enforce core-course study gaps (`BR-02`) and supplementary backlog rules (`BR-12`), pack students into physical halls under 90% session capacity limits (`BR-04`), alternate-column anti-cheating geometry and small-course cross-department merging (`BR-05`), ground-floor Row 1 accessibility with +20 minute extensions (`BR-06`), invigilator and building-chief staffing limits (`BR-07`, `BR-08`), and incremental post-publication disruptions (`BR-09`, `BR-10`, `BR-11`) without disturbing unaffected sessions.

---

## 3. Week 1 Documentation Index

All Week 1 engineering deliverables reside under [`docs/`](docs/):

### Core Requirements & Domain Analysis
1. [Project Overview](docs/01_PROJECT_OVERVIEW.md) — Scope, context, objectives, evaluation rubric, and non-goals.
2. [Software Requirements Specification (SRS)](docs/02_SOFTWARE_REQUIREMENTS_SPECIFICATION.md) — Functional (`FR-01`–`FR-06`) and non-functional requirements.
3. [Domain Glossary](docs/03_DOMAIN_GLOSSARY.md) — Canonical definitions of university examination terminology.
4. [Business Rule Register](docs/04_BUSINESS_RULE_REGISTER.md) — Authoritative catalogue of `BR-01` through `BR-12` and edge cases `EC-01`–`EC-08`.
5. [Assumption Register](docs/05_ASSUMPTION_REGISTER.md) — Structured ambiguity resolutions (`AS-001`–`AS-033`) with policy isolation points.
6. [Constraint Catalogue](docs/06_CONSTRAINT_CATALOGUE.md) — Classification of hard constraints, soft violations, resource shortages, and input errors (`CN-01`–`CN-28`).

### System Architecture, Modelling & Algorithms
7. [System Architecture](docs/07_SYSTEM_ARCHITECTURE.md) — 14-component layered architecture, boundaries, and data flow.
8. [Domain Model](docs/08_DOMAIN_MODEL.md) — 16 in-memory domain entities, ownership invariants, and cardinalities.
9. [Algorithm Design](docs/09_ALGORITHM_DESIGN.md) — Step-by-step pseudocode, complexity, tie-breakers, and worked examples (`ALG-01`–`ALG-20`).
10. [Input & Output Contracts](docs/10_INPUT_OUTPUT_CONTRACTS.md) — **Provisional** CSV/JSON/TXT schemas and adapter isolation strategy.
11. [Incremental Recomputation Design](docs/11_INCREMENTAL_RECOMPUTATION.md) — Dependency DAG, blast-radius isolation, snapshot/rollback transactionality, and immutability verification.

### Verification, Governance & Execution Plans
12. [Module Ownership](docs/12_MODULE_OWNERSHIP.md) — Responsibilities, interface contracts, workload balance analysis, and rebalancing proposal.
13. [Test Strategy](docs/13_TEST_STRATEGY.md) — Unit, integration, property-based, determinism, and performance verification strategy.
14. [Test Case Catalogue](docs/14_TEST_CASE_CATALOGUE.md) — 112 concrete design-level test cases (`TC-001`–`TC-112`).
15. [Requirements Traceability Matrix](docs/15_REQUIREMENTS_TRACEABILITY_MATRIX.md) — Bidirectional mapping across `FR` -> `BR`/`EC` -> `CN` -> `ALG` -> Module -> `TC`.
16. [Architectural Decision Log](docs/16_DECISION_LOG.md) — 13 Architecture Decision Records (`ADR-001`–`ADR-013`).
17. [Risk Register](docs/17_RISK_REGISTER.md) — Technical, algorithmic, schedule, and schema risks (`RSK-001`–`RSK-012`).
18. [Week 2 Implementation Plan](docs/18_WEEK_2_IMPLEMENTATION_PLAN.md) — Self-contained Milestone `M1`–`M5` handover specification (Coordinated by Steven Mathew Binu).
19. [Week 3 Implementation Plan](docs/19_WEEK_3_IMPLEMENTATION_PLAN.md) — Self-contained Milestone `M6`–`M9` handover specification (Coordinated by Tanisha Chhetri).
20. [Viva Preparation Guide](docs/20_VIVA_PREPARATION.md) — Pitch scripts, rule walkthroughs, 35 viva Q&As, and live-modification drills.

### Submission & Quality Assurance
21. [Consolidated Week 1 Design Document](docs/21_WEEK_1_DESIGN_DOCUMENT.md) — Submission-ready master document suitable for PDF export.
22. [Week 1 Review Report](docs/22_WEEK_1_REVIEW_REPORT.md) — Independent consistency audit and 21-gate quality checklist.
23. [Architecture & Behavioural Diagrams](docs/diagrams/README.md) — 12 validated Mermaid source files (`.mmd`) with engineering walkthroughs.

---

## 4. Planned Target Repository Structure (Weeks 2–3)

During Week 1, **only `README.md` and `docs/` exist**. The full directory tree below represents the **planned Week 2–3 implementation layout**:

```text
AI-040-PS-067/
├── docs/                          # [CREATED IN WEEK 1] Specifications, ADRs, plans & diagrams
│   └── diagrams/                  # [CREATED IN WEEK 1] 12 Mermaid (.mmd) diagrams + guide
├── src/                           # [PLANNED WEEK 2] Python package root
│   └── exam_engine/
│       ├── domain/                # Entities, enums, immutable value objects, ScheduleState
│       ├── scheduling/            # Conflict graph, course ordering, gap check, greedy scheduler
│       ├── allocation/            # Largest-first hall packing, small-course merge, seating, accessibility
│       ├── invigilation/          # Hall invigilator & building chief assignment, workload tracker
│       ├── changes/               # Postponement, hall closure, late registration, transactional state
│       ├── validation/            # Independent schedule validator (audits BR-01..BR-12)
│       ├── reporting/             # Deterministic CSV/JSON/TXT formatters
│       ├── io/                    # Provisional schema parsers, normalisers, file writers
│       ├── orchestrator.py        # Top-level batch & incremental execution pipeline
│       └── cli.py                 # Command-line entrypoint
├── tests/                         # [PLANNED WEEKS 2-3] Automated pytest suite
│   ├── unit/
│   ├── integration/
│   ├── regression/
│   └── fixtures/
├── data/                          # [PLANNED WEEKS 2-3] Input datasets
│   ├── sample/                    # Official sample dataset (when released by mentors)
│   └── synthetic/                 # Team-authored edge-case & stress datasets
├── output/                        # [PLANNED WEEKS 2-3] Generated schedules & reports (gitignored)
├── pyproject.toml                 # [PLANNED WEEK 2] Python >=3.10 metadata, pytest & ruff config
├── .gitignore                     # [PLANNED WEEK 2] Bytecode, venv, output artefacts
└── README.md                      # [CREATED IN WEEK 1] Project status & navigation
```
