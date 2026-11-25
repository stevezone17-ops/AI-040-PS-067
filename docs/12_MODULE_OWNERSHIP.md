# 12 — Module Ownership & Workload Balance Analysis

**Document Status:** Proposed Allocation — **Requires Team Confirmation**  
**Related Documents:** [`07_SYSTEM_ARCHITECTURE.md`](07_SYSTEM_ARCHITECTURE.md), [`18_WEEK_2_IMPLEMENTATION_PLAN.md`](18_WEEK_2_IMPLEMENTATION_PLAN.md), [`19_WEEK_3_IMPLEMENTATION_PLAN.md`](19_WEEK_3_IMPLEMENTATION_PLAN.md), [`20_VIVA_PREPARATION.md`](20_VIVA_PREPARATION.md)

> [!IMPORTANT]
> **Governance & Viva Rule:** Under capstone evaluation rules, **all three team members must personally write production Python code, unit/integration tests, and meaningful Git commits across both Weeks 2 and 3**. "Week Coordinator / Lead" denotes integration and milestone coordination responsibility—**never** exclusive coding ownership for that week. Furthermore, every member must understand the full codebase sufficiently to perform live code modifications during the individual viva.

---

## 1. Baseline Proposed Ownership Structure

### 1.1 Mishael Julian (`2462184`) — Architecture, Validation & Integration Lead
- **Week 1 Responsibility (Current Phase):** Requirements engineering, business-rule register (`BR-01`–`BR-12`), assumption register (`AS-001`–`AS-033`), constraint catalogue (`CN-01`–`CN-28`), 14-component architecture, domain model, 12 Mermaid diagrams, provisional data contracts, test strategy & 112-case catalogue, and cross-module integration design.
- **Weeks 2–3 Implementation Ownership:**
  - **Shared Kernel & I/O (`M1`):** `src/exam_engine/domain/` (lead), `src/exam_engine/io/` (`ALG-01`).
  - **Invigilation Engine (`M4`):** `src/exam_engine/invigilation/` (`eligibility.py`, `workload.py`, `invigilator_engine.py`) implementing `BR-07`, `BR-08`, `EC-04`, `EC-05`, `ALG-13`, `ALG-14`.
  - **Independent Schedule Validator (`M5`, `M7`):** `src/exam_engine/validation/validator.py` (`ALG-18` auditing all `BR-01`–`BR-12`).
  - **Orchestrator, CLI & Reporting (`M5`, `M9`):** `src/exam_engine/orchestrator.py`, `src/exam_engine/cli.py`, `src/exam_engine/reporting/` (`ALG-20`).
  - **Testing Ownership:** Unit tests for `io/`, `invigilation/`, `validation/`, `reporting/`, and end-to-end integration/determinism suites (`TC-001`–`TC-007`, `TC-052`–`TC-070`, `TC-099`–`TC-112`).

---

### 1.2 Steven Mathew Binu (`2462157`) — Week 2 Implementation Lead
- **Coordination Role:** Coordinates Week 2 (`M1`–`M5`) integration branches, code reviews, and initial end-to-end schedule synthesis sign-off.
- **Weeks 2–3 Implementation Ownership:**
  - **Session Generation (`M1`/`M2`):** `src/exam_engine/scheduling/session_generator.py` (`FR-02`, `EC-08`, `ALG-02`).
  - **Student Conflict Graph (`M2`):** `src/exam_engine/scheduling/conflict_graph.py` (`BR-01`, `EC-06`, `EC-07`, `ALG-03`).
  - **Programme-Semester Core Gap Validator (`M2`):** `src/exam_engine/scheduling/gap_validator.py` (`BR-02`, `EC-01`, `ALG-04`).
  - **Deterministic Course Ordering & Greedy Scheduler (`M2`):** `src/exam_engine/scheduling/ordering.py`, `src/exam_engine/scheduling/scheduler.py` (`BR-03`, `BR-04` 90% session-level capacity check, `ALG-05`, `ALG-06`).
  - **Supplementary Examination Scheduling (`M2`):** `src/exam_engine/scheduling/supplementary.py` (`BR-12`, `EC-08`, `ALG-07`).
  - **Testing Ownership:** Unit, boundary, and Week-3 regression/edge-case tests for scheduling, conflicts, gaps, and supplementary windows (`TC-008`–`TC-027`, `TC-085`–`TC-090`).

---

### 1.3 Tanisha Chhetri (`2462160`) — Week 3 Implementation Lead
- **Coordination Role:** Coordinates Week 3 (`M6`–`M9`) incremental change management, edge-case hardening, official sample reconciliation, and final verification sign-off.
- **Weeks 2–3 Implementation Ownership:**
  - **Hall Allocation & Merge Engine (`M3`):** `src/exam_engine/allocation/hall_allocator.py`, `src/exam_engine/allocation/merge_policy.py`, `src/exam_engine/allocation/policies.py` (`BR-04` duration compatibility, `BR-05` largest-first & `< 10` mandatory cross-dept merge, `EC-02`, `EC-03`, `ALG-08`–`ALG-10`).
  - **Alternate-Column Seat Assignment & Accessibility (`M3`):** `src/exam_engine/allocation/seat_assigner.py`, `src/exam_engine/allocation/accessibility.py` (`BR-05` non-adjacent columns, `BR-06` row-major alphabetical seating, ground-floor Row 1, `+20m` hall extension, `ALG-11`, `ALG-12`).
  - **Incremental Change Management (`M6`):** `src/exam_engine/changes/` (`postponement.py`, `hall_unavailability.py`, `late_registration.py`, `state_manager.py`) (`BR-09`, `BR-10`, `BR-11`, `EC-06`, `ALG-15`–`ALG-17`, `ALG-19`).
  - **Testing Ownership:** Unit, boundary, and transactional rollback tests for hall packing, seating, accessibility, and incremental change commands (`TC-028`–`TC-051`, `TC-071`–`TC-084`, `TC-091`–`TC-098`).

---

## 2. Cross-Module Interfaces & Shared Responsibilities

| Producer -> Consumer | Shared Interface Contract (`src/exam_engine/domain/protocols.py`) | Integration Guarantee |
| :--- | :--- | :--- |
| **Mishael (`io/`) -> Steven & Tanisha** | `ProblemRegistry` (frozen entities + sorted `enrolments_by_course` / `enrolments_by_student` indices) | Guarantees valid foreign keys, deduplicated enrolments, and `1 <= capacity <= R*C`. |
| **Tanisha (`allocation/`) -> Steven (`scheduling/`)** | `check_and_pack_session(session, course_codes, registry, closed_halls) -> PackingResult` (`ALG-08`) | Allows Steven's greedy scheduler (`ALG-06`) to test exact 2D hall/merge/accessibility feasibility as a black-box pure function! |
| **Tanisha (`allocation/`) -> Mishael (`invigilation/`)** | `tuple[HallAllocation, ...]` (containing `course_student_counts`, `building_code`, `effective_window`) | Gives Mishael's `ALG-13`/`ALG-14` exact student counts, merged course departments (`EC-04`), and `+20m` windows (`EC-05`). |
| **Steven (`scheduling/`) + Mishael (`invigilation/` & `validation/`) -> Tanisha (`changes/`)** | `find_earliest_two_pass()`, `recompute_session_invigilation()`, `validate_schedule_independently()` (`ALG-18`) | Allows Tanisha's incremental engines (`ALG-15`–`ALG-17`) to reuse validated feasibility checks and global `ALG-18` audits cleanly. |

### Shared Team Responsibilities (All 3 Members)
1. **Domain Model Reviews (`M1`):** All three members review and sign off on `src/exam_engine/domain/` before branching into `M2`/`M3`/`M4`.
2. **Pull Request Reviews:** Every PR into `develop` / `main` requires review by at least one teammate who did **not** author the PR, ensuring cross-training for the viva.
3. **Official Sample Schema Adaptation (`M9`):** When mentors release the official sample dataset, Mishael updates `io/` & `reporting/` while Steven and Tanisha verify domain policy flags (`AS-001`–`AS-033`).

---

## 3. Critical Workload Balance Evaluation & Optional Rebalancing Proposal

Per Master Prompt Section 18, we objectively evaluate the implementation effort across Weeks 2 and 3 under the baseline allocation:

| Member | Week 1 Effort | Week 2 Coding (`M1`–`M5`) | Week 3 Coding (`M6`–`M9`) | Owned Algorithms (`ALG`) | Owned Test Cases (`TC`) | Estimated Code Share (Wks 2–3) |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **Mishael Julian** | **High** (Architecture & 23 docs) | Medium (`M1` domain/IO, `M4` invigilation, `M5` orchestrator/reports) | Medium (`M7` full `ALG-18` validator, `M9` CLI/perf/determinism) | `ALG-01`, `13`, `14`, `18`, `20` (5 ALGs + CLI/Orch) | 40 TCs | ~32% |
| **Steven Mathew Binu** | Review & Git setup | **High** (`M2`: sessions, conflict graph, gap, ordering, scheduler, supplementary; Week 2 lead) | Light–Medium (`M8` scheduling edge tests, `M9` regression) | `ALG-02`–`ALG-07` (6 ALGs) | 26 TCs | ~25% |
| **Tanisha Chhetri** | Review | **High** (`M3`: hall packing, `<10` merges, alternate columns, SN Row-1 +20m) | **Very High** (`M6`: `BR-09` postponement, `BR-10` hall closure, `BR-11` late reg, `ALG-19` snapshots; Week 3 lead) | `ALG-08`–`ALG-12`, `15`–`17`, `19` (9 ALGs) | 46 TCs | **~43%** |

### Assessment Finding: Mild Week-3 Asymmetry on Tanisha
While Mishael's heavy Week 1 architectural load balances his 32% coding share, **Tanisha's baseline Week 2 (`M3`) + Week 3 (`M6`) implementation scope (~43% of algorithmic code, 9 of 20 algorithms) is noticeably heavier than Steven's Week 3 coding load** once `M2` finishes in Week 2.

### Proposed Rebalancing Adjustment (Pending Team Confirmation — *Baseline Preserved Until Confirmed*)
Without silently altering the baseline ownership above, we recommend the team confirm the following **2 targeted co-ownership adjustments** at the Week 1 review meeting:

1. **Adjustment R1 (Steven co-implements `ALG-15` `POSTPONE_COURSE` in Week 3 `M6`):**
   - *Why it fits naturally:* Course postponement (`BR-09`, `EC-06`) is fundamentally a **temporal session-search & conflict/gap validation problem** (`ALG-03`, `ALG-04`, `ALG-06`, `ALG-07`)—which Steven already owns! Tanisha retains Change Coordinator leadership, `BR-10` (`MARK_HALL_UNAVAILABLE`), and `BR-11` (`ADD_LATE_REGISTRANT`).
2. **Adjustment R2 (Mishael co-implements `ALG-19` `StateSnapshotManager` in Week 3 `M6`):**
   - *Why it fits naturally:* Session SHA-256 fingerprinting and transactional rollback (`state_manager.py`) sit directly between Mishael's `orchestrator.py` and `IndependentScheduleValidator` (`ALG-18`).

**Resulting Balanced Distribution (if confirmed by team):**
- **Mishael:** ~35% Wks 2–3 code + Week 1 Architecture Lead (`38` TCs)
- **Steven:** ~32% Wks 2–3 code + Week 2 Lead (`34` TCs)
- **Tanisha:** ~33% Wks 2–3 code + Week 3 Lead (`40` TCs)
