# 01 — Project Overview

**Document Status:** Week 1 Design Baseline — Pending Team Confirmation & Mentor Approval  
**Project:** University Exam Timetabling and Hall Allocation Engine (`PS-067`)  
**Team:** `AI-040` (Steven Mathew Binu `2462157`, Tanisha Chhetri `2462160`, Mishael Julian `2462184`)

---

## 1. Executive Summary

The **University Exam Timetabling and Hall Allocation Engine** is a deterministic, command-file-driven backend software system designed for a university Office of Examinations. Its responsibility is to transform raw academic registration records—courses, students, enrolments, physical examination halls, invigilators, and a dated examination calendar—into a conflict-free examination schedule, a physically legal hall and seat allocation plan, a workload-balanced invigilation roster, and a structured violations audit report.

Beyond initial schedule synthesis, the engine supports **incremental operational change management**: postponing scheduled courses, handling sudden hall closures, and admitting late-registering students while strictly isolating recomputation to affected sessions and preserving all unaffected assignments verbatim.

---

## 2. Operational Context & Problem Statement

End-semester university examinations involve tightly coupled combinatorial constraints across four dimensions:

1. **Temporal Scheduling (`BR-01`, `BR-02`, `BR-03`, `BR-12`):** Courses must be placed into Morning (`FN: 09:30–12:30`) and Afternoon (`AN: 14:00–17:00`) sessions without student clashes, respecting daily examination caps, backlog consent exceptions, programme-semester core-course study gaps (`>= 1` full calendar day), and end-of-window supplementary backlog rules.
2. **Spatial & Accessibility Packing (`BR-04`, `BR-05`, `BR-06`):** Session occupancy may not exceed 90% of aggregate available hall capacity. Two-hour and three-hour papers cannot share a hall. Halls are filled largest-first with at most two courses per hall, alternate-column anti-collusion seating, mandatory cross-department merging for small courses (`< 10` students), and ground-floor Row 1 priority plus 20-minute time extensions for special-needs students.
3. **Human Resource Staffing (`BR-07`, `BR-08`):** Occupied halls require `ceil(students / 30)` department-independent invigilators, and each active building requires one additional Chief Invigilator per session, subject to daily (`<= 2`), weekly (`4–8`), date-availability, and extended-duty overlap limits.
4. **Incremental Disruption Recovery (`BR-09`, `BR-10`, `BR-11`):** Post-publication changes must execute transactionally—updating only the impacted sessions, rolling back cleanly when hard rules cannot be met, and maintaining cross-session invariants (daily student limits, core gaps, and weekly invigilator caps).

---

## 3. Design Philosophy & Architectural Priorities

Aligned with the official grading rubric, our engineering design prioritises clarity, determinism, and auditability over speculative infrastructure:

| Priority | Engineering Realisation |
| :--- | :--- |
| **Business-Rule Fidelity (40%)** | Every rule (`BR-01`–`BR-12`) is implemented both constructively in its owning engine and auditably in an **Independent Schedule Validator** ([`07_SYSTEM_ARCHITECTURE.md`](07_SYSTEM_ARCHITECTURE.md)). |
| **Clean Domain Modelling (20%)** | Single-source-of-truth in-memory entities separating immutable input registries from mutable/versioned schedule state ([`08_DOMAIN_MODEL.md`](08_DOMAIN_MODEL.md)). |
| **Edge-Case Explicitness (15%)** | Mandatory scenarios (`EC-01`–`EC-08`) and 33 documented ambiguities (`AS-001`–`AS-033`) have deterministic outcomes and explicit failure codes ([`05_ASSUMPTION_REGISTER.md`](05_ASSUMPTION_REGISTER.md)). |
| **Determinism & Testability (10%)** | Zero randomness (`random` forbidden), avoiding unordered set iteration, explicit lexicographical tie-breakers on every sort, and pure domain services testable without file I/O ([`13_TEST_STRATEGY.md`](13_TEST_STRATEGY.md)). |
| **Code Quality & Viva Readiness (15%)** | Python 3.10+ standard library only (pending team confirmation), small cohesive modules, clear module boundaries so each team member can explain and live-modify any component ([`20_VIVA_PREPARATION.md`](20_VIVA_PREPARATION.md)). |

---

## 4. Expected Operational Scale

Per the capstone specification, the engine is engineered against the expected official sample scale (with generous headroom):

| Entity / Dimension | Official Expected Sample Scale | Design Headroom Target |
| :--- | :--- | :--- |
| **Courses** | ~120 courses | Up to 1,000 courses |
| **Students** | ~2,500 students (with ~10,000–15,000 enrolments) | Up to 15,000 students |
| **Examination Halls** | ~18 halls across multiple buildings | Up to 100 halls |
| **Invigilators** | ~90 invigilators | Up to 500 invigilators |
| **Examination Window** | 12 calendar days (with 2 holidays -> ~20 sessions) | Up to 60 days (120 sessions) |
| **Change Commands** | 8 sequential incremental commands | Arbitrary sequential command batches |
| **Target Runtime** | Sub-second to < 5 seconds end-to-end on standard laptop CPU | < 10 seconds at 5x scale |

> [!NOTE]
> Official input files and sample expected outputs have **not** yet been released. All file schemas in [`10_INPUT_OUTPUT_CONTRACTS.md`](10_INPUT_OUTPUT_CONTRACTS.md) are **explicitly provisional** and isolated behind I/O adapters.

---

## 5. Strict Scope Boundaries & Non-Goals

### In Scope (Week 1)
- Complete requirement engineering, ambiguity resolution, constraint taxonomy, domain model, 20 detailed algorithms, incremental recomputation protocol, provisional I/O contracts, 12 Mermaid diagrams, 112 design-level test cases, and self-contained Week 2 / Week 3 implementation plans.

### Explicitly Out of Scope (All Weeks)
- Graphical user interfaces (React, web dashboards, desktop GUIs).
- Web servers, REST/GraphQL APIs (FastAPI, Flask, Django), or microservices.
- External relational/NoSQL databases (PostgreSQL, SQLite, MongoDB) — state is file-driven and in-memory.
- Machine learning, metaheuristics (genetic algorithms, simulated annealing), or black-box MIP/SAT solvers that deviate from the prescribed deterministic heuristic (`BR-03`).
- Cloud deployment, Docker/Kubernetes orchestration, or authentication layers.

---

## 6. Evaluation Alignment Summary

| Criterion | Marks | Primary Supporting Deliverables |
| :--- | :---: | :--- |
| Business-rule correctness | 40 | [`04_BUSINESS_RULE_REGISTER.md`](04_BUSINESS_RULE_REGISTER.md), [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md), [`09_ALGORITHM_DESIGN.md`](09_ALGORITHM_DESIGN.md) |
| Domain design | 20 | [`07_SYSTEM_ARCHITECTURE.md`](07_SYSTEM_ARCHITECTURE.md), [`08_DOMAIN_MODEL.md`](08_DOMAIN_MODEL.md), [`11_INCREMENTAL_RECOMPUTATION.md`](11_INCREMENTAL_RECOMPUTATION.md) |
| Validation and edge cases | 15 | [`05_ASSUMPTION_REGISTER.md`](05_ASSUMPTION_REGISTER.md), [`10_INPUT_OUTPUT_CONTRACTS.md`](10_INPUT_OUTPUT_CONTRACTS.md) |
| Tests | 10 | [`13_TEST_STRATEGY.md`](13_TEST_STRATEGY.md), [`14_TEST_CASE_CATALOGUE.md`](14_TEST_CASE_CATALOGUE.md), [`15_REQUIREMENTS_TRACEABILITY_MATRIX.md`](15_REQUIREMENTS_TRACEABILITY_MATRIX.md) |
| Code quality & Git hygiene | 5 | [`12_MODULE_OWNERSHIP.md`](12_MODULE_OWNERSHIP.md), [`18_WEEK_2_IMPLEMENTATION_PLAN.md`](18_WEEK_2_IMPLEMENTATION_PLAN.md), [`19_WEEK_3_IMPLEMENTATION_PLAN.md`](19_WEEK_3_IMPLEMENTATION_PLAN.md) |
| Viva & presentation | 10 | [`20_VIVA_PREPARATION.md`](20_VIVA_PREPARATION.md), [`21_WEEK_1_DESIGN_DOCUMENT.md`](21_WEEK_1_DESIGN_DOCUMENT.md) |
| **Total** | **100** | *(Minimum passing score: 50/100; originality strictly enforced)* |
