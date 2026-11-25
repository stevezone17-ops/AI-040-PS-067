# Architecture & Behavioural Diagrams Catalogue

**Document Status:** Week 1 Design Baseline — 12 Validated Mermaid Diagrams  
**Related Documents:** [`../07_SYSTEM_ARCHITECTURE.md`](../07_SYSTEM_ARCHITECTURE.md), [`../08_DOMAIN_MODEL.md`](../08_DOMAIN_MODEL.md), [`../09_ALGORITHM_DESIGN.md`](../09_ALGORITHM_DESIGN.md), [`../11_INCREMENTAL_RECOMPUTATION.md`](../11_INCREMENTAL_RECOMPUTATION.md)

---

## Diagram Index & Engineering Walkthroughs

Every diagram below is stored as a standalone, version-controlled Mermaid source file (`.mmd`) and includes explicit success, partial-resource (`UNSTAFFED`, `SOFT_VIOLATION`, `UNSCHEDULED`), and failure/rollback paths.

| # | Mermaid Source File | Diagram Type | Engineering Purpose & Model Alignment |
| :---: | :--- | :--- | :--- |
| **01** | [`01_system_context.mmd`](01_system_context.mmd) | Flowchart (`LR`) | Shows external actors (Examination Cell, Department Coordinators, Auditors), the 7 provisional input files, the CLI engine boundary, and the 8 deterministic output files. |
| **02** | [`02_component_architecture.mmd`](02_component_architecture.mmd) | Flowchart (`TB`) | Maps all 14 required architectural components across 5 strict unidirectional layers (`Interface -> Adapters -> Control/Audit -> Constructive Engines -> Pure Domain Kernel`). |
| **03** | [`03_uml_class_diagram.mmd`](03_uml_class_diagram.mmd) | UML `classDiagram` | Models all 16 domain entities (`Student`, `Course`, `Enrolment`, `Building`, `Hall`, `Invigilator`, `ExamWindow`, `ExamSession`, `ExamAssignment`, `HallAllocation`, `SeatAssignment`, `InvigilationAssignment`, `Violation`, `ChangeCommand`, `ChangeResult`, `ScheduleState`) with exact attributes and cardinalities (`1`, `0..1`, `0..*`, `1..*`). |
| **04** | [`04_scheduling_state_diagram.mmd`](04_scheduling_state_diagram.mmd) | `stateDiagram-v2` | Captures full batch execution states including fatal input abort (`Exit 2`), `ALG-18` integrity abort (`Exit 3`), clean/soft-fallback/partial schedules, and incremental loop transitions. |
| **05** | [`05_change_command_state_diagram.mmd`](05_change_command_state_diagram.mmd) | `stateDiagram-v2` | Models transactional lifecycle of a `ChangeCommand`: validation, snapshot hashing, clash/capacity precheck, local recomputation, global `ALG-18` audit, SHA-256 unaffected-session verification, commit (`v+1`), and rollback (`v`). |
| **06** | [`06_timetable_generation_activity.mmd`](06_timetable_generation_activity.mmd) | Activity (`flowchart TD`) | Traces `ALG-06`: `BR-03` sorting, Pass-1 (`Hard + Core Gap + Hall Packable`), Pass-2 (`Hard + Hall Packable + CORE_GAP_SOFT_VIOLATION`), small-course co-scheduling (`ALG-10`), and `UNSCHEDULED_COURSE` reporting. |
| **07** | [`07_hall_allocation_activity.mmd`](07_hall_allocation_activity.mmd) | Activity (`flowchart TD`) | Traces `ALG-08`–`ALG-12`: 90% session cap, ground-floor Row-1 reservation for `special_needs`, largest-hall-first allocation, `< 10` cross-department merging, alternate-column seating, and `+20m` hall extension. |
| **08** | [`08_invigilator_assignment_activity.mmd`](08_invigilator_assignment_activity.mmd) | Activity (`flowchart TD`) | Traces `ALG-13` & `ALG-14`: `ceil(n/30)` hall slots, `EC-04` merged-dept exclusion, `EC-05` extended-duty overlap filtering, daily/ISO-weekly caps, `BR-08` sorting, `BUILDING_CHIEF` assignment, and `UNSTAFFED` reporting. |
| **09** | [`09_course_postponement_sequence.mmd`](09_course_postponement_sequence.mmd) | `sequenceDiagram` | Shows `BR-09` (`POSTPONE_COURSE`) interactions across Orchestrator, StateManager, PostponementEngine, Hall/Invigilation engines, and Validator, isolating `{S_orig, S_dest}` and handling rollbacks. |
| **10** | [`10_hall_unavailability_sequence.mmd`](10_hall_unavailability_sequence.mmd) | `sequenceDiagram` | Shows `BR-10` (`MARK_HALL_UNAVAILABLE`): unoccupied no-op, same-session reallocation to next largest hall, iterative smallest-course displacement (`COURSE_DISPLACED_BY_HALL_CLOSURE`), and infeasible rollback. |
| **11** | [`11_late_registration_sequence.mmd`](11_late_registration_sequence.mmd) | `sequenceDiagram` | Shows `BR-11` (`ADD_LATE_REGISTRANT`): atomic `REJECTED_CLASH` detection with 2 course codes, most-free-seats hall selection, single-column-set re-seating, and minimal delta invigilation. |
| **12** | [`12_incremental_recomputation_dependency.mmd`](12_incremental_recomputation_dependency.mmd) | Flowchart (`TD`) | Visualises the exact state dependency DAG separating session-local mutable records from cross-session read-only constraints and SHA-256 unaffected-session digests. |
