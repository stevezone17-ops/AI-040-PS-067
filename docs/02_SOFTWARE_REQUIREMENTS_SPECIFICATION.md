# 02 — Software Requirements Specification (SRS)

**Document Status:** Week 1 Design Baseline — Pending Team Confirmation & Mentor Approval  
**Related Documents:** [`04_BUSINESS_RULE_REGISTER.md`](04_BUSINESS_RULE_REGISTER.md), [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md), [`10_INPUT_OUTPUT_CONTRACTS.md`](10_INPUT_OUTPUT_CONTRACTS.md), [`15_REQUIREMENTS_TRACEABILITY_MATRIX.md`](15_REQUIREMENTS_TRACEABILITY_MATRIX.md)

---

## 1. Purpose & Audience

This Software Requirements Specification (SRS) establishes the complete functional (`FR-01`–`FR-06`) and non-functional (`NFR-01`–`NFR-08`) requirements for `AI-040-PS-067`. It serves as the authoritative contract between Week 1 design and Weeks 2–3 implementation so any developer on the team can implement and test modules without re-interpreting the problem statement.

---

## 2. System Operating Model

The system operates as a **batch and incremental command-file CLI engine**:
1. **Input Phase:** Reads static registry files (`courses`, `students`, `enrolments`, `halls`, `invigilators`, `exam_window`) and an optional ordered sequence of `commands`.
2. **Initial Synthesis Phase:** Validates inputs, builds the examination session timeline, schedules all courses (`FR-02`), allocates halls and individual seats (`FR-03`), staffs halls and building chiefs (`FR-04`), runs independent full-state validation, and writes initial outputs (`FR-06`).
3. **Incremental Change Phase:** Sequentially executes each change command (`FR-05`) on a candidate snapshot, recomputing **only** affected sessions, verifying global invariants, committing or rolling back atomically, and emitting updated artefacts and change audit logs (`FR-06`).

---

## 3. Functional Requirements

### FR-01 — Master Entity Registration & Input Validation

**Description:** The engine shall ingest, validate, and normalise master academic and infrastructure registries prior to scheduling.

| Sub-Requirement | Registered Entity | Mandatory Attributes & Domain Rules |
| :--- | :--- | :--- |
| **FR-01.1** | **Course** | `course_code` (unique ID), `department`, `semester` (`>= 1`), `credits` (`>= 0`; `>= 4` = Core, `< 4` = Elective per `BR-02`), `duration_hours` (`2` or `3` hours only), supplementary indicator (`BR-12`), and resolved student enrolment list. |
| **FR-01.2** | **Student** | `register_number` (unique ID), `programme`, `semester`, `special_needs` boolean flag (`BR-06`), `backlog_courses` collection, and `backlog_consent` boolean flag (`BR-01`). |
| **FR-01.3** | **Enrolment** | Canonical association linking `(register_number, course_code)` with enrolment category (`REGULAR` vs `BACKLOG`), deduplicated and cross-checked against student backlog declarations. |
| **FR-01.4** | **Hall** | `hall_id` (unique ID), `building_code`, `floor` (`0` = ground floor for accessibility per `BR-06`), `rows` (`>= 1`), `columns` (`>= 1`), and declared `capacity` (`1 <= capacity <= rows * columns`, `AS-003`). |
| **FR-01.5** | **Invigilator** | `invigilator_id` (unique ID), `department`, `max_weekly_sessions` (integer within `[4, 8]` per `BR-07`), `unavailable_dates`, and optional time-bounded external duties (`EC-05`, `AS-018`). |

**Acceptance Criteria:**
- Malformed records, missing required columns, out-of-range values (e.g., `duration_hours = 4`, `max_weekly_sessions = 9`), duplicate primary keys, or broken foreign keys (`enrolments` referencing unknown `course_code` or `register_number`) halt execution before scheduling with structured input validation errors (`CN-01`–`CN-06`).

---

### FR-02 — Examination Window Registration & Timetable Generation

**Description:** The engine shall register the dated examination calendar and assign each registered course to exactly one feasible examination session (or explicitly report unschedulable courses).

- **FR-02.1 (Calendar & Sessions):** Construct chronological sessions from `[start_date, end_date]`, excluding full-day `holidays` and session-specific closures (`AS-016`, `EC-08`), using fixed session slots:
  - `FN` (Forenoon): `09:30–12:30`
  - `AN` (Afternoon): `14:00–17:00`
- **FR-02.2 (Deterministic Ordering):** Order courses strictly by `(-enrolment_count, -credits, course_code)` (`BR-03`).
- **FR-02.3 (Constraint-Compliant Assignment):** Assign each course to the earliest eligible session satisfying:
  - Student same-session and daily clash rules, including `BACKLOG_CONSENT` (`BR-01`).
  - Aggregate 90% session seat limit and hall-level packability (`BR-04`, `BR-05`, `BR-06`).
  - Supplementary course window restrictions (`BR-12`: final 3 examination days, `AN` only for `<= 50` students, `FN` or `AN` for `> 50` students).
  - Programme-semester core examination gap (`BR-02`: `>= 1` full calendar day between core exams with `credits >= 4`; holidays count toward the calendar gap).
- **FR-02.4 (Soft-Gap Fallback):** If no session satisfies both hard rules and `BR-02`, assign the earliest session satisfying **all hard rules** and record a `SOFT_VIOLATION` (`BR-03`).
- **FR-02.5 (Infeasibility Reporting):** If no session satisfies all hard rules (even after deterministic small-course merge repair `AS-032`), leave the course `UNSCHEDULED` and report it in `violations.json` without violating hard rules.

---

### FR-03 — Student Hall Allocation & Seat Number Generation

**Description:** For every scheduled session, the engine shall allocate enrolled students into physical examination halls and assign deterministic individual seat coordinates.

- **FR-03.1 (Largest-First Hall Selection):** Select available halls in descending `capacity` order, breaking ties by ascending `hall_id` (`BR-05`, `AS-023`), while prioritising ground-floor halls (`floor == 0`) for courses containing special-needs students (`BR-06`, `AS-010`).
- **FR-03.2 (Duration & Course Count Compatibility):** Never mix 2-hour and 3-hour courses in the same hall (`BR-04`). Never place more than 2 distinct courses in any hall (`BR-05`).
- **FR-03.3 (Mandatory Small-Course Merging):** Any course with `1 <= enrolment_count < 10` must share a hall with another course of identical duration from a **different department** (`BR-05`, `EC-02`).
- **FR-03.4 (Alternate-Column Seating):** Partition hall columns into odd (`1, 3, 5, ...`) and even (`2, 4, 6, ...`) column sets (`AS-004`, `AS-005`) so no two students of the same course occupy horizontally adjacent columns (`BR-05`).
- **FR-03.5 (Row-Major Seat Numbering & Alphabetical Ordering):** Number physical seats in row-major order (`R01C01`..`R{R}C{C}`, seat index `1..R*C`). Seat students of each course alphabetically by `register_number` (`BR-06`).
- **FR-03.6 (Special-Needs Accommodation):** Place special-needs students in **Row 1 of a ground-floor hall** (`floor == 0`, `row == 1`) within their course's column set (`AS-009`), and extend that hall's effective end time by `+20` minutes (`BR-06`: `11:50`/`12:50` for `FN`; `16:20`/`17:20` for `AN`).

---

### FR-04 — Invigilator & Building Chief Assignment

**Description:** For every occupied hall and active building in each session, the engine shall assign eligible invigilators deterministically.

- **FR-04.1 (Staffing Headcount):** Assign `max(1, ceil(occupied_seats / 30))` hall invigilators per occupied hall (`BR-07`). Assign `1` additional Chief Invigilator per active building (any building with `>= 1` occupied hall in that session) (`BR-07`).
- **FR-04.2 (Eligibility Filtering):** Exclude invigilators who:
  - Belong to the department of **either** course seated in that hall (`BR-07`, `EC-04`; hall-level rule per `AS-019`).
  - Are unavailable on that session's date (`BR-08`) or have an external duty overlapping the hall's effective time window (including `+20` minute special-needs extension, `EC-05`, `AS-018`).
  - Are already assigned to another hall or building in the same session.
  - Already have `2` assigned sessions on that calendar date (`BR-07`).
  - Already reached their individual `max_weekly_sessions` (`4..8`) in that Monday–Sunday calendar week (`BR-07`, `AS-021`).
- **FR-04.3 (Deterministic Selection):** Sort eligible candidates by `(assigned_sessions_so_far, department, invigilator_id)` ascending (`BR-08`, `AS-022`).
- **FR-04.4 (Shortage Handling):** If fewer eligible invigilators exist than required, assign all available eligible candidates, mark the remaining slot(s) on the hall/building as `UNSTAFFED`, and log a resource-shortage entry in `violations.json` (`BR-08`). Never assign an ineligible invigilator.

---

### FR-05 — Incremental Change Command Processing

**Description:** The engine shall process an ordered sequence of post-scheduling change commands, recomputing **only** affected sessions and preserving unaffected assignments bit-for-bit.

- **FR-05.1 (`POSTPONE_COURSE` — `BR-09`):** Move a scheduled course to the earliest strictly later session satisfying all hard rules (validating student daily limits against fixed exams; applying `BR-02` gap with soft-violation fallback per `AS-027`). Regenerate hall allocations, seats, and invigilation rosters **only** for `S_source` and `S_dest`.
- **FR-05.2 (`MARK_HALL_UNAVAILABLE` — `BR-10`):** Mark a hall unavailable for a specified session (or date/window scope). Reallocate displaced students into the next largest available compatible hall(s) in `S_source`. If session/hall capacity is insufficient, move `S_source`'s smallest course `(enrolment_count, credits, course_code)` to the next free later session `S_dest` and flag `COURSE_DISPLACED_BY_HALL_CLOSURE`. Recompute **only** `S_source` (and `S_dest` if displacement occurred).
- **FR-05.3 (`ADD_LATE_REGISTRANT` — `BR-11`):** Register a new or additional student enrolment set. If any target course causes a student clash (`BR-01`), reject atomically with `REJECTED_CLASH` naming the two conflicting `course_code`s. Otherwise, seat the student in the eligible hall with the most free legal seats for each enrolled course (`AS-028`), incrementally adding an invigilator only if `ceil(n/30)` increases (`AS-029`).
- **FR-05.4 (Transactional Rollback):** If any change command cannot satisfy hard constraints, reject the command, restore the pre-command `ScheduleState` identically, and record the rejection reason in `change_results.json`.

---

### FR-06 — Deterministic Output & Report Generation

**Description:** The engine shall emit machine-readable and human-auditable schedule artefacts in deterministic canonical order (`AS-033`):

1. **Examination Timetable** (`timetable.csv`) — Session assignment per course.
2. **Hall Allocation Plan** (`hall_plan.csv`) — Course-to-hall occupancy, duration, extended end time, and headcount.
3. **Individual Seat Assignments** (`seat_assignments.csv`) — Student-level session, hall, row, column, and seat label.
4. **Hall Seat Maps** (`seat_maps.txt`) — Visual 2D ASCII matrix per `(session, hall)` showing seat labels, course codes, register numbers, and `[SN]` markers.
5. **Invigilation Roster** (`invigilation_roster.csv`) — Hall invigilators, building chiefs, duty intervals, and `UNSTAFFED` slots.
6. **Violations Report** (`violations.json`) — Structured record of `SOFT_VIOLATION`s, `UNSTAFFED` shortages, `UNSCHEDULED` courses, displacements, and rejected change diagnostics.
7. **State & Change Audit Logs** (`schedule_state.json`, `change_results.json`) — Serialised state and per-command execution outcomes (`APPLIED` vs `REJECTED_*`, affected sessions, diff verification).

---

## 4. Non-Functional Requirements

| ID | Category | Requirement Specification |
| :--- | :--- | :--- |
| **NFR-01** | **Determinism** | Identical input files and command sequences must produce byte-for-byte identical output files across runs, machines, and Python hash seeds (`PYTHONHASHSEED=random`). |
| **NFR-02** | **Auditability** | Every schedule state (initial and post-command) must pass an `IndependentScheduleValidator` that re-verifies `BR-01`–`BR-12` from scratch without sharing mutable state with scheduling engines. |
| **NFR-03** | **Blast-Radius Isolation** | Incremental changes (`FR-05`) must verify via cryptographic/structural snapshot hashing that every `session_id` outside `affected_sessions` has zero diff in courses, halls, seats, and invigilators. |
| **NFR-04** | **Performance** | Initial synthesis + 8 incremental commands on the expected dataset (120 courses, 2,500 students, 18 halls, 90 invigilators, 12 days) must complete in `< 5.0` seconds on a single CPU core. |
| **NFR-05** | **Dependency Minimalism** | Runtime engine must rely exclusively on the Python 3.10+ standard library (`dataclasses`, `enum`, `csv`, `json`, `math`, `datetime`, `pathlib`, `typing`, `argparse`). |
| **NFR-06** | **Schema Adaptability** | File parsing and formatting must be decoupled from domain models via adapter interfaces (`src/exam_engine/io/`) so official dataset formats can be plugged in without touching business logic. |
| **NFR-07** | **Failure Safety** | Hard constraints must never be silently relaxed. Infeasible inputs or impossible change commands fail explicitly with typed codes and preserve prior valid state. |
| **NFR-08** | **Maintainability** | Strict separation across 14 components, 100% type-annotated public signatures, Ruff-clean formatting, and clear per-member module ownership for viva examination. |
