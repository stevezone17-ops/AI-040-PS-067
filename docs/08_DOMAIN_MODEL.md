# 08 — Domain Model Specification

**Document Status:** Week 1 Design Baseline — Mandatory Deliverable  
**Related Diagram:** [`diagrams/03_uml_class_diagram.mmd`](diagrams/03_uml_class_diagram.mmd)  
**Related Documents:** [`03_DOMAIN_GLOSSARY.md`](03_DOMAIN_GLOSSARY.md), [`04_BUSINESS_RULE_REGISTER.md`](04_BUSINESS_RULE_REGISTER.md), [`07_SYSTEM_ARCHITECTURE.md`](07_SYSTEM_ARCHITECTURE.md)

---

## 1. Domain Modelling Principles

1. **Strict Separation of Input Registry vs. Generated State:**
   - **Immutable Master Entities (`ProblemInstance`):** `Course`, `Student`, `Enrolment`, `Building`, `Hall`, `Invigilator`, `ExamWindow`, and `ExamSession` are frozen (`@dataclass(frozen=True, slots=True)`) once parsed (with incremental late-registrant extensions represented cleanly as versioned immutable registry snapshots inside `ScheduleState` so rollbacks also revert rejected late student/enrolment additions!).
   - **Generated Schedule Entities (`ScheduleState`):** `ExamAssignment`, `HallAllocation`, `SeatAssignment`, `InvigilationAssignment`, `Violation`, and `ChangeResult` represent computed schedule decisions.
2. **Single Source of Truth for Enrolments (Ownership Model):**
   - `Enrolment` is the **sole canonical source of truth** linking `(register_number, course_code)`.
   - Neither `Course` nor `Student` stores a mutable duplicate list of objects that could drift out of sync! Instead, `ProblemRegistry` maintains an immutable indexed tuple `enrolments: tuple[Enrolment, ...]` and exposes deterministic O(1) read-only views (`enrolments_by_course[course_code] -> tuple[Enrolment, ...]` sorted by `register_number`, and `enrolments_by_student[register_number] -> tuple[Enrolment, ...]` sorted by `course_code`).
   - Consistency guarantee: During `ALG-01` input normalisation, if `students.csv` lists `backlog_courses = ["CS201"]`, `ALG-01` cross-validates that `(student_id, "CS201")` exists in `enrolments` with `is_backlog = True` (or normalises it if provided inline) so `Student.backlog_courses` and `Enrolment.is_backlog` can **never** disagree.
3. **Justification for Explicit `Building` Entity:**
   - `BR-07` mandates *"Each active building requires one additional chief invigilator per session."* Modelling `Building` explicitly (derived deterministically from `Hall.building_code` during `ALG-01`) gives `InvigilationAssignment` a clean target entity, groups halls by building without string-splitting scattered across engines, and tracks active building end-times cleanly.
4. **No Relational Database Tables:** All entities live purely in memory as typed Python dataclasses and value objects.

---

## 2. Enumerations & Value Objects

| Type Name | Kind | Values / Fields | Purpose |
| :--- | :--- | :--- | :--- |
| `SessionSlot` | `Enum` | `FN = "FN"` (`09:30–12:30`), `AN = "AN"` (`14:00–17:00`) | Fixed daily session slots (`FR-02`), ordered `FN < AN`. |
| `ColumnSlot` | `Enum` | `SET_A_ODD = "ODD"`, `SET_B_EVEN = "EVEN"` | Alternate-column partition (`BR-05`, `AS-005`). |
| `InvigilationRole` | `Enum` | `HALL_INVIGILATOR = "HALL_INVIGILATOR"`, `BUILDING_CHIEF = "BUILDING_CHIEF"` | Distinguishes hall vs building-chief duties (`BR-07`). |
| `StaffingStatus` | `Enum` | `ASSIGNED = "ASSIGNED"`, `UNSTAFFED = "UNSTAFFED"` | Explicit `BR-08` resource-shortage state. |
| `ViolationCategory` | `Enum` | `SOFT_VIOLATION`, `RESOURCE_SHORTAGE`, `UNSCHEDULED_COURSE`, `DISPLACEMENT_NOTICE`, `REJECTED_CHANGE` | Taxonomy from [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md). |
| `ChangeType` | `Enum` | `POSTPONE_COURSE`, `MARK_HALL_UNAVAILABLE`, `ADD_LATE_REGISTRANT` | Supported `FR-05` incremental commands. |
| `ChangeStatus` | `Enum` | `APPLIED`, `REJECTED_CLASH`, `REJECTED_NO_FEASIBLE_SESSION`, `REJECTED_SESSION_CAPACITY`, `REJECTED_HALL_CAPACITY`, `REJECTED_ACCESSIBILITY_CAPACITY`, `REJECTED_HALL_CLOSURE_INFEASIBLE`, `REJECTED_INVALID_COMMAND` | Deterministic outcome codes for `ChangeResult`. |
| `TimeInterval` | `ValueObject` | `start_minutes: int`, `end_minutes: int` (`0..1440`) | Exact minute-from-midnight interval (e.g., `09:30` = `570`, `17:20` = `1040`) avoiding timezone bugs (`EC-05`). |

---

## 3. Master Input Entities (`1` – `8`)

### 3.1 `Student`
- **Purpose:** Represents a registered university examinee and their accessibility/backlog attributes.
- **Identifier:** `register_number: str` (Primary Key, non-empty trimmed uppercase string, e.g., `"2462157"`).
- **Attributes:**
  - `register_number: str` *(Required)* — Unique student ID.
  - `programme: str` *(Required)* — Academic programme code (e.g., `"BTech-AIML"`).
  - `semester: int` *(Required)* — Current regular semester (`>= 1`).
  - `special_needs: bool` *(Optional, default `False`)* — Entitles student to ground-floor Row 1 + 20 extra minutes (`BR-06`).
  - `backlog_consent: bool` *(Optional, default `False`)* — `BACKLOG_CONSENT` flag (`BR-01`).
  - `is_late_registrant: bool` *(Optional, default `False`)* — `True` if added via `BR-11`.
- **Validation & Invariants:** `len(register_number) > 0`; `len(programme) > 0`; `semester >= 1`. Note: if `backlog_consent == True` while student has `0` backlog enrolments, flag stays passive (`AS-013`).
- **Relationships & Cardinalities:** `Student 1 ── 0..* Enrolment`; `Student 1 ── 0..* SeatAssignment`.
- **Business Rules:** `FR-01`, `BR-01`, `BR-02`, `BR-06`, `BR-11`.

### 3.2 `Course`
- **Purpose:** Represents an academic course requiring a single end-semester examination session.
- **Identifier:** `course_code: str` (Primary Key, e.g., `"CSA301"`).
- **Attributes:**
  - `course_code: str` *(Required)* — Unique course code.
  - `title: str` *(Optional, default `""`)* — Human-readable course name.
  - `department: str` *(Required)* — Offering department code (e.g., `"CSE"`).
  - `semester: int` *(Required)* — Curriculum semester (`>= 1`).
  - `credits: int` *(Required)* — Course credit weight (`>= 0`; derived property `is_core -> credits >= 4`).
  - `duration_hours: int` *(Required)* — Exam duration, strictly `2` or `3`.
  - `is_supplementary: bool` *(Optional, default `False`)* — Dedicated supplementary backlog paper (`BR-12`, `AS-012`).
- **Validation & Invariants:** `duration_hours in {2, 3}`; `credits >= 0`; `semester >= 1`; `is_core == (credits >= 4)`.
- **Relationships & Cardinalities:** `Course 1 ── 0..* Enrolment`; `Course 1 ── 0..1 ExamAssignment`; `Course 1 ── 0..* HallAllocation`.
- **Business Rules:** `FR-01`, `BR-02`, `BR-03`, `BR-04`, `BR-05`, `BR-12`.

### 3.3 `Enrolment`
- **Purpose:** Canonical association linking one `Student` to one `Course` (single source of truth).
- **Identifier:** Composite key `(register_number: str, course_code: str)`.
- **Attributes:**
  - `register_number: str` *(Required)* — References `Student.register_number`.
  - `course_code: str` *(Required)* — References `Course.course_code`.
  - `is_backlog: bool` *(Optional, default `False`)* — `True` if student takes this course as a backlog/arrear (`AS-012`).
- **Validation & Invariants:** Foreign keys must exist; `(register_number, course_code)` unique across registry; if `Course.is_supplementary == True`, `is_backlog` **must** be `True`.
- **Relationships & Cardinalities:** `Many-to-One` to `Student` and `Course`.
- **Business Rules:** `FR-01`, `BR-01`, `BR-02`, `BR-11`, `BR-12`.

### 3.4 `Building`
- **Purpose:** Groups physical examination halls located in the same campus building to manage `BR-07` Chief Invigilator staffing.
- **Identifier:** `building_code: str` (Primary Key, e.g., `"BLOCK-A"`).
- **Attributes:**
  - `building_code: str` *(Required)* — Unique building identifier.
  - `hall_ids: tuple[str, ...]` *(Required, derived)* — Sorted tuple of `Hall.hall_id`s belonging to this building (`len >= 1`).
- **Validation & Invariants:** Non-empty `building_code`; `hall_ids` non-empty and sorted ascending.
- **Relationships & Cardinalities:** `Building 1 ── 1..* Hall`; `Building 1 ── 0..* InvigilationAssignment` (`BUILDING_CHIEF`).
- **Business Rules:** `FR-01`, `BR-07`, `BR-08`.

### 3.5 `Hall`
- **Purpose:** Represents a physical examination room with 2D seating geometry and floor-level accessibility metadata.
- **Identifier:** `hall_id: str` (Primary Key, e.g., `"A-001"`).
- **Attributes:**
  - `hall_id: str` *(Required)* — Unique hall code.
  - `building_code: str` *(Required)* — References `Building.building_code`.
  - `floor: int` *(Required)* — Floor number (`0` = ground floor; `> 0` = upper floors; derived `is_ground_floor -> floor == 0`).
  - `rows: int` *(Required)* — Seat grid row count (`>= 1`).
  - `columns: int` *(Required)* — Seat grid column count (`>= 1`).
  - `capacity: int` *(Required)* — Declared usable seat limit (`1 <= capacity <= rows * columns`).
- **Validation & Invariants:** `rows >= 1`, `columns >= 1`, `floor >= 0`, `1 <= capacity <= rows * columns` (`AS-003`). Derived capacities: `odd_col_capacity = min(capacity, rows * ceil(columns / 2))`; `even_col_capacity = min(capacity, rows * floor(columns / 2))`.
- **Relationships & Cardinalities:** `Hall * ── 1 Building`; `Hall 1 ── 0..* HallAllocation`.
- **Business Rules:** `FR-01`, `BR-04`, `BR-05`, `BR-06`, `BR-10`.

### 3.6 `Invigilator`
- **Purpose:** Represents faculty/staff eligible for hall invigilation and building chief duties.
- **Identifier:** `invigilator_id: str` (Primary Key, e.g., `"INV-014"`).
- **Attributes:**
  - `invigilator_id: str` *(Required)* — Unique staff ID.
  - `name: str` *(Optional, default `""`)* — Staff display name.
  - `department: str` *(Required)* — Home academic department (checked against hall course departments in `BR-07`).
  - `max_weekly_sessions: int` *(Required)* — Weekly session ceiling (`4 <= max_weekly_sessions <= 8`).
  - `unavailable_dates: frozenset[date]` *(Optional, default empty)* — Full calendar dates off-duty (`BR-08`).
  - `external_duties: tuple[tuple[date, TimeInterval], ...]` *(Optional, default empty)* — Time-bounded busy windows on specific dates (`EC-05`, `AS-018`).
- **Validation & Invariants:** `4 <= max_weekly_sessions <= 8`; non-empty `department`; valid `TimeInterval` (`0 <= start < end <= 1440`).
- **Relationships & Cardinalities:** `Invigilator 1 ── 0..* InvigilationAssignment`.
- **Business Rules:** `FR-01`, `BR-07`, `BR-08`.

### 3.7 `ExamWindow`
- **Purpose:** Defines the master calendar boundaries, holidays, and slot-level closures for the examination cycle.
- **Identifier:** Singleton per `ProblemInstance` (`window_id: str = "MAIN_WINDOW"`).
- **Attributes:**
  - `start_date: date` *(Required)* — First calendar date of window.
  - `end_date: date` *(Required)* — Final calendar date of window (`end_date >= start_date`).
  - `holidays: frozenset[date]` *(Optional, default empty)* — Non-exam calendar dates (counted toward `BR-02` core gaps).
  - `closed_slots: frozenset[tuple[date, SessionSlot]]` *(Optional, default empty)* — Partial-day unavailable slots (`EC-08`, `AS-016`).
- **Validation & Invariants:** `start_date <= end_date`; yields at least `1` active `ExamSession` (`CN-06`).
- **Relationships & Cardinalities:** `ExamWindow 1 ── 1..* ExamSession`.
- **Business Rules:** `FR-02`, `BR-02`, `BR-12`.

### 3.8 `ExamSession`
- **Purpose:** Represents one concrete schedulable `(date, slot)` examination session in chronological order.
- **Identifier:** `session_id: str` (Canonical format `"YYYY-MM-DD_FN"` or `"YYYY-MM-DD_AN"`).
- **Attributes:**
  - `session_id: str` *(Required)* — Unique canonical ID.
  - `session_index: int` *(Required)* — Contiguous 0-based chronological rank (`0 .. M-1`).
  - `exam_date: date` *(Required)* — Calendar date (`exam_date not in ExamWindow.holidays`).
  - `slot: SessionSlot` *(Required)* — `FN` (`09:30–12:30`) or `AN` (`14:00–17:00`).
  - `base_window: TimeInterval` *(Required)* — `TimeInterval(570, 750)` for `FN`; `TimeInterval(840, 1020)` for `AN`.
  - `is_supplementary_window_date: bool` *(Required, derived)* — `True` iff `exam_date` is among the final 3 active exam dates (`BR-12`, `AS-015`).
  - `iso_week_key: tuple[int, int]` *(Required, derived)* — `(iso_year, iso_week)` for `BR-07` weekly tracking (`AS-021`).
- **Validation & Invariants:** Strictly monotonic `(exam_date, slot_order)` with `session_index`.
- **Relationships & Cardinalities:** `ExamSession 1 ── 0..* ExamAssignment`; `1 ── 0..* HallAllocation`; `1 ── 0..* InvigilationAssignment`.
- **Business Rules:** `FR-02`, `BR-03`, `BR-07`, `BR-12`.

---

## 4. Generated Assignment & Audit Entities (`9` – `16`)

### 4.1 `ExamAssignment`
- **Purpose:** Records the assignment of one `Course` to one `ExamSession`.
- **Identifier:** `course_code: str` (at most one active assignment per course in `ScheduleState`).
- **Attributes:**
  - `course_code: str` *(Required)*
  - `session_id: str` *(Required)*
  - `used_gap_soft_fallback: bool` *(Required, default `False`)* — `True` if placed via `BR-03` Pass-2 fallback.
  - `displaced_by_change_id: str | None` *(Optional, default `None`)* — Populated if relocated by `BR-09` or `BR-10`.
- **Invariants:** Every scheduled course appears in exactly 1 `ExamAssignment`; `UNSCHEDULED` courses have no `ExamAssignment` and appear in `Violation`s.
- **Business Rules:** `FR-02`, `BR-01`–`BR-04`, `BR-09`, `BR-10`, `BR-12`.

### 4.2 `HallAllocation`
- **Purpose:** Records the occupancy of one `Hall` during one `ExamSession` (up to 2 courses of matching duration).
- **Identifier:** Composite key `(session_id: str, hall_id: str)`.
- **Attributes:**
  - `session_id: str` *(Required)*
  - `hall_id: str` *(Required)*
  - `building_code: str` *(Required)*
  - `duration_hours: int` *(Required)* — `2` or `3` (`BR-04`).
  - `slot_a_course: str` *(Required)* — Course code in Odd Column Set A.
  - `slot_b_course: str | None` *(Optional)* — Second course code in Even Column Set B (`None` if single-course `>= 10` hall).
  - `course_student_counts: dict[str, int]` *(Required)* — Exact headcount per course in this hall (`sum > 0`, `sum <= hall.capacity`).
  - `has_special_needs: bool` *(Required)* — `True` iff $\ge 1$ `SeatAssignment` in this hall has `is_special_needs == True`.
  - `effective_window: TimeInterval` *(Required)* — `[start, start + duration*60 + (20 if has_special_needs else 0))` (`BR-06`).
  - `required_invigilators: int` *(Required, derived)* — `max(1, ceil(total_students / 30))` (`BR-07`).
- **Invariants:**
  - `1 <= len(course_student_counts) <= 2` (`BR-05`).
  - If `slot_b_course is not None`: `slot_a_course != slot_b_course` AND matching `duration_hours` (`BR-04`).
  - If any course $c$ in `course_student_counts` has total course enrolment `< 10`: `slot_b_course is not None` AND `dept(slot_a_course) != dept(slot_b_course)` (`BR-05`).
  - If `has_special_needs`: `hall.floor == 0` (`BR-06`).
- **Relationships & Cardinalities:** `HallAllocation 1 ── 1..* SeatAssignment`; `1 ── 1..* InvigilationAssignment` (hall slots).
- **Business Rules:** `FR-03`, `BR-04`, `BR-05`, `BR-06`, `BR-07`.

### 4.3 `SeatAssignment`
- **Purpose:** Assigns a single `Student` to an exact `(row, column)` seat in an occupied `HallAllocation`.
- **Identifier:** Dual uniqueness per session: `(session_id, register_number)` AND `(session_id, hall_id, row, column)`.
- **Attributes:**
  - `session_id: str` *(Required)*
  - `hall_id: str` *(Required)*
  - `row: int` *(Required)* — `1 <= row <= hall.rows`.
  - `column: int` *(Required)* — `1 <= column <= hall.columns`.
  - `seat_number: int` *(Required, derived)* — Row-major index `(row - 1) * hall.columns + column`.
  - `seat_label: str` *(Required, derived)* — `"R{row:02d}C{column:02d}"`.
  - `course_code: str` *(Required)*
  - `register_number: str` *(Required)*
  - `is_special_needs: bool` *(Required)*
- **Invariants:**
  - If `course_code == slot_a_course`: `column % 2 == 1`; if `course_code == slot_b_course`: `column % 2 == 0` (`BR-05`).
  - If `is_special_needs`: `row == 1` and `hall.floor == 0` (`BR-06`).
  - Total `SeatAssignment`s for `course_code` in `session_id` equals `len(enrolments_by_course[course_code])`.
- **Business Rules:** `FR-03`, `BR-05`, `BR-06`, `BR-11`.

### 4.4 `InvigilationAssignment`
- **Purpose:** Represents a single required staffing slot (either Hall Invigilator or Building Chief) in a session—either filled by an eligible `Invigilator` or flagged `UNSTAFFED`.
- **Identifier:** `assignment_id: str` (e.g., `"2026-12-01_FN:HALL:A-001:1"` or `"2026-12-01_FN:CHIEF:BLOCK-A:1"`).
- **Attributes:**
  - `assignment_id: str` *(Required)*
  - `session_id: str` *(Required)*
  - `role: InvigilationRole` *(Required)* — `HALL_INVIGILATOR` or `BUILDING_CHIEF`.
  - `building_code: str` *(Required)*
  - `hall_id: str | None` *(Optional)* — Required iff `role == HALL_INVIGILATOR`; `None` for `BUILDING_CHIEF`.
  - `slot_index: int` *(Required)* — `1..required_invigilators` for halls; `1` for building chief.
  - `status: StaffingStatus` *(Required)* — `ASSIGNED` or `UNSTAFFED`.
  - `invigilator_id: str | None` *(Optional)* — Populated iff `status == ASSIGNED`.
  - `duty_window: TimeInterval` *(Required)* — Hall `effective_window` (or building max `effective_window` across active halls in that building).
- **Invariants:**
  - `status == ASSIGNED` $\iff$ `invigilator_id is not None`.
  - Within a single `session_id`, every non-null `invigilator_id` appears at most once (`CN-21`).
  - If `role == HALL_INVIGILATOR` and `status == ASSIGNED`: `invigilator.department` not in hall's course departments (`BR-07`, `EC-04`).
- **Business Rules:** `FR-04`, `BR-07`, `BR-08`.

### 4.5 `Violation`
- **Purpose:** Structured record capturing permitted soft violations, staffing shortages, unscheduled courses, course displacements, or rejected-change diagnostics for `violations.json`.
- **Identifier:** `violation_id: str` (Deterministic sequential/canonical ID, e.g., `"VIOL-0001"` assigned during `ALG-20` sorting, or content key).
- **Attributes:**
  - `category: ViolationCategory` *(Required)*
  - `code: str` *(Required)* — Typed machine code (`CORE_GAP_SOFT_VIOLATION`, `HALL_UNSTAFFED`, `BUILDING_CHIEF_UNSTAFFED`, `UNSCHEDULED_COURSE`, `COURSE_DISPLACED_BY_HALL_CLOSURE`, `REJECTED_CLASH`, etc.).
  - `rule_id: str` *(Required)* — e.g., `"BR-02"`, `"BR-08"`, `"BR-10"`, `"BR-11"`.
  - `session_id: str | None` *(Optional)*
  - `entity_ids: tuple[str, ...]` *(Required)* — Affected `course_code`(s), `hall_id`, `building_code`, or `register_number`.
  - `message: str` *(Required)* — Clear diagnostic explanation.
  - `source_command_id: str | None` *(Optional)* — `None` for initial synthesis; `command_id` if produced by `FR-05`.
- **Invariants:** Every `UNSTAFFED` `InvigilationAssignment` and every `used_gap_soft_fallback == True` `ExamAssignment` has a corresponding active `Violation`.
- **Business Rules:** `FR-06`, `BR-03`, `BR-08`, `BR-10`, `BR-11`.

### 4.6 `ChangeCommand`
- **Purpose:** Typed representation of an incremental operational request from `commands.json`.
- **Identifier:** `command_id: str` (e.g., `"CMD-001"`).
- **Attributes:**
  - `command_id: str` *(Required)* — Unique command ID in execution sequence `0..K-1`.
  - `sequence_no: int` *(Required)* — 1-based execution order.
  - `change_type: ChangeType` *(Required)* — `POSTPONE_COURSE`, `MARK_HALL_UNAVAILABLE`, or `ADD_LATE_REGISTRANT`.
  - `course_code: str | None` *(Conditional)* — Required for `POSTPONE_COURSE`.
  - `min_target_date: date | None` *(Optional)* — Optional floor date for `POSTPONE_COURSE` (`AS-026`).
  - `hall_id: str | None` *(Conditional)* — Required for `MARK_HALL_UNAVAILABLE`.
  - `target_session_ids: tuple[str, ...]` *(Conditional)* — Session(s) in which `hall_id` becomes unavailable (supports single session, full date, or all remaining sessions).
  - `student_payload: Student | None` *(Conditional)* — Required if late registrant is a new student (`ADD_LATE_REGISTRANT`).
  - `late_enrolments: tuple[Enrolment, ...]` *(Conditional)* — Required non-empty tuple for `ADD_LATE_REGISTRANT`.
- **Validation & Invariants:** Type-specific required attributes verified before candidate execution.
- **Business Rules:** `FR-05`, `BR-09`, `BR-10`, `BR-11`.

### 4.7 `ChangeResult`
- **Purpose:** Immutable audit record of executing one `ChangeCommand`.
- **Identifier:** `command_id: str` (1-to-1 with `ChangeCommand`).
- **Attributes:**
  - `command_id: str` *(Required)*
  - `change_type: ChangeType` *(Required)*
  - `status: ChangeStatus` *(Required)* — `APPLIED` or `REJECTED_*`.
  - `affected_sessions: tuple[str, ...]` *(Required)* — Sorted tuple of `session_id`s mutated (`()` if rejected).
  - `conflicting_courses: tuple[str, ...]` *(Optional, default `()`)* — Populated with the 2 clashing course codes when `status == REJECTED_CLASH` (`BR-11`).
  - `displaced_courses: tuple[tuple[str, str, str], ...]` *(Optional, default `()`)* — `(course_code, from_session, to_session)` for `BR-10` / `BR-09`.
  - `unaffected_sessions_verified: bool` *(Required)* — `True` confirming cryptographic fingerprint equality of all non-affected sessions (`NFR-03`).
  - `reason: str` *(Required)* — Human-readable outcome summary.
- **Business Rules:** `FR-05`, `FR-06`, `BR-09`, `BR-10`, `BR-11`.

### 4.8 `ScheduleState`
- **Purpose:** Top-level versioned aggregate holding the complete consistent snapshot of registries, assignments, closures, and violations at step `version`.
- **Identifier:** `state_version: int` (`0` = initial synthesis; incremented on each `APPLIED` change command).
- **Attributes:**
  - `state_version: int` *(Required)*
  - `registry: ProblemRegistry` *(Required)* — Immutable master collections (`courses`, `students`, `enrolments`, `buildings`, `halls`, `invigilators`, `exam_window`, `sessions`).
  - `closed_hall_sessions: frozenset[tuple[str, str]]` *(Required)* — Active `(session_id, hall_id)` closures applied via `BR-10`.
  - `exam_assignments: dict[str, ExamAssignment]` *(Required)* — Keyed by `course_code`.
  - `session_courses: dict[str, tuple[str, ...]]` *(Required, derived/synced)* — Keyed by `session_id`, sorted `course_code`s.
  - `hall_allocations: dict[str, tuple[HallAllocation, ...]]` *(Required)* — Keyed by `session_id`, sorted by `hall_id`.
  - `seat_assignments: dict[str, tuple[SeatAssignment, ...]]` *(Required)* — Keyed by `session_id`, sorted by `(hall_id, row, column)`.
  - `invigilation_assignments: dict[str, tuple[InvigilationAssignment, ...]]` *(Required)* — Keyed by `session_id`.
  - `active_violations: tuple[Violation, ...]` *(Required)* — Current schedule violations (`SOFT_VIOLATION`, `RESOURCE_SHORTAGE`, `UNSCHEDULED_COURSE`, `DISPLACEMENT_NOTICE`).
  - `change_history: tuple[ChangeResult, ...]` *(Required)* — Ordered history of all executed commands (both `APPLIED` and `REJECTED_*`).
- **Aggregate Invariants:**
  1. `session_courses` is the exact inverse projection of `exam_assignments`.
  2. Every `session_id` key across `hall_allocations`, `seat_assignments`, and `invigilation_assignments` belongs to `registry.sessions`.
  3. No `(session_id, hall_id)` in `closed_hall_sessions` appears in `hall_allocations[session_id]`.
  4. Passes `IndependentScheduleValidator.validate(state)` with zero hard-constraint errors.
