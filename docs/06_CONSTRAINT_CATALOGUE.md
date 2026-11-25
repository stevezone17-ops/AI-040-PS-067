# 06 — Constraint Catalogue

**Document Status:** Week 1 Design Baseline — Authoritative Classification  
**Related Documents:** [`04_BUSINESS_RULE_REGISTER.md`](04_BUSINESS_RULE_REGISTER.md), [`05_ASSUMPTION_REGISTER.md`](05_ASSUMPTION_REGISTER.md), [`09_ALGORITHM_DESIGN.md`](09_ALGORITHM_DESIGN.md), [`14_TEST_CASE_CATALOGUE.md`](14_TEST_CASE_CATALOGUE.md)

---

## 1. Taxonomy of System Outcomes & Failure Concepts

A frequent defect in scheduling engines is conflating malformed input data, inviolable hard rules, permitted soft fallbacks, staffing shortages, and rejected change commands. Our architecture strictly separates **seven distinct operational concepts**:

| Concept Category | Severity / Nature | Engine Behaviour | Mutates Active Schedule? | Emitted Artefact |
| :--- | :--- | :--- | :---: | :--- |
| **1. Invalid Input** (`INVALID_INPUT`) | Fatal pre-execution schema/domain error | Abort run immediately before synthesis; return non-zero CLI exit code (`2`) with structured diagnostics. | No (run never starts) | `stderr` + validation error report |
| **2. Hard-Constraint Violation** (`HARD_CONSTRAINT`) | Inviolable domain invariant (`BR-01`, `BR-04`, `BR-05`, `BR-06`, `BR-07`, `BR-12`) | **Never permitted** in any committed `ScheduleState`. Constructive engines skip invalid slots; if `IndependentScheduleValidator` detects one, it raises `ScheduleIntegrityError` (exit code `3`). | Never | Prevented by construction; audited by `ALG-18` |
| **3. Permitted Soft Violation** (`SOFT_VIOLATION`) | Controlled fallback exclusively for `BR-02` core-course gap (`BR-03`) | Allowed **only** when zero hard-feasible sessions satisfy `BR-02`. Never relaxes any hard constraint. | Yes (valid schedule) | `violations.json` (`CORE_GAP_SOFT_VIOLATION`) |
| **4. Resource Shortage** (`RESOURCE_SHORTAGE`) | Explicit operational staffing deficit (`BR-08` `UNSTAFFED`) | Schedule and student seating remain valid; unfilled invigilator/chief slot marked `UNSTAFFED`. **Never** assigns an ineligible invigilator. | Yes (marked `UNSTAFFED`) | `invigilation_roster.csv` + `violations.json` |
| **5. Unscheduled Course** (`UNSCHEDULED_COURSE`) | Dataset-level hard infeasibility during initial scheduling | Course cannot fit in **any** session without violating a hard rule. Course left unassigned (`None`) rather than breaking hard rules. | Partial valid schedule | `violations.json` (`UNSCHEDULED_*`) |
| **6. Incomplete Allocation** (`INCOMPLETE_ALLOCATION`) | Transient internal trial-packing state (e.g., unmerged `<10` course or unseated student) | Treated as **infeasible** during candidate session check (`ALG-08`); never allowed to commit into `ScheduleState`. | Never committed | Internal rejection -> triggers next session / `UNSCHEDULED` |
| **7. Rejected Change Command** (`REJECTED_CHANGE`) | Impossible post-scheduling mutation (`BR-09`, `BR-10`, `BR-11`) | Candidate snapshot discarded; prior valid `ScheduleState` preserved bit-for-bit; rejection code logged (`REJECTED_CLASH`, etc.). | **No** (rolled back) | `change_results.json` + `violations.json` (`rejected_changes`) |

> [!CAUTION]
> **Two Absolute Non-Negotiable Guardrails:**
> 1. **Gap-Fallback Isolation:** Falling back on `BR-02` (`CORE_GAP_SOFT_VIOLATION`) **never** authorises violating `BR-01` (student clashes), `BR-04` (90% cap / duration), `BR-05` (column adjacency / small-course merge), `BR-06` (ground-floor Row 1), or `BR-12` (supplementary window).
> 2. **Staffing Purity:** `UNSTAFFED` (`BR-08`) is a reportable human-resource shortage—**never** an excuse to assign an invigilator from an excluded department, on an unavailable date, or above daily/weekly limits.

---

## 2. Master Constraint Catalogue (`CN-01` – `CN-28`)

### 2.1 Input Integrity Constraints (`CN-01` – `CN-06`)

| ID | Parent Rule | Classification | Validation Inputs | Formal Validation Condition | Failure Behaviour & Code | Responsible Component | Related Tests |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CN-01** | `FR-01` | Invalid Input | `courses.csv` | Unique `course_code`; `semester >= 1`; `credits >= 0`; `duration_hours in {2, 3}`. | Abort run: `ERR_INVALID_COURSE` | `io/validators.py` | `TC-001`, `TC-002` |
| **CN-02** | `FR-01` | Invalid Input | `students.csv` | Unique `register_number`; non-empty `programme`; `semester >= 1`; boolean flags valid. | Abort run: `ERR_INVALID_STUDENT` | `io/validators.py` | `TC-003` |
| **CN-03** | `FR-01` | Invalid Input | `enrolments.csv`, `students`, `courses` | Every `(register_number, course_code)` references existing `Student` and `Course`; duplicate pairs rejected (or flagged per `10_INPUT_OUTPUT_CONTRACTS.md` -> reject `ERR_DUPLICATE_ENROLMENT`). | Abort run: `ERR_UNKNOWN_REFERENCE` / `ERR_DUPLICATE_ENROLMENT` | `io/validators.py` | `TC-005`, `TC-099`, `TC-100` |
| **CN-04** | `FR-01`, `AS-003` | Invalid Input | `halls.csv` | Unique `hall_id`; `rows >= 1`, `columns >= 1`; `floor >= 0`; `1 <= capacity <= rows * columns`. | Abort run: `ERR_INVALID_HALL_DIMENSIONS` | `io/validators.py` | `TC-004` |
| **CN-05** | `FR-01`, `BR-07` | Invalid Input | `invigilators.csv` | Unique `invigilator_id`; non-empty `department`; `4 <= max_weekly_sessions <= 8`; valid ISO dates/intervals. | Abort run: `ERR_INVALID_INVIGILATOR` | `io/validators.py` | `TC-007` |
| **CN-06** | `FR-02` | Invalid Input | `exam_window.json` | `start_date <= end_date`; after removing holidays and closed slots, `len(active_sessions) >= 1`. | Abort run: `ERR_EMPTY_EXAM_WINDOW` | `io/validators.py`, `scheduling/session_generator.py` | `TC-006`, `TC-101` |

---

### 2.2 Temporal & Student Scheduling Constraints (`CN-07` – `CN-11`, `CN-28`)

| ID | Parent Rule | Classification | Validation Inputs | Formal Validation Condition | Failure Behaviour & Code | Responsible Component | Related Tests |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CN-07** | `BR-01` | Hard Constraint | `Student`, `Enrolment`, `ExamAssignment` | $\forall$ student $s$, session $\tau$: at most `1` enrolled course assigned to $\tau$. | Skip session during scheduling; reject change (`REJECTED_CLASH`). | `scheduling/conflict_graph.py`, `validation/validator.py` | `TC-008`, `TC-009`, `TC-083` |
| **CN-08** | `BR-01`, `AS-013` | Hard Constraint | `Student`, `Enrolment`, `ExamAssignment` | $\forall$ student $s$, date $d$: either $\le 1$ exam on $d$, OR ($2$ exams in `{FN, AN}` AND `s.backlog_consent == True` AND $\ge 1$ exam has `is_backlog == True`). | Skip session during scheduling; reject change (`REJECTED_CLASH`). | `scheduling/conflict_graph.py`, `validation/validator.py` | `TC-010`–`TC-013`, `TC-075`, `TC-076` |
| **CN-09** | `BR-02`, `AS-011` | Soft Constraint (Gap Rule) | Core `Course`s (`credits >= 4`), cohorts, `ExamSession` | $\forall$ distinct core courses $c_1, c_2$ sharing a regular `(programme, semester)` cohort: $|\text{date}(c_1) - \text{date}(c_2)| \ge 2$ calendar days (holidays counted). | Pass 1 skips violating slot; if no Pass 1 slot exists, Pass 2 selects earliest hard-valid slot & logs `CORE_GAP_SOFT_VIOLATION`. | `scheduling/gap_validator.py`, `validation/validator.py` | `TC-014`–`TC-019` |
| **CN-10** | `BR-03`, `AS-032` | Deterministic Policy | All `Course`s, `ExamSession`s | Courses processed strictly in `(-enrolment_count, -credits, course_code)` order; earliest feasible chronological session chosen. | If zero hard-valid sessions exist, mark course `UNSCHEDULED` in `violations.json`. | `scheduling/ordering.py`, `scheduling/scheduler.py` | `TC-020`–`TC-024` |
| **CN-11** | `BR-04`, `AS-001`, `AS-002` | Hard Constraint | Session courses, available `Hall`s | $\sum_{c \in \tau} |E(c)| \le (90 \times \sum_{h \in H_{\text{avail}}(\tau)} h.\text{capacity}) // 100$. | Skip session during scheduling; trigger displacement (`BR-10`) or reject change (`REJECTED_SESSION_CAPACITY`). | `scheduling/scheduler.py`, `validation/validator.py` | `TC-025`–`TC-027` |
| **CN-28** | `BR-12`, `AS-015` | Hard Constraint | Supplementary `Course`, `ExamWindow` | If `c.is_supplementary`: `date(c)` in final 3 active exam dates AND (`slot(c) == AN` OR `len(c.enrolments) > 50`). | Exclude ineligible sessions; if none left, mark `UNSCHEDULED_SUPPLEMENTARY_NO_SLOT`. | `scheduling/supplementary.py`, `validation/validator.py` | `TC-085`–`TC-090` |

---

### 2.3 Spatial Hall, Seating & Accessibility Constraints (`CN-12` – `CN-19`)

| ID | Parent Rule | Classification | Validation Inputs | Formal Validation Condition | Failure Behaviour & Code | Responsible Component | Related Tests |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CN-12** | `BR-04` | Hard Constraint | `HallAllocation` | All courses allocated to the same `(session, hall)` have identical `duration_hours` (`2` or `3`). | Forbid hall sharing across mixed durations; open separate hall or reject session. | `allocation/hall_allocator.py`, `validation/validator.py` | `TC-028`–`TC-030` |
| **CN-13** | `BR-05`, `AS-023` | Deterministic Policy | Available `Hall`s in session | Halls filled in descending `capacity`, tie-broken by ascending `hall_id` (with `floor == 0` prioritised for unresolved `special_needs` courses per `AS-010`). | Enforced constructively by `ALG-09` and verified by determinism tests. | `allocation/hall_allocator.py` | `TC-031`–`TC-033` |
| **CN-14** | `BR-05` | Hard Constraint | `HallAllocation` | Every occupied hall contains `1` or `2` distinct courses (`len(hall_courses) <= 2`). | Never place a 3rd course in any hall; move to next hall or fail session packing. | `allocation/hall_allocator.py`, `validation/validator.py` | `TC-033` |
| **CN-15** | `BR-05`, `AS-004`, `AS-005` | Hard Constraint | `SeatAssignment`s in `(session, hall)` | No two students of the same `course_code` sit in horizontally adjacent columns (`|col_a - col_b| != 1`), even in the same or different rows (enforced via odd Set A / even Set B column partitioning), and total seats in hall $\le h.\text{capacity}$. | Bound single-course seats per hall to $\min(h.\text{capacity}, h.\text{rows} \times |Set|)$; reject session if unpackable. | `allocation/seat_assigner.py`, `validation/validator.py` | `TC-041`–`TC-045` |
| **CN-16** | `BR-05`, `EC-02`, `AS-006` | Hard Constraint | Small `Course` (`1 <= enrolment < 10`), `HallAllocation` | Every hall slice of a course with `1 <= enrolment < 10` shares its hall with a 2nd course $c'$ where `c'.department != c.department` and `c'.duration_hours == c.duration_hours`. | Trigger partner-aware session selection/repair (`ALG-06`/`ALG-10`); mark `UNSCHEDULED` if impossible. | `allocation/merge_policy.py`, `validation/validator.py` | `TC-034`–`TC-040` |
| **CN-17** | `BR-06`, `AS-009` | Deterministic Policy & Hard Rule | `SeatAssignment`s | Seats numbered row-major `R{r:02d}C{c:02d}`; within each course's column set, `special_needs` students seated alphabetically in Row 1 (`floor == 0`), followed by regular students alphabetically in row-major order. | Enforced constructively in `ALG-11`/`ALG-12`; audited in `ALG-18`. | `allocation/seat_assigner.py`, `validation/validator.py` | `TC-044`–`TC-048` |
| **CN-18** | `BR-06`, `AS-010` | Hard Constraint | `Student` (`special_needs=True`), `Hall`, `SeatAssignment` | Every student with `special_needs == True` is assigned to a hall with `floor == 0` and seat with `row == 1`. | Reserve ground-floor Row 1 slots; skip session if insufficient; mark `UNSCHEDULED` (`INSUFFICIENT_ACCESSIBLE_SEATS`) or reject late reg (`REJECTED_ACCESSIBILITY_CAPACITY`). | `allocation/accessibility.py`, `validation/validator.py` | `TC-046`–`TC-050` |
| **CN-19** | `BR-06`, `AS-017` | Hard Constraint | `HallAllocation`, `Student` | If `(session, hall)` seats $\ge 1$ `special_needs` student, `effective_end_time = session_start + duration + 20 min`; else `session_start + duration`. | Propagated directly to invigilator time-overlap checker (`CN-24`) and reports. | `allocation/accessibility.py`, `validation/validator.py` | `TC-051`, `TC-062` |

---

### 2.4 Invigilation & Workload Constraints (`CN-20` – `CN-24`)

| ID | Parent Rule | Classification | Validation Inputs | Formal Validation Condition | Failure Behaviour & Code | Responsible Component | Related Tests |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CN-20** | `BR-07` | Resource Requirement | Occupied `HallAllocation` ($n_h > 0$), active `Building` | Hall invigilator slots $= \max(1, \lceil n_h / 30 \rceil)$; active building Chief slots $= 1$ per session. | Any unfilled required slot becomes `UNSTAFFED` (`RESOURCE_SHORTAGE` in `violations.json`). | `invigilation/invigilator_engine.py`, `validation/validator.py` | `TC-052`–`TC-055`, `TC-058` |
| **CN-21** | `BR-07`, `EC-04`, `AS-019` | Hard Constraint | `Invigilator`, `HallAllocation` | For every hall invigilator $v$ assigned to hall $h$: $v.\text{department} \notin \{c.\text{department} : c \in h.\text{courses}\}$. Also at most 1 duty per invigilator per session. | Exclude $v$ from candidate pool; never assign. | `invigilation/eligibility.py`, `validation/validator.py` | `TC-056`, `TC-057`, `TC-059` |
| **CN-22** | `BR-07`, `AS-020` | Hard Constraint | `Invigilator`, `InvigilationAssignment`s on date $d$ | Total duties (hall + chief) for invigilator $v$ on date $d \le 2$. | Exclude $v$ once daily count $= 2$. | `invigilation/workload.py`, `validation/validator.py` | `TC-060` |
| **CN-23** | `BR-07`, `AS-021` | Hard Constraint | `Invigilator`, `InvigilationAssignment`s in ISO week $w$ | Total duties (hall + chief) for invigilator $v$ in Monday–Sunday week $w \le v.\text{max\_weekly\_sessions}$. | Exclude $v$ once weekly count $= v.\text{max\_weekly\_sessions}$. | `invigilation/workload.py`, `validation/validator.py` | `TC-061` |
| **CN-24** | `BR-08`, `EC-05`, `AS-018`, `AS-022` | Hard Availability + Deterministic Policy + Shortage Reporting | `Invigilator`, `unavailable_dates`, external duties, `effective_end_time` | $d \notin v.\text{unavailable\_dates}$ AND no overlap with external duties; eligible pool sorted by `(assigned_so_far, department, invigilator_id)`. | Exhausted pool -> emit `HALL_UNSTAFFED` or `BUILDING_CHIEF_UNSTAFFED` in `violations.json`. | `invigilation/invigilator_engine.py`, `validation/validator.py` | `TC-062`–`TC-070` |

---

### 2.5 Incremental Change & Transactional Constraints (`CN-25` – `CN-27`)

| ID | Parent Rule | Classification | Validation Inputs | Formal Validation Condition | Failure Behaviour & Code | Responsible Component | Related Tests |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CN-25** | `BR-09`, `AS-026`, `AS-027`, `AS-031` | Incremental Change + Blast-Radius Invariant | `POSTPONE_COURSE` command, `ScheduleState` | Target `S_dest > S_orig` satisfies all hard rules (and `BR-02` with soft fallback); **only** `{S_orig, S_dest}` recomputed; all $\tau \notin \{S_{\text{orig}}, S_{\text{dest}}\}$ byte-identical before & after. | Rollback candidate state; emit `REJECTED_NO_FEASIBLE_SESSION` (or `REJECTED_SOURCE_ORPHANED`). | `changes/postponement.py`, `changes/state_manager.py` | `TC-071`–`TC-077`, `TC-098` |
| **CN-26** | `BR-10`, `AS-025`, `AS-031` | Incremental Change + Blast-Radius Invariant | `MARK_HALL_UNAVAILABLE` command, `ScheduleState` | Displaced students repacked into largest free compatible hall(s) in `S_orig`; else smallest course(s) moved to next free later session(s) `S_dest` & flagged `COURSE_DISPLACED_BY_HALL_CLOSURE`; all other sessions unchanged. | Rollback candidate state if unrecoverable; emit `REJECTED_HALL_CLOSURE_INFEASIBLE`. | `changes/hall_unavailability.py`, `changes/state_manager.py` | `TC-078`–`TC-082`, `TC-098` |
| **CN-27** | `BR-11`, `AS-028`–`AS-030` | Incremental Change + Atomic Clash Check | `ADD_LATE_REGISTRANT` command, `ScheduleState` | Zero `BR-01` clashes across student's courses; seated in eligible hall with most free seats per course; delta invigilator added only if $\lceil n/30 \rceil$ rises; atomic across all courses in command. | Rollback all tentative seats in command; emit `REJECTED_CLASH` (with 2 conflicting `course_code`s) or `REJECTED_HALL_CAPACITY` / `REJECTED_SESSION_CAPACITY` / `REJECTED_ACCESSIBILITY_CAPACITY`. | `changes/late_registration.py`, `changes/state_manager.py` | `TC-083`, `TC-084`, `TC-091`–`TC-098` |
