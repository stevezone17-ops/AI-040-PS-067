# 05 — Assumption Register

**Document Status:** Provisional Design Baseline — Pending Mentor Clarification & Sample Dataset Verification  
**Related Documents:** [`04_BUSINESS_RULE_REGISTER.md`](04_BUSINESS_RULE_REGISTER.md), [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md), [`09_ALGORITHM_DESIGN.md`](09_ALGORITHM_DESIGN.md), [`14_TEST_CASE_CATALOGUE.md`](14_TEST_CASE_CATALOGUE.md)

---

## 1. Ambiguity Resolution Protocol

Because mentor clarification and official sample files are unavailable during Week 1, every specification ambiguity identified in [`04_BUSINESS_RULE_REGISTER.md`](04_BUSINESS_RULE_REGISTER.md) is resolved below using a strict 9-field engineering protocol:
1. **Assumption ID** (`AS-001`–`AS-033`)
2. **Parent Rule(s)**
3. **Ambiguity Description**
4. **Reasonable Interpretations**
5. **Selected Provisional Interpretation**
6. **Engineering Rationale**
7. **Affected Modules & Test Cases**
8. **Change Isolation Strategy** *(isolated in dedicated policy/validator functions—never scattered across magic constants or arbitrary CLI flags)*
9. **Resolvable via Official Sample Outputs?**

> [!WARNING]
> **Distinction Notice:** Items in [`04_BUSINESS_RULE_REGISTER.md`](04_BUSINESS_RULE_REGISTER.md) are **official capstone requirements**. All selections in this document are **team-proposed provisional interpretations** designed to preserve strict hard-rule safety until official expected outputs are inspected.

---

## 2. Capacity, Geometry & Hall Packing Assumptions (`AS-001` – `AS-010`)

### AS-001 — Aggregate vs. Per-Hall 90% Capacity Limit
- **Parent Rule:** `BR-04` (*"Total seats used in a session must not exceed 90% of total available hall capacity."*)
- **Ambiguity:** Whether the 90% ceiling restricts the **sum of seats across all available halls** in a session, or restricts **each individual hall** to 90% of its own capacity.
- **Interpretations:**
  - *Option A:* Session-wide aggregate cap: $\sum \text{seats\_used} \le \lfloor 0.90 \times \sum_{h \in H_{\text{avail}}} h.\text{capacity} \rfloor$; individual halls may fill up to their physical alternate-column / declared limit.
  - *Option B:* Per-hall cap: every hall $h$ capped at $\lfloor 0.90 \times h.\text{capacity} \rfloor$.
- **Provisional Selection:** **Option A (Aggregate available session capacity).**
- **Rationale:** Literally matches the phrasing *"Total seats used in a session ... of total available hall capacity"* and aligns with recommended capstone defaults. Furthermore, alternate-column seating (`BR-05`) already bounds single-course occupancy per hall to $\sim 50\%$.
- **Affected Modules & Tests:** `scheduling/scheduler.py`, `allocation/hall_allocator.py`, `validation/validator.py`; `TC-025`, `TC-026`, `TC-027`.
- **How to Change Later:** Modify `SessionCapacityPolicy.max_session_seats()` and `HallCapacityPolicy.max_hall_seats()` in `allocation/policies.py`.
- **Sample Output Resolvable?** **Yes** — any sample hall filled between 91% and 100% proves Option A.

### AS-002 — Fractional Capacity Rounding
- **Parent Rule:** `BR-04`, `EC-03`
- **Ambiguity:** When $0.90 \times \text{TotalCapacity}$ is non-integral (e.g., $0.90 \times 105 = 94.5$), whether to apply `floor` (94), `round` (95), or `ceil` (95).
- **Interpretations:** *Option A:* `math.floor` (`94`); *Option B:* Half-up rounding (`95`); *Option C:* `math.ceil` (`95`).
- **Provisional Selection:** **Option A (`math.floor`, implemented via integer arithmetic `(90 * total_cap) // 100`).**
- **Rationale:** *"Must not exceed 90%"* is an upper-bound inequality ($n \le 0.90 C$). For $C=105$, $95 / 105 = 90.476\% > 90\%$, which violates the upper bound. Integer arithmetic `(90 * C) // 100` also eliminates IEEE-754 floating-point representation drift.
- **Affected Modules & Tests:** `allocation/policies.py`, `validation/validator.py`; `TC-026`, `TC-027`.
- **How to Change Later:** Single helper `compute_ninety_percent_cap(total_capacity: int) -> int`.
- **Sample Output Resolvable?** **Likely**, if sample total hall capacity is not a multiple of 10 and a session packs near capacity.

### AS-003 — Physical Seat Grid (`rows * columns`) vs. Declared Hall Capacity
- **Parent Rule:** `FR-01`, `BR-04`, `BR-06`
- **Ambiguity:** A hall record declares `capacity`, `rows`, and `columns`. What happens if `capacity < rows * columns` (e.g., broken/pillar seats or fire limit) or `capacity > rows * columns`?
- **Interpretations:**
  - *Option A:* Reject `capacity > rows * columns` as invalid input; allow `capacity <= rows * columns` where `capacity` bounds both `BR-04` total capacity and maximum assignable seats in that hall.
  - *Option B:* Require exact equality `capacity == rows * columns`.
- **Provisional Selection:** **Option A (`1 <= capacity <= rows * columns`; `effective_capacity = capacity`).**
- **Rationale:** Real university halls frequently have `rows * cols = 64` physical grid coordinates with a fire/desk limit of `60`, while `capacity > rows * cols` is physically impossible to seat in a `rows x cols` map.
- **Affected Modules & Tests:** `io/parsers.py`, `allocation/seat_assigner.py`; `TC-004`, `TC-045`.
- **How to Change Later:** Adjust `validate_hall_dimensions()` in `io/validators.py`.
- **Sample Output Resolvable?** **Yes** — inspect `halls.csv` in official sample dataset.

### AS-004 — Single-Course Alternate-Column Seating
- **Parent Rule:** `BR-05`, `BR-06`
- **Ambiguity:** When a single course ($\ge 10$ students) occupies a hall alone with no second course merged into it, may its students sit in **every** column, or must they still sit in **alternate columns** only?
- **Interpretations:**
  - *Option A:* Alternate columns (`1, 3, 5, ...`) always enforced, leaving even columns (`2, 4, ...`) empty unless a second course shares the hall.
  - *Option B:* Alternate columns enforced only when two courses share a hall.
- **Provisional Selection:** **Option A (Unconditional alternate-column seating per course).**
- **Rationale:** `BR-05` states *"Students from the same course may not occupy adjacent columns"* (anti-cheating rule—most critical when only one course is in the room!) and `BR-06` states *"Students of a course are seated alphabetically by register number in alternate columns."* Thus a single course in a `R x C` hall can use at most $\min(\text{capacity}, R \times \lceil C/2 \rceil)$ seats in that hall (overflowing remaining students of that course into the next largest hall!).
- **Affected Modules & Tests:** `allocation/hall_allocator.py`, `allocation/seat_assigner.py`, `validation/validator.py`; `TC-031`, `TC-041`.
- **How to Change Later:** Encapsulated in `ColumnPartitionPolicy.usable_columns_for_slot()` in `allocation/seat_assigner.py`.
- **Sample Output Resolvable?** **Yes** — immediately visible in `seat_assignments.csv` and `seat_maps.txt`.

### AS-005 — Odd and Even Column Counts in Alternate-Column Geometry
- **Parent Rule:** `BR-05`, `BR-06`
- **Ambiguity:** In a hall with an **odd** number of columns (e.g., `7` columns), how are alternate columns partitioned between Course Slot A and Course Slot B?
- **Interpretations:**
  - *Option A:* 1-indexed **Set A (Odd)** $= \{1, 3, 5, \dots, 2\lceil C/2 \rceil - 1\}$ ($\lceil C/2 \rceil$ columns) and **Set B (Even)** $= \{2, 4, 6, \dots, 2\lfloor C/2 \rfloor\}$ ($\lfloor C/2 \rfloor$ columns). Larger course in the hall gets Set A; second course gets Set B.
  - *Option B:* Leave the last odd column permanently unused ($\lfloor C/2 \rfloor$ columns each).
- **Provisional Selection:** **Option A (Set A = odd columns $\lceil C/2 \rceil$, Set B = even columns $\lfloor C/2 \rfloor$).**
- **Rationale:** Column `1` and Column `7` are on opposite walls of the room, never adjacent (`|c_i - c_j| >= 2` within Set A and within Set B). Option A maximises usable seats without violating adjacency.
- **Affected Modules & Tests:** `allocation/seat_assigner.py`; `TC-042`, `TC-043`.
- **How to Change Later:** Single function `partition_hall_columns(num_cols: int)` in `allocation/seat_assigner.py`.
- **Sample Output Resolvable?** **Yes** — visible whenever a hall has odd `columns`.

### AS-006 — Small-Course (`< 10` Students) Merging When No Compatible Partner Exists in Session
- **Parent Rule:** `BR-05`, `EC-02`
- **Ambiguity:** `BR-05` states *"A course with fewer than ten students must be merged into a hall containing another course from a different department."* What if a session contains no other course of the same exam duration from a different department? Also, how are `0`-enrolment courses handled?
- **Interpretations:**
  - *Option A (Hard Rule + Deterministic Repair):* Small-course merging (`1 <= enrolment < 10`) is a **hard constraint**. During scheduling (`ALG-06`), if a small course is tentatively placed in a session and no compatible partner joins that session by end-of-pass, deterministic repair (`ALG-06` Phase 2 / `ALG-10`) relocates the small course to the earliest hard-valid session containing an already-placed compatible partner (`same duration, different department`, with free Set B capacity). If zero compatible partners exist anywhere in the exam window, the small course is marked `UNSCHEDULED` (`NO_MERGE_PARTNER`). Courses with `0` enrolled students require `0` hall seats.
  - *Option B (Soft Fallback):* Seat the `< 10` course alone and log a soft violation.
- **Provisional Selection:** **Option A (Hard constraint with deterministic partner-aware scheduling/repair).**
- **Rationale:** Master Prompt Section 12 & 26 explicitly forbid relaxing hard constraints (*"The gap-rule fallback must never permit unrelated hard-constraint violations"* — `BR-02` is the **only** soft-fallback rule in Section 5).
- **Affected Modules & Tests:** `scheduling/scheduler.py`, `allocation/merge_policy.py`, `validation/validator.py`; `TC-034`, `TC-035`, `TC-037`, `TC-038`.
- **How to Change Later:** `SmallCourseMergePolicy` in `allocation/merge_policy.py`.
- **Sample Output Resolvable?** **Yes**, if sample dataset includes `< 10` student courses.

### AS-007 — Multiple Small Courses Competing for Halls
- **Parent Rule:** `BR-05`
- **Ambiguity:** May two small courses (`< 10` students each, e.g., 7 `CSE` students and 6 `MEC` students, both 3-hour) merge **with each other** in one hall, and in what order are multiple small courses paired?
- **Interpretations:**
  - *Option A:* Yes—two small courses of equal duration and **different departments** merged into the same hall satisfy *"merged into a hall containing another course from a different department"* for both courses simultaneously. Pairing order follows deterministic course order `(-enrolment, -credits, course_code)`, filling Set B of already-opened compatible 1-course halls (largest hall first) before opening a new hall for a compatible pair of small courses.
  - *Option B:* A small course may only merge with a large (`>= 10`) course.
- **Provisional Selection:** **Option A.**
- **Rationale:** Literally satisfies `BR-05` without inventing an unstated `>= 10` partner requirement, and prevents artificial infeasibility during supplementary/elective sessions consisting solely of small courses.
- **Affected Modules & Tests:** `allocation/merge_policy.py`, `allocation/hall_allocator.py`; `TC-039`, `TC-040`.
- **How to Change Later:** Predicate `can_pair_courses(c1, c2)` in `allocation/merge_policy.py`.
- **Sample Output Resolvable?** **Possibly**, if two `< 10` courses occur in the same session.

### AS-008 — Department Restrictions for Ordinary (`>= 10`) vs. Mandatory Small-Course (`< 10`) Merging
- **Parent Rule:** `BR-05`, `EC-04`
- **Ambiguity:** When two courses with `>= 10` students share a hall to conserve halls, must they also belong to **different departments**, or does the different-department mandate strictly apply only to `< 10` merges?
- **Interpretations:**
  - *Option A:* Mandatory different-department for `< 10` courses; **prefer** different-department when pairing `>= 10` courses, permitting same-department distinct courses (`c1.course_code != c2.course_code`) only if no different-department course needs Set B.
  - *Option B:* Require different departments for **all** 2-course halls regardless of enrolment size.
- **Provisional Selection:** **Option B as default preference with strict cross-department pairing (`c1.department != c2.department`) for all 2-course halls unless session capacity forces same-department `>= 10` sharing (`HallPairingPolicy`).**
  - *Refined Exact Rule:* Let us make this 100% deterministic: in `HallPairingPolicy`, `< 10` courses **strictly require** `c1.department != c2.department` (hard rule). For `>= 10` courses, two courses share a hall first if `c1.department != c2.department`, and fall back to `c1.department == c2.department` (`c1 != c2`) **only** when available halls would otherwise run out (`BR-05` explicitly scopes *"from a different department"* to the `< 10` clause while `EC-04` refers to *"either department represented in a merged examination hall"*).
- **Rationale:** Preserves exact fidelity to `BR-05` wording while maximising cross-department mixing and avoiding false hall-exhaustion failures when a single department schedules multiple large electives in one session.
- **Affected Modules & Tests:** `allocation/merge_policy.py`; `TC-036`, `TC-040`.
- **How to Change Later:** Single boolean `ALLOW_SAME_DEPT_LARGE_COURSE_PAIRING` in `HallPairingPolicy`.
- **Sample Output Resolvable?** **Yes** — inspect `hall_plan.csv` for any 2-course halls.

### AS-009 — Special-Needs Seating Priority vs. Strict Alphabetical Register-Number Order
- **Parent Rule:** `BR-06`
- **Ambiguity:** `BR-06` states both *"Students of a course are seated alphabetically by register number in alternate columns"* and *"Special-needs students must occupy row one of a ground-floor hall."* If a special-needs student has register number `2462199` (near the end of the alphabet), placing them in Row 1 places them ahead of `2462101`.
- **Interpretations:**
  - *Option A (Partitioned Alphabetical Seating):* Partition a course's enrolled students into `SN_students` (`special_needs == True`, sorted ascending by `register_number`) and `regular_students` (`special_needs == False`, sorted ascending by `register_number`). Seat `SN_students` first into `(row = 1, col in course_col_set)` of ground-floor hall(s); then seat `regular_students` in ascending `register_number` order across all remaining available seats of `course_col_set` in row-major order (remaining `row = 1` slots on ground floor if any, then `row = 2..R`, then upper-floor overflow halls if split).
  - *Option B:* Reserve Row 1 exclusively for special-needs students (leaving unused Row 1 slots empty) and start regular students in Row 2.
- **Provisional Selection:** **Option A (Partitioned Alphabetical Seating, using remaining Row 1 slots in the course's column set after all `SN_students` of that course are seated).**
- **Rationale:** Satisfies the hard physical accessibility requirement (`row == 1, floor == 0`) for every special-needs student, preserves deterministic alphabetical order within both subgroups, and avoids wasting Row 1 capacity when only 1 special-needs student sits in a hall with 5 alternate columns.
- **Affected Modules & Tests:** `allocation/accessibility.py`, `allocation/seat_assigner.py`, `validation/validator.py`; `TC-046`, `TC-047`, `TC-048`.
- **How to Change Later:** Isolated in `AccessibilitySeatingPolicy.assign_course_seats()`.
- **Sample Output Resolvable?** **Yes** — directly observable in `seat_assignments.csv` and `seat_maps.txt`.

### AS-010 — Insufficient Accessible Seats (Ground-Floor Row 1 Exhaustion)
- **Parent Rule:** `BR-06`
- **Ambiguity:** How should the engine behave if courses containing special-needs students compete with non-special-needs courses for ground-floor halls, or if total special-needs students in a session exceed total ground-floor Row 1 alternate-column seats?
- **Interpretations:**
  - *Option A:* Two-stage protection: (1) Within any session, allocate ground-floor halls (`floor == 0`, ordered by `(-capacity, hall_id)`) to courses with `special_needs_count > 0` **before** allocating remaining halls largest-first to non-special-needs courses; (2) During scheduling (`ALG-06` / `ALG-08`), treat aggregate ground-floor Row 1 alternate-column capacity as a **hard session feasibility check**. If even an empty session across the entire window lacks sufficient ground-floor Row 1 seats for a single course's special-needs cohort, mark that course `UNSCHEDULED` (`INSUFFICIENT_ACCESSIBLE_SEATS`) in `violations.json`.
  - *Option B:* Seat overflow special-needs students in Row 2 of ground floor.
- **Provisional Selection:** **Option A (Ground-floor reservation + hard accessibility feasibility).**
- **Rationale:** `BR-06` (*"must occupy row one of a ground-floor hall"*) is a hard accessibility guarantee; Option B silently breaks a hard constraint.
- **Affected Modules & Tests:** `allocation/accessibility.py`, `allocation/hall_allocator.py`, `scheduling/scheduler.py`; `TC-049`, `TC-050`.
- **How to Change Later:** `AccessibilitySeatingPolicy` in `allocation/accessibility.py`.
- **Sample Output Resolvable?** **Yes**, if sample dataset has ground-floor and upper-floor halls.

---

## 3. Cohorts, Backlogs & Temporal Scheduling Assumptions (`AS-011` – `AS-017`)

### AS-011 — Programme-Semester Membership for Cross-Programme Courses
- **Parent Rule:** `BR-02`
- **Ambiguity:** `BR-02` applies to *"Students in the same programme-semester"*, while `FR-01` registers `department` and `semester` on `Course` and `programme` and `semester` on `Student`. Common core courses (e.g., Engineering Mathematics) may enrol regular students from both `BTech-AIML Sem 2` and `BTech-CSE Sem 2`.
- **Interpretations:**
  - *Option A (Enrolled Regular Cohort Union):* Define a core course $c$'s active cohorts $\Gamma(c)$ as the set of `(student.programme, student.semester)` pairs across all **regular** (`is_backlog == False`) students enrolled in $c$ (falling back to `{(c.department, c.semester)}` if `c` has 0 regular enrolments). Two core courses $c_1, c_2$ (`credits >= 4`) require $|\text{date}(c_1) - \text{date}(c_2)| \ge 2$ iff $\Gamma(c_1) \cap \Gamma(c_2) \ne \emptyset$.
  - *Option B:* Match solely on `(course.department, course.semester)`.
- **Provisional Selection:** **Option A (Enrolled Regular Cohort Union).**
- **Rationale:** `BR-02` explicitly protects **students** in the same programme-semester. Matching only `course.department` would miss a `MAT`-department core course taken by `AIML` students! Excluding `is_backlog == True` repeaters from $\Gamma(c)$ prevents a single senior student repeating a Sem-2 core paper from coupling the entire Sem-6 cohort with Sem-2's gap schedule (the senior repeater's personal load is already governed by `BR-01`).
- **Affected Modules & Tests:** `scheduling/gap_validator.py`, `validation/validator.py`; `TC-014`, `TC-015`, `TC-018`.
- **How to Change Later:** Single helper `extract_course_cohorts(course, enrolments)` in `scheduling/gap_validator.py`.
- **Sample Output Resolvable?** **Yes** — verifiable from `timetable.csv` and `violations.json` on shared core courses.

### AS-012 — Distinction Between Backlog Enrolments and Supplementary Courses
- **Parent Rule:** `FR-01`, `BR-01`, `BR-12`
- **Ambiguity:** `FR-01` mentions student `backlog courses`, `BR-01` mentions `a backlog student`, and `BR-12` mentions `Supplementary backlog courses`. Are all backlog courses supplementary courses, or can a student take a regular course as a backlog alongside dedicated supplementary courses?
- **Interpretations:**
  - *Option A (Dual Representation):* `Course.is_supplementary: bool` marks dedicated supplementary backlog courses governed by `BR-12` (final 3 days). Independently, `Enrolment.is_backlog: bool` (derived from `Student.backlog_courses` or `Course.is_supplementary == True`) marks that a specific student is sitting that paper as a backlog/arrear, qualifying for `BR-01` same-day consent if `student.backlog_consent == True`.
  - *Option B:* Every course referenced in any student's `backlog_courses` automatically becomes a `BR-12` supplementary course.
- **Provisional Selection:** **Option A.**
- **Rationale:** In Indian universities (including CHRIST University), arrear students may either sit a dedicated supplementary examination (`BR-12`) OR sit with a junior batch's regular examination; Option B would illegally drag a regular junior course of 180 students into the final 3 days just because 1 senior had it as a backlog! Note: if a course has **only** backlog enrolments (100% backlog students), input normalisation (`ALG-01`) treats `is_supplementary = True` unless explicitly marked false.
- **Affected Modules & Tests:** `domain/entities.py`, `io/parsers.py`, `scheduling/supplementary.py`; `TC-011`, `TC-085`, `TC-086`.
- **How to Change Later:** Normalisation rule in `io/parsers.py`.
- **Sample Output Resolvable?** **Yes** — immediately clear from `courses.csv` / `students.csv` schema and `timetable.csv` dates.

### AS-013 — Scope of `BACKLOG_CONSENT` Same-Day Exception
- **Parent Rule:** `BR-01`
- **Ambiguity:** If a student has `backlog_consent == True` because they registered for a Sem-4 arrear paper, may the scheduler place **two regular Sem-6 papers** for that student on the same day (`FN` + `AN`)?
- **Interpretations:**
  - *Option A:* Same-day `FN` + `AN` pairing for a consenting student is permitted **only when at least one of the two examinations on that date is a backlog enrolment (`enrolment.is_backlog == True`)** for that student.
  - *Option B:* `backlog_consent == True` permits any two exams (`FN` + `AN`) on the same day regardless of whether either exam is a backlog.
- **Provisional Selection:** **Option A (At least one of the two same-day exams must be a backlog enrolment).**
- **Rationale:** `BACKLOG_CONSENT` exists specifically because arrear exams cross cohort boundaries; a student never consents to taking two regular current-semester exams on the same day.
- **Affected Modules & Tests:** `scheduling/conflict_graph.py`, `validation/validator.py`; `TC-011`, `TC-012`, `TC-013`.
- **How to Change Later:** Single predicate `StudentConflictPolicy.allows_same_day(student, e1, e2)`.
- **Sample Output Resolvable?** **Yes** — check consenting students' schedules in `timetable.csv`.

### AS-014 — Three Examinations Across Two Consecutive Days for a Consenting Backlog Student
- **Parent Rule:** `BR-01`, `BR-02`, `BR-09`, `EC-06`
- **Ambiguity:** `EC-06` asks how the system handles postponement resulting in a backlog student having **three examinations across two consecutive days** (e.g., Day $d$ `FN` + `AN`, Day $d+1$ `FN`). Is there a hidden sliding-window cap of 2 exams per 48 hours, or is `BR-01` strictly per calendar day?
- **Interpretations:**
  - *Option A:* `BR-01` is strictly evaluated **per calendar date**: Day $d$ has 2 exams in `{FN, AN}` with `backlog_consent == True` and $\ge 1$ backlog enrolment (valid); Day $d+1$ has 1 exam (valid). No hard `BR-01` violation occurs, while `BR-02` core-gap is still checked if two of those papers are regular cohort core exams on consecutive dates.
  - *Option B:* Invent an unwritten rule banning 3 exams in 2 consecutive days.
- **Provisional Selection:** **Option A (Strictly follow `BR-01` daily boundaries + `BR-02` core-gap rules; do not invent unstated rules).**
- **Rationale:** Master Prompt Section 5 warns *"Treat the following rules as the authoritative project requirements. Do not silently modify them."* `EC-06` specifically tests that our validator distinguishes valid 2+1 consenting backlog schedules from illegal 2-in-one-session or non-consenting 2-in-one-day clashes, and properly evaluates `BR-02` core gaps!
- **Affected Modules & Tests:** `scheduling/conflict_graph.py`, `changes/postponement.py`, `validation/validator.py`; `TC-075`, `TC-076`.
- **How to Change Later:** `StudentConflictPolicy` in `scheduling/conflict_graph.py`.
- **Sample Output Resolvable?** **Yes**, if one of the 8 sample change commands triggers `EC-06`.

### AS-015 — Final Three Calendar Days vs. Final Three Active Examination Days (`BR-12`)
- **Parent Rule:** `BR-12`, `EC-08`
- **Ambiguity:** Does *"final three days of the examination window"* mean the last 3 calendar dates `[end_date - 2, end_date]` (even if one is a Sunday/holiday), or the **last 3 active examination dates** (dates having at least one open session)?
- **Interpretations:**
  - *Option A:* Final 3 active examination dates in `ExamWindow` (`active_exam_dates[-3:]`).
  - *Option B:* Literal calendar dates `[end_date - 2 days, end_date]`.
- **Provisional Selection:** **Option A (Final 3 active examination dates).**
- **Rationale:** In a 12-day window with 2 holidays, if a holiday falls on Day 11, Option B shrinks supplementary capacity by 33% for an administrative calendar artifact. Under `EC-08`, if the final active day has **only `FN`** open, that day still counts as one of the final 3 active examination days (usable by `> 50` supplementary courses in `FN`, while `<= 50` supplementary courses must use `AN` on the preceding two final active days).
- **Affected Modules & Tests:** `scheduling/supplementary.py`, `validation/validator.py`; `TC-087`, `TC-088`, `TC-089`, `TC-090`.
- **How to Change Later:** `SupplementaryWindowPolicy.get_supplementary_dates(exam_window)`.
- **Sample Output Resolvable?** **Yes** — inspect supplementary exam dates relative to holidays in `exam_window.json` and `timetable.csv`.

### AS-016 — Partial-Day Holidays and Unavailable Sessions
- **Parent Rule:** `FR-02`, `BR-02`, `EC-08`
- **Ambiguity:** `EC-08` states *"The final day of the examination window having only an FN session available."* Hence session availability is finer-grained than full-day holidays.
- **Interpretations:**
  - *Option A:* `ExamWindow` supports both `holidays: list[date]` (excludes both `FN` and `AN`, counts as calendar gap day for `BR-02`) and `unavailable_sessions: list[tuple[date, SessionSlot]]` (closes only the specified `FN` or `AN` slot, e.g., `(end_date, AN)`).
  - *Option B:* Explicit enumeration of active sessions in `exam_window.json`.
- **Provisional Selection:** **Support both declaratively in `ExamWindow` (`ALG-02` normalises either representation into an ordered tuple of active `ExamSession` objects).**
- **Rationale:** Directly supports `EC-08` and makes adapting to the official `exam_window` file trivial.
- **Affected Modules & Tests:** `domain/entities.py`, `io/parsers.py`, `scheduling/session_generator.py`; `TC-006`, `TC-088`.
- **How to Change Later:** Handled solely inside `io/parsers.py` -> `ALG-02`.
- **Sample Output Resolvable?** **Yes** — directly visible in official `exam_window` input file.

### AS-017 — Actual Start and End Times for Two-Hour vs. Three-Hour Examinations
- **Parent Rule:** `FR-01`, `FR-02`, `BR-06`
- **Ambiguity:** Session envelopes are `FN: 09:30–12:30` and `AN: 14:00–17:00` (3 hours). When a 2-hour exam runs in `FN` or `AN`, when does it start and end, and how is the +20 minute special-needs extension calculated?
- **Interpretations:**
  - *Option A:* All exams start promptly at session start (`09:30` for `FN`, `14:00` for `AN`). Standard end = `start + duration_hours`:
    - `FN` 2h: `09:30–11:30` (`11:50` with SN +20m)
    - `FN` 3h: `09:30–12:30` (`12:50` with SN +20m)
    - `AN` 2h: `14:00–16:00` (`16:20` with SN +20m)
    - `AN` 3h: `14:00–17:00` (`17:20` with SN +20m, matching `EC-05`!)
  - *Option B:* Extend session envelope `12:30`/`17:00` by 20m even for 2-hour exams.
- **Provisional Selection:** **Option A (`effective_end = session_start + course_duration + (20m if has_special_needs else 0m)`).**
- **Rationale:** Matches `EC-05` (`14:00 + 3h + 20m = 17:20`) and explains why `BR-04` forbids mixing 2-hour and 3-hour exams in the same hall (different paper collection times: `11:30` vs `12:30`).
- **Affected Modules & Tests:** `allocation/accessibility.py`, `invigilation/invigilator_engine.py`; `TC-051`, `TC-062`.
- **How to Change Later:** Helper `compute_hall_time_window(session_slot, duration_hours, has_special_needs)`.
- **Sample Output Resolvable?** **Yes** — inspect end times in `hall_plan.csv` / `invigilation_roster.csv`.

---

## 4. Invigilation & Workload Assumptions (`AS-018` – `AS-022`)

### AS-018 — Extra-Time Invigilator Availability and External Duty Overlaps (`EC-05`)
- **Parent Rule:** `BR-06`, `BR-08`, `EC-05`
- **Ambiguity:** `EC-05` specifies *"A special-needs student in a three-hour examination extending a hall's duty to 17:20 when the invigilator has another duty at 17:30."* Two subtleties arise: (1) `FR-01` mentions `unavailable dates`, so external timed commitments on partially available dates must also be representable; (2) Does `17:20` conflict with `17:30` (if a post-exam script-handover buffer > 10 min is assumed), or is `17:20 <= 17:30` non-overlapping?
- **Interpretations:**
  - *Option A (Zero-Buffer Half-Open Interval `[start, end)`):* An invigilator may have timed busy intervals `(date, start_time, end_time)` in addition to full-day `unavailable_dates`. Duty `[14:00, 17:20)` conflicts with busy `[t_1, t_2)` iff `max(14:00, t_1) < min(17:20, t_2)`. Thus a `17:30` duty does **not** conflict (`17:20 <= 17:30` -> **eligible**), whereas a `17:15` or `17:00` duty **does** conflict (`17:15 < 17:20` -> **ineligible**, even though `17:15` would NOT have conflicted with a standard `17:00` hall!).
  - *Option B (Mandatory 15-Minute Handover Buffer):* Require `effective_end + 15m <= next_duty_start`, making `17:20 + 15m = 17:35 > 17:30` **ineligible**.
- **Provisional Selection:** **Option A (`MIN_TRANSITION_BUFFER_MINUTES = 0`, strict clock non-overlap), with `MIN_TRANSITION_BUFFER_MINUTES` isolated as a named policy constant.**
- **Rationale:** Nowhere in `BR-01`–`BR-12` is a 15-minute post-exam buffer stated; inventing a 15-minute constant risks failing automated grading if `EC-05` tests exact boundary survival (`17:20 <= 17:30`), while isolating `MIN_TRANSITION_BUFFER_MINUTES` lets us switch to `15` (Option B) in 1 line if mentor clarification or sample output treats `EC-05` as a buffer-conflict rejection. Our test catalogue tests **both** `17:15` (overlap exclusion) and `17:30` (boundary behaviour) (`TC-062`–`TC-064`).
- **Affected Modules & Tests:** `invigilation/eligibility.py`, `io/parsers.py`; `TC-062`, `TC-063`, `TC-064`.
- **How to Change Later:** Single constant `MIN_TRANSITION_BUFFER_MINUTES` in `invigilation/eligibility.py`.
- **Sample Output Resolvable?** **Yes** — check `invigilation_roster.csv` on official sample dataset.

### AS-019 — Chief Invigilator Eligibility and Department Conflicts
- **Parent Rule:** `BR-07`, `BR-08`
- **Ambiguity:** `BR-07` states *"Each active building requires one additional chief invigilator per session. An invigilator may not invigilate a hall containing a course from their own department."* Does the department restriction apply to Building Chiefs across **all** courses in that building, or only to Hall Invigilators?
- **Interpretations:**
  - *Option A (Hall-Scoped Department Restriction):* Hall invigilators cannot belong to any department seated in their assigned hall (`EC-04`). Building Chiefs supervise corridor/building logistics rather than sitting inside a course hall, so they are **not** disqualified by courses inside the building's halls (though they must satisfy availability, intra-session uniqueness, daily `<= 2`, weekly `<= max_weekly`, and cover the latest hall `effective_end_time` in that building).
  - *Option B (Building-Wide Department Restriction):* Exclude any invigilator whose department has a course anywhere in that building during that session.
- **Provisional Selection:** **Option A (Department rule strictly hall-scoped as written in `BR-07`).**
- **Rationale:** A large main academic block with 10 halls can easily host courses from every department in the university during peak sessions; Option B would routinely cause false `BUILDING_CHIEF_UNSTAFFED` shortages despite plenty of senior faculty being available.
- **Affected Modules & Tests:** `invigilation/eligibility.py`, `invigilation/invigilator_engine.py`; `TC-058`, `TC-059`.
- **How to Change Later:** Boolean policy flag `CHIEF_EXCLUDES_BUILDING_DEPARTMENTS` in `invigilation/eligibility.py`.
- **Sample Output Resolvable?** **Yes** — inspect building chief departments in `invigilation_roster.csv`.

### AS-020 — Chief Invigilator Duties Counting Towards Daily, Weekly & Cumulative Workload
- **Parent Rule:** `BR-07`, `BR-08`
- **Ambiguity:** Does serving as a Building Chief count as 1 session toward the 2-sessions/day limit, the `4–8` weekly limit, and `BR-08`'s *"fewest sessions assigned so far"*, and are halls staffed before building chiefs within a session?
- **Interpretations:** *Option A:* Yes to counting toward daily, weekly, and cumulative counts; within each session, staff occupied halls first (ordered by `hall_id` ascending) and active buildings second (ordered by `building_code` ascending). *Option B:* Track chief duties separately.
- **Provisional Selection:** **Option A.**
- **Rationale:** A Building Chief physically works the entire 3-hour session; excluding chief duties would allow 4 duties/day (`FN` hall + `FN` chief — impossible simultaneously — or exceeding weekly caps). Staffing halls first preserves department-constrained invigilators for halls before drawing from the broader pool for building chiefs.
- **Affected Modules & Tests:** `invigilation/invigilator_engine.py`, `validation/validator.py`; `TC-058`, `TC-060`.
- **How to Change Later:** `InvigilationOrderPolicy` in `invigilation/invigilator_engine.py`.
- **Sample Output Resolvable?** **Yes** — verifiable directly from `invigilation_roster.csv`.

### AS-021 — Weekly Workload Boundaries
- **Parent Rule:** `BR-07`
- **Ambiguity:** How is a "week" bounded when checking `max_weekly_sessions` (`4–8`): ISO Monday–Sunday calendar weeks, Sunday–Saturday weeks, or rolling 7-day windows (`[d-6, d]`)?
- **Interpretations:** *Option A:* Monday–Sunday ISO calendar week (`date.isocalendar()[:2]`); *Option B:* Rolling 7-day window; *Option C:* Exam-window 7-day chunks starting at `start_date`.
- **Provisional Selection:** **Option A (Monday–Sunday ISO calendar week).**
- **Rationale:** Standard academic timetable convention at Indian universities (Monday–Saturday teaching/exam week) and explicitly recommended in Master Prompt Section 9.
- **Affected Modules & Tests:** `invigilation/workload.py`, `validation/validator.py`; `TC-061`.
- **How to Change Later:** Single function `week_bucket(exam_date: date, window_start: date) -> tuple[int, int]` in `invigilation/workload.py`.
- **Sample Output Resolvable?** **Yes**, across a 12-day multi-week sample window.

### AS-022 — Meaning of "Fewest Sessions Assigned So Far"
- **Parent Rule:** `BR-08`
- **Ambiguity:** During initial synthesis, sessions are staffed chronologically, so "so far" equals total sessions assigned up to that point. During an incremental change (`BR-09` postponement or `BR-10` hall closure on Day 3 when Days 4–12 are already scheduled), does "assigned so far" count **all currently active assignments across the entire `ScheduleState`** (excluding stripped affected sessions), or only dates `<= target_date`?
- **Interpretations:**
  - *Option A:* Total active session assignments held by the invigilator in the candidate `ScheduleState` at the exact instant of selection (chronological cumulative during initial run; full-window active count minus cleared affected sessions during incremental re-staffing).
  - *Option B:* Prefix-only count (`date <= session.date`).
- **Provisional Selection:** **Option A.**
- **Rationale:** During initial chronological staffing, Option A and Option B are **100% identical**! During incremental updates, counting all active fixed duties across the schedule ensures workload stays balanced and never pushes an invigilator above their weekly cap (`BR-07`) on later fixed days.
- **Affected Modules & Tests:** `invigilation/workload.py`, `changes/`; `TC-065`, `TC-077`.
- **How to Change Later:** `WorkloadTracker.assigned_count(invigilator_id)` in `invigilation/workload.py`.
- **Sample Output Resolvable?** **Yes** — check invigilator assignments after change commands.

---

## 5. Deterministic Tie-Breaking & Ordering Assumptions (`AS-023` – `AS-024`, `AS-033`)

### AS-023 — Deterministic Hall Ordering When Capacities Are Equal
- **Parent Rule:** `BR-05` (*"Fill the largest hall first."*)
- **Ambiguity:** Tie-breaker when two halls have identical `capacity` (e.g., `H01` and `H02` both hold `60` seats).
- **Interpretations:** *Option A:* `(-hall.capacity, hall.hall_id)` ascending lexicographical `hall_id`; *Option B:* `(-hall.capacity, hall.building_code, hall.floor, hall.hall_id)`.
- **Provisional Selection:** **Option A (`(-hall.capacity, hall.hall_id)`), with ground-floor (`floor == 0`) subset selected first when seating unresolved special-needs students (`AS-010`).**
- **Rationale:** Matches Master Prompt Section 9 recommended default (*"Use hall identifiers as deterministic capacity tie-breakers"*).
- **Affected Modules & Tests:** `allocation/hall_allocator.py`; `TC-032`.
- **How to Change Later:** `hall_sort_key(hall: Hall)` in `allocation/policies.py`.
- **Sample Output Resolvable?** **Yes** — immediately visible in `hall_plan.csv`.

### AS-024 — Deterministic Ordering of Courses and Students Within a Session and Hall
- **Parent Rule:** `BR-05`, `BR-06`
- **Ambiguity:** Within a single session containing multiple courses, in what order do courses claim halls and column sets (Set A odd vs Set B even)?
- **Interpretations:**
  - *Option A:* Within a session:
    1. Courses containing `special_needs` students (`special_needs_count > 0`) claim ground-floor halls first in `(-enrolment_count, -credits, course_code)` order (`AS-010`).
    2. Remaining regular courses (`enrolment_count >= 10`) are allocated in `(-enrolment_count, -credits, course_code)` order, filling largest available halls first (`AS-023`); if a regular course splits across multiple halls, each chunk fills Set A (or compatible open Set B of equal duration) before opening the next hall.
    3. Mandatory small courses (`1 <= enrolment_count < 10`) are paired in `(-enrolment_count, -credits, course_code)` order into compatible open Set B slots (largest hall first), or paired together in a new hall (`AS-007`).
    4. Inside any 2-course hall, **Slot A (Odd columns `1, 3, 5...`)** belongs to the first/larger course `(enrolment_in_hall, -course_order_rank)` and **Slot B (Even columns `2, 4, 6...`)** belongs to the second course.
- **Provisional Selection:** **Option A.**
- **Rationale:** Preserves `BR-03` priority order throughout spatial packing, guarantees Set A ($\lceil C/2 \rceil \ge \lfloor C/2 \rfloor$ columns) goes to the larger hall slice, and guarantees accessibility (`BR-06`).
- **Affected Modules & Tests:** `allocation/hall_allocator.py`, `allocation/seat_assigner.py`; `TC-033`, `TC-042`, `TC-048`.
- **How to Change Later:** `SessionAllocationOrderPolicy` in `allocation/policies.py`.
- **Sample Output Resolvable?** **Yes** — inspect `hall_plan.csv` and `seat_maps.txt`.

---

## 6. Incremental Change, Repair & Output Assumptions (`AS-025` – `AS-033`)

### AS-025 — Meaning of "Next Free Session" During Hall Unavailability (`BR-10`)
- **Parent Rule:** `BR-10`
- **Ambiguity:** When hall closure leaves insufficient capacity in `S_orig`, *"move the session's smallest course to the next free session and flag the change."* How is "smallest course" tied-broken, what if multiple small courses must move, and does "next free session" mean strictly chronological later (`> S_orig`) or earliest from window start?
- **Interpretations:**
  - *Option A:*
    - **Smallest Course Key:** `(len(c.enrolments), c.credits, c.course_code)` ascending (exact inverse of `BR-03`'s size/credit priority, with ascending `course_code` deterministic tie-breaker; note: if displacing the partner of a `< 10` course would leave the `< 10` course unmerged in `S_orig`, the `< 10` course already has smaller enrolment so it is naturally selected first!).
    - **Iterative Sufficiency:** If moving 1 smallest course still leaves `S_orig` above 90% aggregate cap or unpackable in remaining halls, repeat moving the next smallest course until `S_orig` is hard-feasible (or fail transactionally if `S_orig` has 0 halls left and a course cannot move).
    - **Next Free Session:** Earliest session **strictly after `S_orig`** (`session_index > S_orig.session_index`) satisfying all hard rules (and `BR-02` gap with soft fallback per `AS-027`). Flag `COURSE_DISPLACED_BY_HALL_CLOSURE` in `change_results.json` and `violations.json`.
  - *Option B:* Search from `session_index = 0` (including earlier dates in the past).
- **Provisional Selection:** **Option A (Strictly later session `session_index > S_orig.session_index`).**
- **Rationale:** Operational hall closures happen mid-window or forward-looking; moving an exam backward to an earlier date gives students negative notice and violates operational common sense ("next free session").
- **Affected Modules & Tests:** `changes/hall_unavailability.py`; `TC-078`–`TC-082`.
- **How to Change Later:** `DisplacementSearchPolicy` in `changes/hall_unavailability.py`.
- **Sample Output Resolvable?** **Yes** — directly verifiable from the 4 sample change command outputs.

### AS-026 — Meaning of "Earliest Later Session" During Course Postponement (`BR-09`)
- **Parent Rule:** `BR-09`
- **Ambiguity:** Does "earliest later session" allow moving from `Date D FN` to `Date D AN` (same calendar date, later session), or must it be `Date >= D + 1`?
- **Interpretations:**
  - *Option A:* Any active `ExamSession` with `session_index > current_session.session_index` (including `Date D AN` if currently in `Date D FN`, provided `BR-01`, `BR-04`, `BR-05`, `BR-06`, `BR-12` hold).
  - *Option B:* Strictly `session.date > current_session.date`.
- **Provisional Selection:** **Option A (`session_index > current_session.session_index`, plus optional `min_target_date` parameter in `POSTPONE_COURSE` command payload if specified).**
- **Rationale:** Matches the literal domain noun **"session"** (*"earliest later session"*, not *"earliest later date"*). Supporting an optional `min_date` field in the provisional command contract (`10_INPUT_OUTPUT_CONTRACTS.md`) cleanly handles date-level postponements if present in official commands.
- **Affected Modules & Tests:** `changes/postponement.py`; `TC-071`, `TC-072`.
- **How to Change Later:** Predicate `is_eligible_postponement_target(orig, cand, cmd)` in `changes/postponement.py`.
- **Sample Output Resolvable?** **Yes** — verifiable from sample postponement output.

### AS-027 — Core-Gap Rule (`BR-02`) Treatment During Incremental Changes (`BR-09`, `BR-10`)
- **Parent Rule:** `BR-02`, `BR-03`, `BR-09`, `BR-10`
- **Ambiguity:** `BR-09` says *"Move the postponed course to the earliest later session satisfying all hard rules."* Should incremental moves (`BR-09` postponement and `BR-10` displacement) also respect `BR-02` core-course gap first (with `SOFT_VIOLATION` fallback only if no gap-valid later session exists), or ignore `BR-02` and immediately pick the first hard-valid slot?
- **Interpretations:**
  - *Option A (Gap-Respecting with Soft Fallback, consistent with `BR-03`):* Pass 1 scans strictly later sessions for `hard_valid AND gap_valid`; if none exists, Pass 2 selects earliest strictly later `hard_valid` session and records `SOFT_VIOLATION` (`CORE_GAP_SOFT_VIOLATION`). Also remove any stale `CORE_GAP_SOFT_VIOLATION` previously caused by `S_orig` that is now resolved!
  - *Option B (Hard-Only Scan):* Pick earliest strictly later `hard_valid` session immediately and log `SOFT_VIOLATION` if `BR-02` happens to be broken.
- **Provisional Selection:** **Option A.**
- **Rationale:** Keeps `BR-02` active across the entire lifecycle and ensures `IndependentScheduleValidator` never encounters an avoidable core-gap violation when a clean gap-compliant later slot was open.
- **Affected Modules & Tests:** `changes/postponement.py`, `changes/hall_unavailability.py`; `TC-073`, `TC-074`.
- **How to Change Later:** Single policy enum `IncrementalGapMode.PREFER_GAP_WITH_FALLBACK | HARD_ONLY` in `changes/policies.py`.
- **Sample Output Resolvable?** **Yes** — directly verifiable if a core course is postponed in sample commands.

### AS-028 — Late Registration Hall Selection & Capacity Exhaustion (`BR-11`)
- **Parent Rule:** `BR-11`
- **Ambiguity:** `BR-11` says *"allocate the student to the eligible hall with the most free seats."* Which halls are "eligible" for course $c$ in session $\tau$, how are ties broken, how does alphabetical seating (`BR-06`) interact with unaffected seats, and what happens if no eligible seat or 90% session cap remains?
- **Interpretations:**
  - *Option A:*
    1. Check `BR-01` clashes across all enrolled courses (existing + new); if any clash occurs, reject with `REJECTED_CLASH` and the 2 conflicting `course_code`s (sorted ascending for determinism).
    2. Check `BR-04` 90% session aggregate cap (`total_students_in_session + 1 <= cap_90`); if exceeded, reject with `REJECTED_SESSION_CAPACITY`.
    3. Candidate Hall Priority:
       - **Tier 1:** Halls in $\tau$ **already hosting course $c$** that have $\ge 1$ free legal seat in $c$'s column set (and `floor == 0` with free Row 1 slot if student has `special_needs`), sorted by `(-free_legal_seats_for_c, hall_id)`.
       - **Tier 2 (Overflow):** If all existing halls for $c$ are full, search compatible halls in $\tau$ (`1-course` hall of same duration and compatible department with free Set B, or unoccupied hall if $|E(c)|+1 \ge 10$; requiring `floor == 0` if `special_needs`), sorted by `(-free_legal_seats, hall_id)`.
    4. Within the single selected hall, re-run `ALG-11`/`ALG-12` **only for course $c$'s column set in that hall** so `BR-06` alphabetical + Row 1 invariants hold strictly, leaving all other halls and the partner course's column set in that hall completely untouched!
    5. If no Tier 1 or Tier 2 hall can accommodate the student, reject atomically with `REJECTED_HALL_CAPACITY` (or `REJECTED_ACCESSIBILITY_CAPACITY`).
- **Provisional Selection:** **Option A.**
- **Rationale:** Satisfies `BR-11` ("eligible hall with the most free seats"), preserves `BR-04`/`BR-05`/`BR-06` hard invariants verified by `IndependentScheduleValidator`, and restricts seat mutation to the single target course-column-set in the single chosen hall. (Note: an append-only seat mode `APPEND_LAST_SEAT` is also isolated in `LateSeatPolicy` in case official outputs append the late student at the end of the column set without shifting register numbers in that hall.)
- **Affected Modules & Tests:** `changes/late_registration.py`; `TC-083`, `TC-084`, `TC-091`–`TC-095`.
- **How to Change Later:** `LateRegistrationPolicy` (`RE_SORT_COURSE_IN_HALL` vs `APPEND_FIRST_FREE_SEAT`) in `changes/late_registration.py`.
- **Sample Output Resolvable?** **Yes** — immediately visible in sample late-registration expected outputs.

### AS-029 — Invigilator Updates Upon Late Registration (`BR-07`, `BR-11`)
- **Parent Rule:** `BR-07`, `BR-08`, `BR-11`
- **Ambiguity:** If adding 1 late registrant pushes a hall from `30` to `31` students ($\lceil 31/30 \rceil = 2$ invigilators), opens a new overflow hall (requiring 1 hall invigilator + possibly 1 building chief), or adds the first `special_needs` student to a hall (`+20m` extension), how is invigilation updated?
- **Interpretations:**
  - *Option A (Minimal Delta Staffing):* Keep all existing valid invigilators in that session fixed; assign **only** the newly required additional invigilator slot(s) via `BR-08` (or mark the extra slot `UNSTAFFED` if pool exhausted). If `+20m` extension is newly triggered on that hall and causes an external-duty overlap (`EC-05`) for that hall's existing invigilator, replace only that conflicting invigilator from the eligible pool.
  - *Option B:* Regenerate the entire session's invigilation roster from scratch.
- **Provisional Selection:** **Option A (Minimal Delta Staffing).**
- **Rationale:** Preserves unaffected assignments inside the same session while maintaining 100% `BR-07`/`BR-08` compliance.
- **Affected Modules & Tests:** `changes/late_registration.py`, `invigilation/invigilator_engine.py`; `TC-094`, `TC-095`.
- **How to Change Later:** `update_hall_invigilation_delta()` in `invigilation/invigilator_engine.py`.
- **Sample Output Resolvable?** **Yes**, if sample late registration crosses a 30-student boundary.

### AS-030 — Multi-Course Late Registration Atomicity
- **Parent Rule:** `BR-11`, `FR-05`
- **Ambiguity:** A late registrant usually registers for an entire semester basket (e.g., 5–6 courses at once). If 4 courses succeed and the 5th clashes (`REJECTED_CLASH`) or lacks hall seats, should the first 4 be kept or rolled back?
- **Interpretations:** *Option A:* All-or-nothing transactional atomicity per `ChangeCommand`; *Option B:* Partial per-course acceptance.
- **Provisional Selection:** **Option A (Atomic per `ChangeCommand`).**
- **Rationale:** `BR-11` says *"If adding the student causes an examination clash, reject the registration with REJECTED_CLASH"* — singular ("the registration"). Partial registration would leave a student half-enrolled for a semester and violate transactional state safety.
- **Affected Modules & Tests:** `changes/late_registration.py`, `changes/state_manager.py`; `TC-093`, `TC-096`.
- **How to Change Later:** Command granularity controlled by input `commands.json` (1 command = 1 atomic unit).
- **Sample Output Resolvable?** **Yes** — check `change_results.json` / expected outputs on rejected late registration.

### AS-031 — Failure Behaviour When Postponement or Hall-Closure Recovery Is Impossible
- **Parent Rule:** `BR-09`, `BR-10`
- **Ambiguity:** What if a course on the final session of the window is postponed (`POSTPONE_COURSE`), or no later session satisfies hard rules during `POSTPONE_COURSE` or `MARK_HALL_UNAVAILABLE`?
- **Interpretations:**
  - *Option A (Transactional Rejection + Clean Rollback):* Never violate hard constraints. Reject the command (`REJECTED_NO_FEASIBLE_SESSION` or `REJECTED_HALL_CLOSURE_INFEASIBLE`), roll back `ScheduleState` completely to the pre-command valid snapshot, record detailed diagnostic metadata in `change_results.json`, and append an audit entry (or keep `violations.json` reflecting the active committed schedule while `change_results.json` holds rejected-command diagnostics — see `10_INPUT_OUTPUT_CONTRACTS.md`: we include a dedicated `rejected_changes` section in `violations.json` as well so auditors see it in one place!).
  - *Option B:* Leave courses unscheduled mid-stream and mutate half the state.
- **Provisional Selection:** **Option A (Transactional Rollback + Explicit Rejection Reporting).**
- **Rationale:** Matches Master Prompt Section 9 (*"Reject impossible changes without corrupting the previous valid schedule. Report infeasibility rather than silently violate hard rules."*)
- **Affected Modules & Tests:** `changes/state_manager.py`, `changes/postponement.py`, `changes/hall_unavailability.py`; `TC-077`, `TC-082`, `TC-097`.
- **How to Change Later:** `TransactionPolicy` in `changes/state_manager.py`.
- **Sample Output Resolvable?** **Yes**, if any sample command is infeasible.

### AS-032 — Deterministic Repair When Initial Greedy Placement Encounters Coupled Spatial Constraints
- **Parent Rule:** `BR-03`, `BR-05`, `BR-06`, `EC-07`
- **Ambiguity:** `BR-03` prescribes greedy course-by-course placement. Two subtleties can arise:
  1. Aggregate 90% seats (`BR-04`) is satisfied in session $\tau$, yet physical hall packing (`BR-04` 2h/3h separation, `BR-05` alternate columns, `BR-06` ground-floor Row 1) cannot fit the added course into actual halls!
  2. A small course (`< 10` students, placed near the end of `BR-03` order) needs a compatible different-department partner in the same session (`AS-006`), OR two small courses arrive sequentially where the first tentatively enters a session waiting for a second small course.
- **Interpretations:**
  - *Option A (Exact Trial Packing + Bounded Deterministic Small-Course Repair):*
    - During `ALG-06`, candidate session $\tau$ is accepted for course $c$ (`enrolment >= 10`) **only if** exact trial hall & seat packing (`ALG-08`–`ALG-12`) succeeds on $\tau \cup \{c\}$.
    - For small courses (`1 <= enrolment < 10`), `ALG-06` first checks sessions that **already contain** a compatible merge partner (`same duration, different department` with open Set B capacity); if none exists yet, it checks sessions where **another unscheduled small course** of equal duration and different department can co-schedule into the same session cleanly. Any course for which no hard-valid session exists across the entire window is marked `UNSCHEDULED` in `violations.json` (never silently breaking hard rules, and never reordering already-placed larger courses in violation of `BR-03`).
- **Provisional Selection:** **Option A.**
- **Rationale:** Strictly obeys `BR-03` (*"Do not silently replace this heuristic with an optimisation algorithm that produces different expected outputs"*) while guaranteeing that aggregate vs. physical hall mismatches (`Section 13`) never crash later during `FR-03`!
- **Affected Modules & Tests:** `scheduling/scheduler.py`, `allocation/hall_allocator.py`; `TC-023`, `TC-024`, `TC-037`.
- **How to Change Later:** `SchedulerFeasibilityCheck` in `scheduling/scheduler.py`.
- **Sample Output Resolvable?** **Yes** — verifiable against initial expected `timetable.csv` and `hall_plan.csv`.

### AS-033 — Canonical Output Ordering & Violation Ordering
- **Parent Rule:** `FR-06`
- **Ambiguity:** Unspecified row/record sort order in generated CSV, JSON, and TXT artefacts could break `diff`-based grading even when assignments are logically identical.
- **Interpretations:** Define explicit deterministic primary/secondary sort keys for every output artefact.
- **Provisional Selection:**
  - `timetable.csv`: `(session_date, session_slot_order [FN=0, AN=1], course_code)` (unscheduled courses, if emitted or kept only in `violations.json`, controlled by `ReportFormatPolicy` — default: `timetable.csv` lists scheduled courses sorted chronologically then `course_code`, while `UNSCHEDULED` courses appear in `violations.json`).
  - `hall_plan.csv`: `(session_date, session_slot_order, hall_id, course_code)`.
  - `seat_assignments.csv`: `(session_date, session_slot_order, hall_id, row, column)`.
  - `seat_maps.txt`: `(session_date, session_slot_order, hall_id)`, grid rendered `row = 1..rows`, `col = 1..columns`.
  - `invigilation_roster.csv`: `(session_date, session_slot_order, role_order [BUILDING_CHIEF=0, HALL_INVIGILATOR=1], building_code, hall_id_or_empty, slot_index, invigilator_id_or_UNSTAFFED)`.
  - `violations.json`: `(category_order, session_date_or_empty, session_slot_order, primary_entity_id, violation_code)`.
- **Rationale:** Guarantees 100% reproducible outputs (`NFR-01`).
- **Affected Modules & Tests:** `reporting/` formatters; `TC-108`, `TC-109`.
- **How to Change Later:** Isolated entirely inside `reporting/` adapters (`NFR-06`).
- **Sample Output Resolvable?** **Yes** — 100% resolvable the moment official sample outputs are provided.

---

## 7. Summary Matrix of Assumptions

| ID Range | Count | Domain Area | Official Sample Resolves? | Isolation Layer |
| :--- | :---: | :--- | :---: | :--- |
| `AS-001` – `AS-010` | 10 | Capacity rounding, alternate columns, small-course merge, accessibility | Yes (10/10) | `allocation/policies.py`, `allocation/accessibility.py` |
| `AS-011` – `AS-017` | 7 | Cohorts, backlog vs supplementary, session clocks, partial holidays | Yes (7/7) | `scheduling/gap_validator.py`, `scheduling/supplementary.py` |
| `AS-018` – `AS-022` | 5 | Extra-time buffer (`EC-05`), building chief rules, ISO weeks, cumulative load | Yes (5/5) | `invigilation/eligibility.py`, `invigilation/workload.py` |
| `AS-023` – `AS-033` | 11 | Tie-breakers, incremental blast radius, late seating, atomic rollback, sorting | Yes (11/11) | `changes/policies.py`, `reporting/` |
| **Total** | **33** | **Zero unresolved architectural blockers** | **33 / 33** | **Policy-isolated, standard-library pure functions** |
