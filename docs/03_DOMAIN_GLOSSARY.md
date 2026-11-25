# 03 — Domain Glossary

**Document Status:** Week 1 Design Baseline — Mandatory Deliverable  
**Purpose:** Establish unambiguous, project-wide definitions for every domain and architectural term used across requirements, code identifiers, algorithms, and viva discussions.

---

## 1. Academic & Examination Terms

| Term | Canonical Definition | Related Rules / Entities |
| :--- | :--- | :--- |
| **Active Building** | A physical university building containing **at least one occupied hall** during a specific `ExamSession`. Requires exactly one additional Chief Invigilator in that session. | `BR-07`, `Building` |
| **Afternoon Session (`AN`)** | The second daily examination slot, scheduled from **`14:00` to `17:00`** (standard 3h end; `16:00` for 2h; `+20` min to `16:20`/`17:20` with special-needs students). | `FR-02`, `BR-06`, `AS-017` |
| **Alternate-Column Seating** | Anti-collusion seating rule requiring students of the same course to sit only in non-adjacent columns: either **Column Set A** (`1, 3, 5, ...`) or **Column Set B** (`2, 4, 6, ...`). | `BR-05`, `BR-06`, `AS-004`, `AS-005` |
| **Backlog Consent (`BACKLOG_CONSENT`)** | Explicit boolean declaration on a `Student` permitting up to **two examinations on the same calendar day** provided they occur in different sessions (`FN` and `AN`) and involve a backlog enrolment (`AS-013`). | `FR-01`, `BR-01`, `Student` |
| **Backlog Enrolment** | A student's registration in an arrear/repeat course from a prior semester (either a dedicated supplementary paper or a regular lower-semester course repeated alongside current courses). | `FR-01`, `BR-01`, `AS-012`, `Enrolment` |
| **Chief Invigilator (Building Chief)** | One senior/additional invigilator assigned per **active building per session** (`BR-07`), distinct from hall invigilators, whose duty counts toward daily and weekly session caps (`AS-020`). | `BR-07`, `BR-08`, `AS-019`, `AS-020` |
| **Core Course** | Any course with **`credits >= 4`**. Consecutive core examinations for the same `(programme, semester)` cohort require at least one full calendar day gap (`BR-02`). | `BR-02`, `Course` |
| **Course Displacement** | Automatic relocation of a session's smallest course `(enrolment_count, credits, course_code)` to the next free later session when a hall closure leaves insufficient capacity in the original session. | `BR-10`, `AS-025` |
| **Declared Hall Capacity** | The official maximum student count (`capacity`) registered for a `Hall` (`capacity <= rows * columns`). | `FR-01`, `BR-04`, `AS-003` |
| **Effective Hall End Time** | Actual clock time when invigilation concludes in an occupied hall: base duration (`+2h` or `+3h` from session start) plus `+20` minutes if `>= 1` special-needs student is seated in that hall. | `BR-06`, `EC-05`, `AS-017` |
| **Elective Course** | Any course with **`credits < 4`**. Exempt from the `BR-02` calendar-day gap rule. | `BR-02`, `Course` |
| **Examination Session (`ExamSession`)** | A unique schedulable `(date, slot)` pair (e.g., `2026-12-01_FN`), ordered chronologically across the `ExamWindow`. | `FR-02`, `ExamSession` |
| **Examination Window (`ExamWindow`)** | The bounded range of calendar dates `[start_date, end_date]`, minus full-day `holidays` and session closures, within which all examinations take place. | `FR-02`, `ExamWindow` |
| **Forenoon Session (`FN`)** | The first daily examination slot, scheduled from **`09:30` to `12:30`** (standard 3h end; `11:30` for 2h; `+20` min to `11:50`/`12:50` with special-needs students). | `FR-02`, `BR-06`, `AS-017` |
| **Full Calendar Day Gap** | At least one complete intervening calendar date between two exam dates: `\|date_2 - date_1\| >= 2` days (e.g., Monday to Wednesday has Tuesday between them). Holidays count as intervening calendar days. | `BR-02` |
| **Ground-Floor Hall** | An examination hall with `floor == 0`, eligible to seat special-needs students in Row 1 (`row == 1`). | `FR-01`, `BR-06` |
| **Holiday** | A calendar date inside `ExamWindow` on which no examinations may be scheduled, but which **does** count toward the `BR-02` calendar-day gap between core examinations. | `FR-02`, `BR-02`, `AS-016` |
| **Late Registrant** | A student added after initial timetable generation via `ADD_LATE_REGISTRANT`, seated incrementally in free hall seats without disturbing existing assignments, or rejected on clash/capacity failure. | `FR-05`, `BR-11` |
| **Merged Hall** | A single examination hall hosting **two distinct courses** of identical exam duration (`2h` or `3h`) in separate alternate column sets (Set A odd, Set B even). | `BR-04`, `BR-05`, `EC-04` |
| **Programme-Semester Cohort** | A distinct `(programme, semester)` student group (e.g., `("BTech-AIML", 6)`) for whom consecutive core courses must satisfy `BR-02`. | `BR-02`, `AS-011` |
| **Row-Major Seat Order** | Deterministic numbering of seats across rows top-to-bottom (`row = 1..rows`) and within each row left-to-right (`col = 1..columns`), yielding index `(row - 1) * columns + col` and label `R{row:02d}C{col:02d}`. | `BR-06` |
| **Session Aggregate Capacity Cap** | The `BR-04` limit restricting total students scheduled in any session `S` to at most **`floor(0.90 * sum_of_available_hall_capacities_in_S)`**. | `BR-04`, `EC-03`, `AS-001`, `AS-002` |
| **Small Course** | Any course with **`1 <= enrolment_count < 10`** (i.e., 1 to 9 students). Must be merged into a hall containing another course from a **different department** and identical exam duration (`BR-05`). A 10-student course is **not** a small course (`EC-02`). | `BR-05`, `EC-02`, `AS-006` |
| **Special-Needs Student** | A student flagged `special_needs == True`, entitled to **Row 1 of a ground-floor hall** and **20 extra minutes** of examination time. | `FR-01`, `BR-06`, `EC-05` |
| **Supplementary Examination** | A dedicated backlog course (`is_supplementary == True`) restricted by `BR-12` to the **final three active examination days** in `AN` sessions (or `FN`+`AN` if `enrolment_count > 50`). | `BR-12`, `EC-08`, `AS-012`, `AS-015` |

---

## 2. Architectural, Constraint & Diagnostic Terms

| Term | Canonical Definition | Related Documents |
| :--- | :--- | :--- |
| **Affected Sessions (Blast Radius)** | The minimal subset of `ExamSession` IDs whose allocations may legally be recomputed during a `ChangeCommand` (e.g., `{S_source, S_dest}` for postponement). All other sessions are frozen. | [`11_INCREMENTAL_RECOMPUTATION.md`](11_INCREMENTAL_RECOMPUTATION.md) |
| **Candidate State** | An isolated deep copy / copy-on-write clone of `ScheduleState` on which a `ChangeCommand` is tentatively executed and validated before atomic commit or rollback. | [`11_INCREMENTAL_RECOMPUTATION.md`](11_INCREMENTAL_RECOMPUTATION.md) |
| **Conflict Graph** | Undirected weighted graph `G = (V, E)` where vertices `V` are courses and an edge `(u, v)` exists iff `>= 1` student is enrolled in both `u` and `v` (annotated with regular vs consenting-backlog overlap). | [`09_ALGORITHM_DESIGN.md`](09_ALGORITHM_DESIGN.md) (`ALG-03`) |
| **Hard Constraint** | An inviolable domain rule (`BR-01`, `BR-04`, `BR-05`, `BR-06`, `BR-07` eligibility, `BR-12`). Never relaxed silently; violation blocks slot selection or rejects a change command. | [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md) |
| **Independent Schedule Validator** | A standalone verification component (`ALG-18`) that audits any `ScheduleState` against `BR-01`–`BR-12` without sharing code paths or caches with the constructive engines. | [`07_SYSTEM_ARCHITECTURE.md`](07_SYSTEM_ARCHITECTURE.md) |
| **Rejected Change (`REJECTED_*`)** | Clean transactional refusal of an incremental `ChangeCommand` (such as `REJECTED_CLASH`) that leaves the pre-command `ScheduleState` completely unmodified. | [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md) |
| **Resource Shortage (`UNSTAFFED`)** | Explicit operational condition under `BR-08` when eligible invigilators are exhausted for a hall or building; recorded in `violations.json` rather than assigning an ineligible invigilator. | `BR-08`, [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md) |
| **Soft Violation (`SOFT_VIOLATION`)** | Formally permitted fallback recorded when `BR-02` core-course gap cannot be met by any hard-feasible session (`BR-03`). Never permits breaking any hard constraint. | `BR-02`, `BR-03`, [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md) |
| **Unscheduled Course (`UNSCHEDULED`)** | Explicit failure state when zero sessions in `ExamWindow` satisfy all hard constraints for a course during initial scheduling; reported in `violations.json`. | [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md) |
