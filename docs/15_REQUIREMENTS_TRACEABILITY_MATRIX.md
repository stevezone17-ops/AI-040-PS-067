# 15 — Requirements Traceability Matrix (RTM)

**Document Status:** Week 1 Design Baseline — 100% Bidirectional Coverage Verified  
**Related Documents:** [`02_SOFTWARE_REQUIREMENTS_SPECIFICATION.md`](02_SOFTWARE_REQUIREMENTS_SPECIFICATION.md), [`04_BUSINESS_RULE_REGISTER.md`](04_BUSINESS_RULE_REGISTER.md), [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md), [`09_ALGORITHM_DESIGN.md`](09_ALGORITHM_DESIGN.md), [`14_TEST_CASE_CATALOGUE.md`](14_TEST_CASE_CATALOGUE.md)

---

## 1. Functional Requirement Traceability (`FR-01` – `FR-06`)

| FR ID | Requirement Summary | Governing Business Rules | Constraints (`CN`) | Algorithms (`ALG`) | Planned Modules (`src/exam_engine/`) | Verification Test Cases (`TC`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FR-01** | Register courses, students, enrolments, halls, invigilators | `BR-01`, `BR-02`, `BR-06`, `BR-07`, `BR-12` | `CN-01`–`CN-05` | `ALG-01` | `domain/entities.py`, `io/parsers.py`, `io/validators.py` | `TC-001`–`TC-005`, `TC-007`, `TC-099`, `TC-100` |
| **FR-02** | Register exam window (`FN`/`AN`, holidays) & generate timetable | `BR-01`–`BR-04`, `BR-12` | `CN-06`–`CN-11`, `CN-28` | `ALG-02`–`ALG-08` | `scheduling/session_generator.py`, `conflict_graph.py`, `gap_validator.py`, `ordering.py`, `supplementary.py`, `scheduler.py` | `TC-006`, `TC-008`–`TC-027`, `TC-085`–`TC-090`, `TC-101`, `TC-102`, `TC-109` |
| **FR-03** | Allocate students to halls, enforce seating & accessibility | `BR-04`, `BR-05`, `BR-06` | `CN-12`–`CN-19` | `ALG-08`–`ALG-12` | `allocation/hall_allocator.py`, `merge_policy.py`, `seat_assigner.py`, `accessibility.py` | `TC-028`–`TC-051` |
| **FR-04** | Assign hall invigilators & building chiefs under workload caps | `BR-07`, `BR-08` | `CN-20`–`CN-24` | `ALG-13`, `ALG-14` | `invigilation/eligibility.py`, `workload.py`, `invigilator_engine.py` | `TC-052`–`TC-070` |
| **FR-05** | Incremental changes (postpone, hall closure, late reg) | `BR-09`, `BR-10`, `BR-11` | `CN-25`–`CN-27` | `ALG-15`–`ALG-17`, `ALG-19` | `changes/postponement.py`, `hall_unavailability.py`, `late_registration.py`, `state_manager.py` | `TC-071`–`TC-084`, `TC-091`–`TC-098`, `TC-112` |
| **FR-06** | Deterministic outputs, seat maps, invigilation & violations reports | All `BR-01`–`BR-12` | `CN-09`, `CN-24`–`CN-27` | `ALG-18`, `ALG-20` | `validation/validator.py`, `reporting/`, `orchestrator.py`, `cli.py` | `TC-103`–`TC-112` |

---

## 2. Business-Rule Traceability Matrix (`BR-01` – `BR-12`)

| Rule ID | Rule Title | Linked Assumptions (`AS`) | Constraints | Algorithms | Constructive Module (Owner) | Audit Module | Test Coverage (`POS` / `NEG` / `BND` / `INT`) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BR-01** | Student examination clashes & `BACKLOG_CONSENT` | `AS-012`, `AS-013`, `AS-014` | `CN-07`, `CN-08` | `ALG-03`, `ALG-06`, `ALG-17` | `scheduling/conflict_graph.py` (Steven) | `validation/validator.py` | `TC-008`–`TC-013`, `TC-022`, `TC-075`, `TC-076`, `TC-083`, `TC-084` (11 TCs) |
| **BR-02** | Core examination gap (`>= 4` cr, `>= 1` full day, holidays count) | `AS-011`, `AS-016`, `AS-027` | `CN-09` | `ALG-04`, `ALG-06` | `scheduling/gap_validator.py` (Steven) | `validation/validator.py` | `TC-014`–`TC-019`, `TC-073`, `TC-105` (8 TCs) |
| **BR-03** | Deterministic heuristic & `SOFT_VIOLATION` fallback | `AS-006`, `AS-032` | `CN-10` | `ALG-05`, `ALG-06` | `scheduling/ordering.py`, `scheduler.py` (Steven) | `validation/validator.py` | `TC-016`, `TC-017`, `TC-020`–`TC-024`, `TC-109` (8 TCs) |
| **BR-04** | Session 90% capacity & `2h`/`3h` hall isolation | `AS-001`, `AS-002`, `AS-003` | `CN-11`, `CN-12` | `ALG-08`, `ALG-09` | `scheduling/scheduler.py` (Steven), `allocation/hall_allocator.py` (Tanisha) | `validation/validator.py` | `TC-023`, `TC-025`–`TC-030`, `TC-038`, `TC-096` (9 TCs) |
| **BR-05** | Largest hall first, max 2 courses, alt cols, `< 10` cross-dept merge | `AS-004`–`AS-008`, `AS-023`, `AS-024` | `CN-13`–`CN-16` | `ALG-09`–`ALG-11` | `allocation/hall_allocator.py`, `merge_policy.py` (Tanisha) | `validation/validator.py` | `TC-031`–`TC-043`, `TC-090`, `TC-103` (15 TCs) |
| **BR-06** | Row-major seating, alphabetical alt cols, ground-floor Row 1, `+20m` | `AS-003`, `AS-009`, `AS-010`, `AS-017` | `CN-17`–`CN-19` | `ALG-11`, `ALG-12` | `allocation/seat_assigner.py`, `accessibility.py` (Tanisha) | `validation/validator.py` | `TC-044`–`TC-051`, `TC-062`, `TC-092`, `TC-104`, `TC-107` (12 TCs) |
| **BR-07** | `ceil(n/30)` hall staff, `1` building chief, dept ban, `<=2`/day, `4..8`/wk | `AS-019`–`AS-021` | `CN-05`, `CN-20`–`CN-23` | `ALG-13`, `ALG-14` | `invigilation/eligibility.py`, `workload.py` (Mishael) | `validation/validator.py` | `TC-007`, `TC-052`–`TC-061`, `TC-094`, `TC-097`, `TC-104` (14 TCs) |
| **BR-08** | Deterministic invigilator sort, availability, `UNSTAFFED` reporting | `AS-018`, `AS-022`, `AS-029` | `CN-24` | `ALG-13`, `ALG-14` | `invigilation/invigilator_engine.py` (Mishael) | `validation/validator.py` | `TC-062`–`TC-070`, `TC-095`, `TC-105` (11 TCs) |
| **BR-09** | Course postponement (`{S_orig, S_dest}` blast radius) | `AS-026`, `AS-027`, `AS-031` | `CN-25` | `ALG-15`, `ALG-19` | `changes/postponement.py` (Tanisha) | `validation/validator.py` | `TC-071`–`TC-077`, `TC-097`, `TC-098` (9 TCs) |
| **BR-10** | Hall unavailability & smallest-course displacement | `AS-025`, `AS-027`, `AS-031` | `CN-26` | `ALG-16`, `ALG-19` | `changes/hall_unavailability.py` (Tanisha) | `validation/validator.py` | `TC-078`–`TC-082`, `TC-098` (6 TCs) |
| **BR-11** | Late registration (most free seats, `REJECTED_CLASH`) | `AS-028`–`AS-030` | `CN-27` | `ALG-17`, `ALG-19` | `changes/late_registration.py` (Tanisha) | `validation/validator.py` | `TC-083`, `TC-084`, `TC-091`–`TC-096`, `TC-098` (9 TCs) |
| **BR-12** | Supplementary exams (final 3 days `AN`; `> 50` allows `FN`) | `AS-012`, `AS-015`, `AS-016` | `CN-28` | `ALG-02`, `ALG-07` | `scheduling/supplementary.py` (Steven) | `validation/validator.py` | `TC-074`, `TC-085`–`TC-090` (7 TCs) |

---

## 3. Mandatory Edge-Case Traceability (`EC-01` – `EC-08`)

| Edge Case | Description | Governing Rules | Handling Algorithm | Verification Test IDs |
| :--- | :--- | :--- | :--- | :--- |
| **EC-01** | Two core courses of same programme-semester with only consecutive dates left | `BR-02`, `BR-03` | `ALG-04`, `ALG-06` (Pass 2 `CORE_GAP_SOFT_VIOLATION`) | `TC-016`, `TC-017` |
| **EC-02** | Course with `10` students vs course with `9` students | `BR-05` | `ALG-09`, `ALG-10` (`< 10` threshold) | `TC-034`, `TC-035`, `TC-036` |
| **EC-03** | Fractional 90% hall/aggregate capacity (`0.90 * 105 = 94.5`) | `BR-04` | `ALG-08` (`(90 * C) // 100` integer floor) | `TC-026`, `TC-027` |
| **EC-04** | Invigilator belonging to either department in a merged 2-course hall | `BR-05`, `BR-07`, `BR-08` | `ALG-13` (`v.department not in hall_depts`) | `TC-057` |
| **EC-05** | Special-needs student in 3h `AN` extending hall to `17:20` vs `17:30` / `17:15` duty | `BR-06`, `BR-08` | `ALG-12`, `ALG-13` (`TimeInterval(840, 1040)` overlap check) | `TC-062`, `TC-063`, `TC-064`, `TC-095` |
| **EC-06** | Postponement giving consenting backlog student 3 exams across 2 days | `BR-01`, `BR-02`, `BR-09` | `ALG-03`, `ALG-15` (per-date `BR-01` + `BACKLOG_CONSENT`) | `TC-075`, `TC-076` |
| **EC-07** | Student enrolled in two courses competing for the same earliest session | `BR-01`, `BR-03` | `ALG-03`, `ALG-06` (`ConflictGraph` filtering) | `TC-009`, `TC-010`, `TC-022` |
| **EC-08** | Final day of exam window having only an `FN` session available | `FR-02`, `BR-12` | `ALG-02`, `ALG-07` (`closed_slots` + `> 50` check) | `TC-006`, `TC-088`, `TC-089` |

---

## 4. Orphan & Completeness Audit

- **Unmapped Functional Requirements:** `0 / 6`
- **Unmapped Business Rules:** `0 / 12`
- **Unmapped Mandatory Edge Cases:** `0 / 8`
- **Unmapped Constraints:** `0 / 28` (`CN-01`–`CN-28` all trace to modules and test cases)
- **Unmapped Algorithms:** `0 / 20` (`ALG-01`–`ALG-20` all trace to modules and test cases)
- **Orphan Test Cases (without parent requirement):** `0 / 112`
