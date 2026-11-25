# 09 — Algorithm Design Specification

**Document Status:** Week 1 Design Baseline — Implementation-Ready Specification  
**Related Diagrams:** [`diagrams/06_timetable_generation_activity.mmd`](diagrams/06_timetable_generation_activity.mmd), [`diagrams/07_hall_allocation_activity.mmd`](diagrams/07_hall_allocation_activity.mmd), [`diagrams/08_invigilator_assignment_activity.mmd`](diagrams/08_invigilator_assignment_activity.mmd)  
**Related Documents:** [`04_BUSINESS_RULE_REGISTER.md`](04_BUSINESS_RULE_REGISTER.md), [`05_ASSUMPTION_REGISTER.md`](05_ASSUMPTION_REGISTER.md), [`08_DOMAIN_MODEL.md`](08_DOMAIN_MODEL.md), [`11_INCREMENTAL_RECOMPUTATION.md`](11_INCREMENTAL_RECOMPUTATION.md)

> [!NOTE]
> **Theoretical Scope & Non-Optimality Notice:** `ALG-06` implements the prescribed deterministic greedy heuristic (`BR-03`). Because university exam timetabling generalises bounded graph colouring coupled with 2D spatial bin-packing (NP-hard), greedy scheduling **does not guarantee finding a globally optimal or feasible schedule for every theoretically satisfiable input dataset**. Instead, it guarantees 100% deterministic, reproducible, auditable behaviour matching `BR-03`, distinguishes aggregate 90% session capacity from concrete hall/seat packability (`ALG-08`), provides bounded deterministic small-course merge repair (`ALG-10`), and reports hard infeasibility explicitly rather than silently breaking rules.

---

## Notation

Let $C$ = courses ($\sim 120$), $S$ = students ($\sim 2{,}500$), $E$ = enrolments ($\sim 12{,}500$, average $k \approx 5$ courses/student), $H$ = halls ($\sim 18$), $B$ = buildings ($\le H$), $V$ = invigilators ($\sim 90$), $M$ = active sessions ($\sim 20$), $D$ = calendar days in window ($\sim 12$), and $K$ = change commands ($\sim 8$).

---

## ALG-01 — Input Validation and Normalisation

- **Business Rules:** `FR-01`, `FR-02`, `CN-01`–`CN-06`, `AS-003`, `AS-012`.
- **Inputs:** Raw parsed records from `courses.csv`, `students.csv`, `enrolments.csv`, `halls.csv`, `invigilators.csv`, `exam_window.json`, and optional `commands.json`.
- **Outputs:** `Result[tuple[ProblemRegistry, tuple[ChangeCommand, ...]], tuple[InputValidationError, ...]]`.
- **Preconditions:** Files exist and are syntactically parseable UTF-8 CSV/JSON.
- **Postconditions:** Unique primary keys across all registries; resolved foreign keys; `duration_hours in {2, 3}`; `1 <= hall.capacity <= rows * columns`; `4 <= max_weekly_sessions <= 8`; canonical `Enrolment` index built as single source of truth.
- **Tie-Breaking:** Validation errors sorted by `(file_name, row_number, error_code)`.
- **Failure Cases:** `ERR_MISSING_REQUIRED_FIELD`, `ERR_DUPLICATE_KEY`, `ERR_UNKNOWN_REFERENCE`, `ERR_DUPLICATE_ENROLMENT`, `ERR_INVALID_COURSE`, `ERR_INVALID_HALL_DIMENSIONS`, `ERR_INVALID_INVIGILATOR`, `ERR_EMPTY_EXAM_WINDOW`.
- **Complexity:** Time $\mathcal{O}(C + S + E \log E + H \log H + V \log V)$; Space $\mathcal{O}(C + S + E + H + V)$.
- **Pseudocode:**
```text
FUNCTION normalise_and_validate(raw) -> Result:
    errors <- []
    courses <- parse_unique(raw.courses, pk="course_code", errors)
    FOR c IN courses.values():
        IF c.duration_hours NOT IN {2, 3} OR c.credits < 0 OR c.semester < 1:
            errors.append(Error("ERR_INVALID_COURSE", c.course_code))

    students <- parse_unique(raw.students, pk="register_number", errors)
    halls <- parse_unique(raw.halls, pk="hall_id", errors)
    FOR h IN halls.values():
        IF h.rows < 1 OR h.columns < 1 OR h.floor < 0 OR NOT (1 <= h.capacity <= h.rows * h.columns):
            errors.append(Error("ERR_INVALID_HALL_DIMENSIONS", h.hall_id))

    invigilators <- parse_unique(raw.invigilators, pk="invigilator_id", errors)
    FOR v IN invigilators.values():
        IF NOT (4 <= v.max_weekly_sessions <= 8):
            errors.append(Error("ERR_INVALID_INVIGILATOR", v.invigilator_id))

    seen_enrols <- set(); enrolments <- []
    FOR row IN raw.enrolments:
        key <- (norm_id(row.register_number), norm_id(row.course_code))
        IF key[0] NOT IN students OR key[1] NOT IN courses:
            errors.append(Error("ERR_UNKNOWN_REFERENCE", key))
        ELSE IF key IN seen_enrols:
            errors.append(Error("ERR_DUPLICATE_ENROLMENT", key))
        ELSE:
            seen_enrols.add(key)
            is_bg <- row.is_backlog OR (key[1] IN students[key[0]].declared_backlogs) OR courses[key[1]].is_supplementary
            enrolments.append(Enrolment(key[0], key[1], is_bg))

    sessions <- ALG_02_generate_sessions(raw.exam_window, errors)
    IF errors IS NOT EMPTY: RETURN Failure(sort_errors(errors))
    buildings <- derive_sorted_buildings(halls)
    RETURN Success(build_registry(courses, students, enrolments, buildings, halls, invigilators, sessions))
```
- **Worked Example:** Hall `H04` with `rows=6, columns=8` (`48` grid positions) and `capacity=50` fails `1 <= 50 <= 48` and halts with `ERR_INVALID_HALL_DIMENSIONS`.

---

## ALG-02 — Examination Session Generation

- **Business Rules:** `FR-02`, `BR-02`, `BR-12`, `EC-08`, `AS-015`, `AS-016`.
- **Inputs:** `ExamWindow(start_date, end_date, holidays, closed_slots)`.
- **Outputs:** Chronological `tuple[ExamSession, ...]`.
- **Preconditions:** `start_date <= end_date`.
- **Postconditions:** Contiguous `session_index = 0..M-1`; `FN` (`09:30–12:30`) precedes `AN` (`14:00–17:00`) per date; `is_supplementary_window_date = True` on the final 3 active examination dates.
- **Tie-Breaking:** `(exam_date ASC, slot_order [FN=0, AN=1] ASC)`.
- **Failure Cases:** Zero active sessions after holiday/slot filtering -> `ERR_EMPTY_EXAM_WINDOW`.
- **Complexity:** Time $\mathcal{O}(D)$; Space $\mathcal{O}(M \le 2D)$.
- **Pseudocode:**
```text
FUNCTION generate_sessions(window: ExamWindow) -> tuple[ExamSession, ...]:
    pairs <- []
    FOR d FROM window.start_date TO window.end_date:
        IF d NOT IN window.holidays:
            FOR slot IN [FN, AN]:
                IF (d, slot) NOT IN window.closed_slots:
                    pairs.append((d, slot))
    IF pairs IS EMPTY: RAISE ValidationError("ERR_EMPTY_EXAM_WINDOW")
    active_dates <- sorted_unique([d FOR (d, _) IN pairs])
    supp_dates <- set(active_dates[max(0, len(active_dates) - 3) : ])
    RETURN tuple(
        ExamSession(
            session_id = f"{d.isoformat()}_{slot.value}",
            session_index = i, exam_date = d, slot = slot,
            base_window = TimeInterval(570, 750) IF slot == FN ELSE TimeInterval(840, 1020),
            is_supplementary_window_date = (d IN supp_dates),
            iso_week_key = (d.isocalendar().year, d.isocalendar().week)
        ) FOR i, (d, slot) IN enumerate(pairs)
    )
```
- **Worked Example (`EC-08`):** `Dec 01–Dec 04`, `Dec 02` holiday, `Dec 04 AN` closed -> generates 5 sessions ending at `2026-12-04_FN`, with `supp_dates = {Dec 01, Dec 03, Dec 04}`.

---

## ALG-03 — Student Conflict Graph Construction

- **Business Rules:** `BR-01`, `EC-06`, `EC-07`, `AS-013`, `AS-014`.
- **Inputs:** `ProblemRegistry` (`students`, `enrolments_by_student`).
- **Outputs:** `ConflictGraph(same_session_forbidden, same_day_forbidden)`.
- **Preconditions:** Validated `Enrolment` records.
- **Postconditions:**
  - `v in same_session_forbidden[u]` iff $\ge 1$ student takes both $u$ and $v$.
  - `v in same_day_forbidden[u]` iff $\ge 1$ shared student has `not backlog_consent` OR takes **both** $u$ and $v$ as regular (`not is_backlog`) courses (`AS-013`).
- **Tie-Breaking:** Adjacency sets stored as sorted `frozenset` / `tuple` for deterministic diagnostics.
- **Failure Cases:** None (pure graph construction).
- **Complexity:** Time $\mathcal{O}(S \cdot k^2 + C^2)$; Space $\mathcal{O}(C^2)$.
- **Pseudocode:**
```text
FUNCTION build_conflict_graph(registry: ProblemRegistry) -> ConflictGraph:
    same_sess <- defaultdict(set); same_day <- defaultdict(set)
    FOR s_id, enrols IN registry.enrolments_by_student.items():
        stu <- registry.students[s_id]
        FOR i FROM 0 TO len(enrols) - 1:
            FOR j FROM i + 1 TO len(enrols) - 1:
                u, v <- enrols[i].course_code, enrols[j].course_code
                same_sess[u].add(v); same_sess[v].add(u)
                consent_ok <- stu.backlog_consent AND (enrols[i].is_backlog OR enrols[j].is_backlog)
                IF NOT consent_ok:
                    same_day[u].add(v); same_day[v].add(u)
    RETURN ConflictGraph(freeze(same_sess), freeze(same_day))
```
- **Worked Example:** Student `S1` (`backlog_consent=True`) takes regular `CS601`, regular `CS602`, and backlog `CS401`. `(CS601, CS602)` is forbidden same-day; `(CS601, CS401)` is forbidden same-session only, permitting `FN` + `AN` on the same day!

---

## ALG-04 — Programme-Semester Core-Course Gap Validation

- **Business Rules:** `BR-02`, `EC-01`, `AS-011`.
- **Inputs:** `course: Course`, `cand_session: ExamSession`, `exam_assignments`, `cohorts_map`, `registry`.
- **Outputs:** `(is_gap_valid: bool, violating_courses: tuple[str, ...])`.
- **Preconditions:** `cohorts_map[c]` holds union of `(s.programme, s.semester)` over non-backlog students of $c$.
- **Postconditions:** Returns `(True, ())` if `course.credits < 4`; else verifies `abs((cand_session.exam_date - other_date).days) >= 2` against every scheduled core course sharing a cohort.
- **Complexity:** Time $\mathcal{O}(C)$; Space $\mathcal{O}(C)$.
- **Pseudocode:**
```text
FUNCTION check_core_gap(course, cand_session, exam_assignments, cohorts_map, registry):
    IF course.credits < 4: RETURN (True, ())
    my_cohorts <- cohorts_map[course.course_code]
    violators <- []
    FOR other_code, assign IN sorted_items(exam_assignments):
        other <- registry.courses[other_code]
        IF other.credits >= 4 AND (my_cohorts INTERSECT cohorts_map[other_code]) IS NOT EMPTY:
            other_date <- registry.sessions_by_id[assign.session_id].exam_date
            IF abs((cand_session.exam_date - other_date).days) < 2:
                violators.append(other_code)
    RETURN (len(violators) == 0, tuple(violators))
```
- **Worked Example:** Core exam on Monday `Dec 01`, holiday on Tuesday `Dec 02`, second core exam on Wednesday `Dec 03` -> `|Dec 03 - Dec 01| = 2 >= 2` -> `True`.

---

## ALG-05 — Deterministic Course Ordering

- **Business Rules:** `BR-03`.
- **Inputs:** `ProblemRegistry`.
- **Outputs:** `tuple[Course, ...]` sorted by `(-enrolment_count, -credits, course_code)`.
- **Preconditions:** Canonical `enrolments_by_course` populated.
- **Postconditions:** Strict total ordering across all courses.
- **Complexity:** Time $\mathcal{O}(C \log C)$; Space $\mathcal{O}(C)$.
- **Pseudocode:**
```text
FUNCTION order_courses(registry: ProblemRegistry) -> tuple[Course, ...]:
    RETURN tuple(sorted(
        registry.courses.values(),
        key = LAMBDA c: (-len(registry.enrolments_by_course[c.course_code]), -c.credits, c.course_code)
    ))
```
- **Worked Example:** `(CS101: 90 students, 4 cr)`, `(AI101: 90 students, 4 cr)`, `(EC101: 90 students, 3 cr)` -> `[AI101, CS101, EC101]`.

---

## ALG-06 — Earliest-Feasible-Session Timetable Generation

- **Business Rules:** `BR-01`, `BR-02`, `BR-03`, `BR-04`, `BR-05`, `BR-06`, `BR-12`, `EC-01`, `EC-07`, `AS-006`, `AS-032`.
- **Inputs:** `ProblemRegistry`, `ConflictGraph`, `cohorts_map`.
- **Outputs:** `(exam_assignments, session_courses, violations)`.
- **Preconditions:** `ALG-01`–`ALG-05` complete.
- **Postconditions:** Every scheduled course satisfies all hard rules AND exact hall/accessibility packability (`ALG-08`); `CORE_GAP_SOFT_VIOLATION` logged iff Pass 2 was used; hard-infeasible courses logged as `UNSCHEDULED_COURSE`.
- **Complexity:** Time $\mathcal{O}(C \cdot M \cdot (C_{\text{sess}} + H \log H))$; Space $\mathcal{O}(C + M \cdot H)$.
- **Pseudocode:**
```text
FUNCTION generate_timetable(registry, conflict_graph, cohorts_map):
    ordered <- ALG_05_order_courses(registry)
    assignments <- {}; session_courses <- {s.session_id: [] FOR s IN registry.sessions}
    violations <- []; deferred_small <- []

    FOR course IN ordered:
        enrol_cnt <- len(registry.enrolments_by_course[course.course_code])
        chosen <- None; fallback <- False; violators <- ()

        # Pass 1: Hard rules + Core Gap (BR-02) + Exact Hall Packability (ALG-08)
        FOR sess IN registry.sessions:
            IF is_hard_feasible(course, sess, session_courses, registry, conflict_graph):
                gap_ok, _ <- ALG_04_check_core_gap(course, sess, assignments, cohorts_map, registry)
                IF gap_ok: chosen <- sess; BREAK

        # Pass 2: Hard rules only -> record SOFT_VIOLATION (BR-03)
        IF chosen IS None:
            FOR sess IN registry.sessions:
                IF is_hard_feasible(course, sess, session_courses, registry, conflict_graph):
                    _, violators <- ALG_04_check_core_gap(course, sess, assignments, cohorts_map, registry)
                    chosen <- sess; fallback <- True; BREAK

        IF chosen IS NOT None:
            assignments[course.course_code] <- ExamAssignment(course.course_code, chosen.session_id, fallback)
            session_courses[chosen.session_id].append(course.course_code)
            IF fallback:
                violations.append(make_soft_gap_violation(course, chosen, violators))
        ELSE IF 1 <= enrol_cnt < 10:
            deferred_small.append(course)   # Repair: co-schedule compatible small-course pairs (ALG-10)
        ELSE:
            violations.append(make_unscheduled_violation(course))

    IF deferred_small IS NOT EMPTY:
        ALG_10_coschedule_deferred_small_courses(deferred_small, assignments, session_courses, violations, registry, conflict_graph, cohorts_map)

    RETURN assignments, session_courses, violations

FUNCTION is_hard_feasible(course, sess, session_courses, registry, conflict_graph) -> bool:
    IF NOT ALG_07_is_supplementary_eligible(course, sess, registry): RETURN False
    FOR c_other IN session_courses[sess.session_id]:
        IF c_other IN conflict_graph.same_session_forbidden[course.course_code]: RETURN False
    FOR sib IN registry.sessions_on_date[sess.exam_date]:
        IF sib.session_id != sess.session_id:
            FOR c_other IN session_courses[sib.session_id]:
                IF c_other IN conflict_graph.same_day_forbidden[course.course_code]: RETURN False
    RETURN ALG_08_check_and_pack_session(sess, session_courses[sess.session_id] + [course.course_code], registry, empty_set()).is_feasible
```
- **Worked Example (`EC-01`):** Only `Dec 01` and `Dec 02` exist for two Sem-6 core courses `AIML601` and `AIML602`. `AIML601` takes `Dec 01 FN` in Pass 1; `AIML602` finds zero Pass-1 slots (`|Dec 02 - Dec 01| = 1 < 2`), takes `Dec 02 FN` in Pass 2, and emits `CORE_GAP_SOFT_VIOLATION`.

---

## ALG-07 — Supplementary Examination Eligibility

- **Business Rules:** `BR-12`, `EC-08`, `AS-015`.
- **Inputs:** `course: Course`, `session: ExamSession`, `registry: ProblemRegistry`.
- **Outputs:** `bool`.
- **Preconditions:** `session.is_supplementary_window_date` precomputed by `ALG-02`.
- **Postconditions:** Regular courses return `True`; supplementary courses return `True` iff in final 3 active exam dates AND (`slot == AN` OR `enrolment_count > 50`).
- **Complexity:** Time $\mathcal{O}(1)$; Space $\mathcal{O}(1)$.
- **Pseudocode:**
```text
FUNCTION is_supplementary_eligible(course, session, registry) -> bool:
    IF NOT course.is_supplementary: RETURN True
    IF NOT session.is_supplementary_window_date: RETURN False
    IF len(registry.enrolments_by_course[course.course_code]) > 50:
        RETURN session.slot IN {FN, AN}
    RETURN session.slot == AN
```
- **Worked Example:** `50` supplementary students -> `AN` only; `51` supplementary students -> `FN` or `AN` on final 3 exam days.

---

## ALG-08 — Hall Feasibility and Duration Compatibility

- **Business Rules:** `BR-04`, `BR-05`, `BR-06`, `EC-03`, `AS-001`–`AS-010`.
- **Inputs:** `session`, `course_codes`, `registry`, `closed_halls`.
- **Outputs:** `PackingResult(is_feasible: bool, allocations: tuple[HallAllocation, ...], failure_code: str | None)`.
- **Preconditions:** Candidate courses belong to `session`.
- **Postconditions:** Verifies both aggregate 90% session cap (`(90 * total_cap) // 100`) AND concrete 2D hall packing (`2h` vs `3h` isolation, alternate columns, ground-floor Row 1, `< 10` merges).
- **Complexity:** Time $\mathcal{O}(H \log H + |C_{\text{sess}}| \cdot H)$; Space $\mathcal{O}(H)$.
- **Pseudocode:**
```text
FUNCTION check_and_pack_session(session, course_codes, registry, closed_halls) -> PackingResult:
    IF course_codes IS EMPTY: RETURN PackingResult(True, (), None)
    avail_halls <- [h FOR h IN registry.halls.values() IF (session.session_id, h.hall_id) NOT IN closed_halls]
    IF avail_halls IS EMPTY: RETURN PackingResult(False, (), "NO_AVAILABLE_HALLS")

    cap_90 <- (90 * sum(h.capacity FOR h IN avail_halls)) // 100
    total_stu <- sum(len(registry.enrolments_by_course[c]) FOR c IN course_codes)
    IF total_stu > cap_90:
        RETURN PackingResult(False, (), "SESSION_90_PERCENT_CAP_EXCEEDED")

    RETURN ALG_09_allocate_halls(session, course_codes, avail_halls, registry)
```
- **Worked Example (`EC-03`):** Available hall capacities sum to `105` -> `(90 * 105) // 100 = 94`. `94` students pass; `95` students fail `SESSION_90_PERCENT_CAP_EXCEEDED`.

---

## ALG-09 — Largest-First Hall Allocation

- **Business Rules:** `BR-04`, `BR-05`, `BR-06`, `AS-004`, `AS-005`, `AS-008`, `AS-010`, `AS-023`, `AS-024`.
- **Inputs:** `session`, `course_codes`, `avail_halls`, `registry`.
- **Outputs:** `PackingResult`.
- **Tie-Breaking:** Halls sorted by `(-h.capacity, h.hall_id)`; courses sorted by `BR-03` key; ground-floor (`floor == 0`) halls reserved first for courses with `special_needs` students (`AS-010`).
- **Complexity:** Time $\mathcal{O}(|C_{\text{sess}}| \cdot H + H \log H)$; Space $\mathcal{O}(H)$.
- **Pseudocode:**
```text
FUNCTION allocate_halls(session, course_codes, avail_halls, registry) -> PackingResult:
    active <- [registry.courses[c] FOR c IN course_codes IF len(registry.enrolments_by_course[c]) > 0]
    IF active IS EMPTY: RETURN PackingResult(True, (), None)

    large <- sort_br03([c FOR c IN active IF enrol_count(c) >= 10])
    small <- sort_br03([c FOR c IN active IF 1 <= enrol_count(c) < 10])
    all_halls    <- sorted(avail_halls, key = LAMBDA h: (-h.capacity, h.hall_id))
    ground_halls <- [h FOR h IN all_halls IF h.floor == 0]
    open_halls   <- {}

    # 1. Reserve ground-floor Row 1 seats for courses with special-needs students
    sn_courses <- [c FOR c IN (large + small) IF sn_count(c) > 0]
    IF NOT allocate_ground_floor_special_needs(sn_courses, ground_halls, open_halls, registry):
        RETURN PackingResult(False, (), "INSUFFICIENT_ACCESSIBLE_SEATS")

    # 2. Pack remaining students of >=10 courses largest-hall-first (odd Set A, or compatible open even Set B)
    FOR c IN large:
        rem <- unallocated_count(c, open_halls, registry)
        rem <- fill_open_slot_b(c, rem, open_halls, all_halls, same_dept_ok=False)
        FOR h IN all_halls:
            IF rem == 0: BREAK
            IF h.hall_id NOT IN open_halls:
                take <- min(rem, odd_col_cap(h))
                open_halls[h.hall_id] <- HallDraft(h, slot_a=c, count_a=take)
                rem <- rem - take
        IF rem > 0:
            rem <- fill_open_slot_b(c, rem, open_halls, all_halls, same_dept_ok=True)
        IF rem > 0:
            RETURN PackingResult(False, (), "HALL_CAPACITY_EXHAUSTED")

    # 3. Merge <10 small courses (ALG-10)
    IF NOT ALG_10_merge_small_courses(small, open_halls, all_halls, registry):
        RETURN PackingResult(False, (), "SMALL_COURSE_NO_MERGE_PARTNER")

    RETURN PackingResult(True, build_hall_allocations(session, open_halls, registry), None)
```
- **Worked Example:** Two halls `H1(cap=60)` and `H2(cap=60)` tie on capacity -> `H1` is selected before `H2` (`"H1" < "H2"`).

---

## ALG-10 — Mandatory Small-Course Merging

- **Business Rules:** `BR-05`, `EC-02`, `AS-006`, `AS-007`.
- **Inputs:** `small_courses` (`1 <= enrolment < 10`), `open_halls`, `all_halls`, `registry`.
- **Outputs:** `bool` (and `ALG_10_coschedule_deferred_small_courses` for `ALG-06` deferred pairs).
- **Preconditions:** `1 <= enrolment < 10`.
- **Postconditions:** Every small course shares its hall with a second course of identical `duration_hours` and **different `department`**.
- **Tie-Breaking:** Largest open compatible 1-course hall first; else pair two waiting small courses `(c_i, c_j)` in `BR-03` order into largest unused hall.
- **Complexity:** Time $\mathcal{O}(|C_{\text{small}}|^2 + |C_{\text{small}}| \cdot H)$; Space $\mathcal{O}(|C_{\text{small}}|)$.
- **Pseudocode:**
```text
FUNCTION merge_small_courses(small_courses, open_halls, all_halls, registry) -> bool:
    waiting <- []
    FOR c IN small_courses:
        rem <- unallocated_count(c, open_halls, registry)
        IF rem == 0: CONTINUE
        merged <- False
        FOR h IN all_halls:
            IF h.hall_id IN open_halls:
                d <- open_halls[h.hall_id]
                IF d.slot_b IS None AND d.duration == c.duration_hours AND d.slot_a.department != c.department:
                    IF min(h.capacity - d.count_a, even_col_cap(h)) >= rem:
                        d.set_slot_b(c, rem); merged <- True; BREAK
        IF NOT merged: waiting.append(c)

    # Pair remaining small courses with each other across different departments (AS-007)
    paired <- set()
    FOR i FROM 0 TO len(waiting) - 1:
        IF i IN paired: CONTINUE
        c1 <- waiting[i]; j_match <- None
        FOR j FROM i + 1 TO len(waiting) - 1:
            IF j NOT IN paired AND waiting[j].duration_hours == c1.duration_hours AND waiting[j].department != c1.department:
                j_match <- j; BREAK
        IF j_match IS None: RETURN False
        c2 <- waiting[j_match]
        h <- first_unused_hall_fitting_pair(c1, c2, open_halls, all_halls)
        IF h IS None: RETURN False
        open_halls[h.hall_id] <- HallDraft(h, slot_a=c1, count_a=enrol(c1), slot_b=c2, count_b=enrol(c2))
        paired.add(i); paired.add(j_match)

    # Ensure any small course pre-placed in Slot A (for SN Row 1) also obtained a different-dept Slot B partner
    FOR d IN open_halls.values():
        IF enrol_count(d.slot_a) < 10 AND (d.slot_b IS None OR d.slot_b.department == d.slot_a.department):
            RETURN False
    RETURN True
```
- **Worked Example (`EC-02`):** `9`-student `CSE` course merges into Slot B of an `AIML` hall; `10`-student `CSE` course occupies its own hall without requiring a partner.

---

## ALG-11 — Alternate-Column Seat Assignment

- **Business Rules:** `BR-05`, `BR-06`, `AS-003`–`AS-005`, `AS-009`, `AS-024`.
- **Inputs:** `session`, `hall_allocations`, `registry`.
- **Outputs:** Sorted `tuple[SeatAssignment, ...]`.
- **Preconditions:** Valid `HallAllocation`s for `session`.
- **Postconditions:** Slot A in odd columns (`1, 3, 5...`), Slot B in even columns (`2, 4, 6...`); `seat_number = (row - 1) * cols + col`; alphabetical `register_number` order within SN Row-1 and Regular subsets.
- **Complexity:** Time $\mathcal{O}(N_{\text{sess}} \log N_{\text{sess}} + \sum R \cdot \text{Cols})$; Space $\mathcal{O}(N_{\text{sess}})$.
- **Pseudocode:**
```text
FUNCTION assign_seats(session, hall_allocations, registry) -> tuple[SeatAssignment, ...]:
    sn_q  <- {c: deque(sorted_sn_students(c, registry))  FOR c IN session_courses(hall_allocations)}
    reg_q <- {c: deque(sorted_reg_students(c, registry)) FOR c IN session_courses(hall_allocations)}
    seats <- []
    FOR alloc IN hall_allocations:
        hall <- registry.halls[alloc.hall_id]
        odd_cols  <- [k FOR k IN 1..hall.columns IF k % 2 == 1]
        even_cols <- [k FOR k IN 1..hall.columns IF k % 2 == 0]
        seats.extend(fill_column_set(session, hall, alloc.slot_a_course, alloc.count_a, odd_cols, sn_q, reg_q))
        IF alloc.slot_b_course IS NOT None:
            seats.extend(fill_column_set(session, hall, alloc.slot_b_course, alloc.count_b, even_cols, sn_q, reg_q))
    RETURN tuple(sorted(seats, key = LAMBDA s: (s.hall_id, s.row, s.column)))

FUNCTION fill_column_set(session, hall, course_code, count, cols, sn_q, reg_q):
    coords <- [(r, c) FOR r IN 1..hall.rows FOR c IN cols]
    out <- []; idx <- 0
    WHILE sn_q[course_code] AND idx < count AND coords[idx][0] == 1 AND hall.floor == 0:
        stu <- sn_q[course_code].popleft(); r, c <- coords[idx]; idx <- idx + 1
        out.append(SeatAssignment(session.session_id, hall.hall_id, r, c, (r-1)*hall.columns+c, f"R{r:02d}C{c:02d}", course_code, stu.register_number, True))
    WHILE len(out) < count:
        stu <- reg_q[course_code].popleft(); r, c <- coords[idx]; idx <- idx + 1
        out.append(SeatAssignment(session.session_id, hall.hall_id, r, c, (r-1)*hall.columns+c, f"R{r:02d}C{c:02d}", course_code, stu.register_number, False))
    RETURN out
```
- **Worked Example:** `7`-column hall -> Odd Set A = `{1, 3, 5, 7}` (`4` cols/row), Even Set B = `{2, 4, 6}` (`3` cols/row).

---

## ALG-12 — Special-Needs Seating and Extra-Time Allocation

- **Business Rules:** `BR-06`, `EC-05`, `AS-009`, `AS-010`, `AS-017`.
- **Inputs:** `session: ExamSession`, `duration_hours: int`, `hall_seats: sequence[SeatAssignment]`.
- **Outputs:** `(has_special_needs: bool, effective_window: TimeInterval)`.
- **Preconditions:** `is_special_needs` seats verified at `floor == 0, row == 1`.
- **Postconditions:** Adds `+20` minutes iff `has_special_needs == True`.
- **Complexity:** Time $\mathcal{O}(|hall\_seats|)$; Space $\mathcal{O}(1)$.
- **Pseudocode:**
```text
FUNCTION compute_hall_effective_window(session, duration_hours, hall_seats) -> (bool, TimeInterval):
    has_sn <- ANY(s.is_special_needs FOR s IN hall_seats)
    start  <- 570 IF session.slot == FN ELSE 840
    end    <- start + duration_hours * 60 + (20 IF has_sn ELSE 0)
    RETURN (has_sn, TimeInterval(start, end))
```
- **Worked Example (`EC-05`):** `AN` (`14:00`), `3h`, `has_sn=True` -> `14:00–17:20` (`TimeInterval(840, 1040)`).

---

## ALG-13 — Invigilator Eligibility and Workload Balancing

- **Business Rules:** `BR-07`, `BR-08`, `EC-04`, `EC-05`, `AS-018`–`AS-022`.
- **Inputs:** `session`, `hall_allocations`, `workload: WorkloadTracker`, `registry`.
- **Outputs:** `(hall_assignments, shortage_violations, used_in_session)`.
- **Tie-Breaking:** Halls in ascending `hall_id`; invigilators sorted by `(workload.total_assigned(v), v.department, v.invigilator_id)`.
- **Failure Cases:** Exhausted eligible pool -> slot marked `UNSTAFFED` + `HALL_UNSTAFFED` violation (`BR-08`).
- **Complexity:** Time $\mathcal{O}(H_{\text{slots}} \cdot V \log V)$; Space $\mathcal{O}(V)$.
- **Pseudocode:**
```text
FUNCTION assign_hall_invigilators(session, hall_allocations, workload, registry):
    out <- []; viols <- []; used <- set()
    FOR alloc IN sorted(hall_allocations, key = LAMBDA a: a.hall_id):
        n_stu <- sum(alloc.course_student_counts.values())
        req   <- max(1, (n_stu + 29) // 30)
        banned_depts <- {registry.courses[c].department FOR c IN alloc.course_student_counts}
        FOR slot_idx FROM 1 TO req:
            pool <- [
                v FOR v IN registry.invigilators.values()
                IF v.invigilator_id NOT IN used
                AND v.department NOT IN banned_depts
                AND session.exam_date NOT IN v.unavailable_dates
                AND NOT overlaps_external_duty(v, session.exam_date, alloc.effective_window)
                AND workload.daily_count(v.invigilator_id, session.exam_date) < 2
                AND workload.weekly_count(v.invigilator_id, session.iso_week_key) < v.max_weekly_sessions
            ]
            IF pool IS NOT EMPTY:
                pool.sort(key = LAMBDA v: (workload.total_assigned(v.invigilator_id), v.department, v.invigilator_id))
                v <- pool[0]; used.add(v.invigilator_id); workload.record(v.invigilator_id, session)
                out.append(make_assigned_hall_staff(session, alloc, slot_idx, v))
            ELSE:
                out.append(make_unstaffed_hall_staff(session, alloc, slot_idx))
                viols.append(make_unstaffed_violation("HALL_UNSTAFFED", session, alloc.hall_id, slot_idx))
    RETURN out, viols, used
```
- **Worked Example:** `30` students -> `1` invigilator; `31` students -> `2` invigilators (`(31+29)//30 = 2`). Merged `CSE`+`ECE` hall excludes both `CSE` and `ECE` staff (`EC-04`).

---

## ALG-14 — Building Chief Assignment

- **Business Rules:** `BR-07`, `BR-08`, `AS-019`, `AS-020`.
- **Inputs:** `session`, `hall_allocations`, `used_in_session`, `workload`, `registry`.
- **Outputs:** `(chief_assignments, chief_violations)`.
- **Preconditions:** `ALG-13` executed for `session`.
- **Postconditions:** `1` Chief per active building (sorted by `building_code`), counting toward daily/weekly/cumulative workload (`AS-020`), or `BUILDING_CHIEF_UNSTAFFED`.
- **Complexity:** Time $\mathcal{O}(B \cdot V \log V)$; Space $\mathcal{O}(B + V)$.
- **Pseudocode:**
```text
FUNCTION assign_building_chiefs(session, hall_allocations, used, workload, registry):
    chiefs <- []; viols <- []
    FOR bldg_code, bldg_halls IN group_active_buildings_sorted(hall_allocations):
        win <- TimeInterval(min_start(bldg_halls), max_end(bldg_halls))
        pool <- [
            v FOR v IN registry.invigilators.values()
            IF v.invigilator_id NOT IN used
            AND session.exam_date NOT IN v.unavailable_dates
            AND NOT overlaps_external_duty(v, session.exam_date, win)
            AND workload.daily_count(v.invigilator_id, session.exam_date) < 2
            AND workload.weekly_count(v.invigilator_id, session.iso_week_key) < v.max_weekly_sessions
        ]
        IF pool IS NOT EMPTY:
            pool.sort(key = LAMBDA v: (workload.total_assigned(v.invigilator_id), v.department, v.invigilator_id))
            v <- pool[0]; used.add(v.invigilator_id); workload.record(v.invigilator_id, session)
            chiefs.append(make_assigned_chief(session, bldg_code, v, win))
        ELSE:
            chiefs.append(make_unstaffed_chief(session, bldg_code, win))
            viols.append(make_unstaffed_violation("BUILDING_CHIEF_UNSTAFFED", session, bldg_code, 1))
    RETURN chiefs, viols
```
- **Worked Example:** Building `BLOCK-2` has 0 occupied halls in `2026-12-03_AN` -> inactive building, `0` Chiefs assigned. `BLOCK-1` has 3 occupied halls -> `1` Chief assigned.

---

## ALG-15 — Course Postponement (`BR-09`)

- **Business Rules:** `BR-09`, `EC-06`, `AS-026`, `AS-027`, `AS-031`.
- **Inputs:** `cmd: ChangeCommand`, `state: ScheduleState`, `conflict_graph`, `cohorts_map`.
- **Outputs:** `(ScheduleState, ChangeResult)`.
- **Preconditions:** `cmd.course_code` scheduled in `S_orig`.
- **Postconditions:** Moves course to earliest `S_dest > S_orig` satisfying hard rules (+ gap with soft fallback); regenerates **only** `{S_orig, S_dest}`; rolls back cleanly if infeasible.
- **Complexity:** Time $\mathcal{O}(M \cdot H \log H + V \log V)$; Space $\mathcal{O}(M + H + V)$.
- **Pseudocode:**
```text
FUNCTION postpone_course(cmd, state, conflict_graph, cohorts_map) -> (ScheduleState, ChangeResult):
    IF cmd.course_code NOT IN state.exam_assignments:
        RETURN (state, reject(cmd, REJECTED_INVALID_COMMAND, "Course not scheduled"))
    cand <- ALG_19_begin_candidate(state)
    s_orig_id <- cand.exam_assignments[cmd.course_code].session_id
    s_orig    <- cand.registry.sessions_by_id[s_orig_id]
    course    <- cand.registry.courses[cmd.course_code]

    cand.remove_course(cmd.course_code, s_orig_id)
    IF NOT ALG_08_check_and_pack_session(s_orig, cand.session_courses[s_orig_id], cand.registry, cand.closed_hall_sessions).is_feasible:
        RETURN ALG_19_rollback(state, cmd, REJECTED_NO_FEASIBLE_SESSION, "Source session orphaned <10 merge partner")

    later <- [s FOR s IN cand.registry.sessions IF s.session_index > s_orig.session_index AND (cmd.min_target_date IS None OR s.exam_date >= cmd.min_target_date)]
    s_dest <- find_earliest_two_pass(course, later, cand, conflict_graph, cohorts_map)
    IF s_dest IS None:
        RETURN ALG_19_rollback(state, cmd, REJECTED_NO_FEASIBLE_SESSION, "No feasible later session")

    cand.place_course(course, s_dest)
    recompute_affected_sessions(cand, {s_orig_id, s_dest.session_id})
    RETURN ALG_19_validate_and_commit(state, cand, cmd, {s_orig_id, s_dest.session_id}, displaced=((course.course_code, s_orig_id, s_dest.session_id),))
```
- **Worked Example:** Course on `Day 12 AN` (final session) receives `POSTPONE_COURSE` -> `later` is empty -> returns `(state, REJECTED_NO_FEASIBLE_SESSION)` with zero mutations.

---

## ALG-16 — Hall Unavailability Recovery (`BR-10`)

- **Business Rules:** `BR-10`, `AS-025`, `AS-027`, `AS-031`.
- **Inputs:** `cmd: ChangeCommand`, `state: ScheduleState`, `conflict_graph`, `cohorts_map`.
- **Outputs:** `(ScheduleState, ChangeResult)`.
- **Preconditions:** Valid `hall_id` and `target_session_ids`.
- **Postconditions:** Reallocates displaced students into next largest hall in `S_orig`; if insufficient capacity, displaces `S_orig`'s smallest course `(enrolment_count, credits, course_code)` to next free later session `S_dest` and flags `COURSE_DISPLACED_BY_HALL_CLOSURE`.
- **Complexity:** Time $\mathcal{O}(|T| \cdot M \cdot H \log H)$; Space $\mathcal{O}(M + H + V)$.
- **Pseudocode:**
```text
FUNCTION recover_hall_unavailability(cmd, state, conflict_graph, cohorts_map) -> (ScheduleState, ChangeResult):
    cand <- ALG_19_begin_candidate(state)
    affected <- set(); displaced <- []
    FOR s_id IN cmd.target_session_ids:
        cand.closed_hall_sessions.add((s_id, cmd.hall_id))
        IF NOT was_hall_occupied(state, s_id, cmd.hall_id): CONTINUE
        affected.add(s_id)
        s_orig <- cand.registry.sessions_by_id[s_id]

        WHILE NOT ALG_08_check_and_pack_session(s_orig, cand.session_courses[s_id], cand.registry, cand.closed_hall_sessions).is_feasible:
            IF cand.session_courses[s_id] IS EMPTY:
                RETURN ALG_19_rollback(state, cmd, REJECTED_HALL_CLOSURE_INFEASIBLE, "No courses left to displace")
            smallest <- min(cand.session_courses[s_id], key = LAMBDA c: (enrol_count(c), credits(c), c))
            cand.remove_course(smallest, s_id)
            later <- [s FOR s IN cand.registry.sessions IF s.session_index > s_orig.session_index]
            s_dest <- find_earliest_two_pass(cand.registry.courses[smallest], later, cand, conflict_graph, cohorts_map)
            IF s_dest IS None:
                RETURN ALG_19_rollback(state, cmd, REJECTED_HALL_CLOSURE_INFEASIBLE, f"No free session for {smallest}")
            cand.place_course(cand.registry.courses[smallest], s_dest)
            affected.add(s_dest.session_id)
            displaced.append((smallest, s_id, s_dest.session_id))
            cand.record_displacement_violation(smallest, cmd.hall_id, s_id, s_dest.session_id, cmd.command_id)

    IF affected IS NOT EMPTY:
        recompute_affected_sessions(cand, affected)
    RETURN ALG_19_validate_and_commit(state, cand, cmd, affected, displaced=tuple(displaced))
```
- **Worked Example:** Closing unoccupied `BLK2-102` marks it closed with `affected = ∅`. Closing occupied `BLK1-G01` shifts students to `BLK1-101` in the same session if capacity allows, else moves smallest course `ECE609` (`8` students) to the next free session.

---

## ALG-17 — Late Student Registration (`BR-11`)

- **Business Rules:** `BR-11`, `BR-01`, `BR-04`–`BR-08`, `AS-028`–`AS-030`.
- **Inputs:** `cmd: ChangeCommand`, `state: ScheduleState`.
- **Outputs:** `(ScheduleState, ChangeResult)`.
- **Tie-Breaking:** Conflicting course pair sorted ascending `(c1, c2)`; eligible hall selected by `(-free_legal_seats, hall_id)`.
- **Complexity:** Time $\mathcal{O}(k^2 + k \cdot (H + N_{\text{hall}} \log N_{\text{hall}} + V \log V))$; Space $\mathcal{O}(k + N_{\text{hall}})$.
- **Pseudocode:**
```text
FUNCTION register_late_student(cmd, state) -> (ScheduleState, ChangeResult):
    cand <- ALG_19_begin_candidate(state)
    stu <- cand.upsert_late_student(cmd.student_payload, cmd.late_enrolments)
    enrols <- cand.registry.enrolments_by_student[stu.register_number]

    # 1. Atomic clash check across all student courses (BR-01)
    FOR i FROM 0 TO len(enrols) - 1:
        FOR j FROM i + 1 TO len(enrols) - 1:
            e1, e2 <- enrols[i], enrols[j]
            s1, s2 <- cand.session_of(e1.course_code), cand.session_of(e2.course_code)
            same_day_clash <- (s1.exam_date == s2.exam_date) AND NOT (stu.backlog_consent AND (e1.is_backlog OR e2.is_backlog))
            IF s1.session_id == s2.session_id OR same_day_clash:
                pair <- tuple(sorted([e1.course_code, e2.course_code]))
                RETURN ALG_19_rollback(state, cmd, REJECTED_CLASH, "Student exam clash", conflicting_courses=pair)

    # 2. Seat in eligible hall with most free legal seats per course
    affected <- set()
    FOR enrol IN sorted(cmd.late_enrolments, key = LAMBDA e: e.course_code):
        sess <- cand.session_of(enrol.course_code)
        IF NOT has_90_percent_session_headroom(cand, sess, delta=1):
            RETURN ALG_19_rollback(state, cmd, REJECTED_SESSION_CAPACITY, "90% session limit reached")
        hall_choice <- pick_hall_most_free_seats(cand, sess, enrol.course_code, stu.special_needs)
        IF hall_choice IS None:
            status <- REJECTED_ACCESSIBILITY_CAPACITY IF stu.special_needs ELSE REJECTED_HALL_CAPACITY
            RETURN ALG_19_rollback(state, cmd, status, "No eligible hall seat")
        affected.add(sess.session_id)
        re_seat_single_course_in_hall(cand, sess, hall_choice, enrol.course_code)
        update_delta_invigilation(cand, sess, hall_choice.hall_id)

    RETURN ALG_19_validate_and_commit(state, cand, cmd, affected)
```
- **Worked Example:** Course `CS301` occupies `H1` (`5` free odd seats) and `H2` (`12` free odd seats). Late student `2462990` is placed into `H2` (`12 > 5` free seats).

---

## ALG-18 — Independent Schedule Validation

- **Business Rules:** Audits all `BR-01`–`BR-12` (`CN-07`–`CN-28`).
- **Inputs:** `state: ScheduleState`.
- **Outputs:** `ValidationReport(is_hard_valid: bool, errors: tuple[AuditError, ...])`.
- **Preconditions:** None (zero shared state with constructive engines).
- **Postconditions:** Independently verifies student clashes (`BR-01`), core gaps vs logged `CORE_GAP_SOFT_VIOLATION`s (`BR-02`, `BR-03`), 90% session cap & duration purity (`BR-04`), max 2 courses/hall, non-adjacent columns (`|c1 - c2| != 1`), `< 10` different-department merges (`BR-05`), Row-1 ground-floor SN seating & `+20m` windows (`BR-06`), hall/chief staffing formulas, dept exclusions (`EC-04`), unavailable/external duty overlaps (`EC-05`), daily `<= 2`, ISO weekly `<= max_weekly`, `UNSTAFFED` reporting (`BR-07`, `BR-08`), and supplementary slots (`BR-12`).
- **Complexity:** Time $\mathcal{O}(E + C^2 + M \cdot H \cdot R \cdot \text{Cols} + M \cdot V)$; Space $\mathcal{O}(E + V)$.
- **Pseudocode:**
```text
FUNCTION validate_schedule_independently(state: ScheduleState) -> ValidationReport:
    errs <- []
    audit_student_clashes_br01(state, errs)
    audit_core_gaps_br02_br03(state, errs)
    audit_session_cap_and_durations_br04(state, errs)
    audit_hall_packing_and_merges_br05(state, errs)
    audit_seating_and_accessibility_br06(state, errs)
    audit_invigilation_and_workload_br07_br08(state, errs)
    audit_supplementary_window_br12(state, errs)
    RETURN ValidationReport(len(errs) == 0, tuple(errs))
```
- **Worked Example:** If a bug in an allocation helper accidentally placed a `special_needs` student in `row = 2`, `ALG-18` flags `AUDIT_ERR_BR06_SN_NOT_ROW1` and aborts commit before invalid output can be written.

---

## ALG-19 — Incremental State Updates and Rollback

- **Business Rules:** `FR-05`, `BR-09`–`BR-11`, `NFR-03`.
- **Inputs:** `prev_state`, `cand_state`, `cmd`, `affected_sessions`.
- **Outputs:** `(ScheduleState, ChangeResult)`.
- **Postconditions:** Verifies SHA-256 session digest equality on all `s not in affected_sessions` AND `ALG-18` full-state hard validity; commits atomically or rolls back without side effects.
- **Complexity:** Time $\mathcal{O}(E + M \cdot H \cdot R \cdot \text{Cols})$; Space $\mathcal{O}(M)$ copy-on-write references.
- **Pseudocode:**
```text
FUNCTION validate_and_commit(prev_state, cand_state, cmd, affected, displaced=()) -> (ScheduleState, ChangeResult):
    FOR s IN prev_state.registry.sessions:
        IF s.session_id NOT IN affected:
            ASSERT session_sha256(prev_state, s.session_id) == session_sha256(cand_state, s.session_id)
    report <- ALG_18_validate_schedule_independently(cand_state)
    IF NOT report.is_hard_valid:
        RETURN rollback(prev_state, cmd, REJECTED_NO_FEASIBLE_SESSION, report.first_error())
    res <- ChangeResult(cmd.command_id, cmd.change_type, APPLIED, tuple(sorted(affected)), (), displaced, True, "OK")
    RETURN (cand_state.with_committed_result(prev_state.state_version + 1, res), res)
```
- **Worked Example:** `POSTPONE_COURSE` mutates `2` of `20` sessions -> `18` unaffected session digests match bit-for-bit (`unaffected_sessions_verified = True`).

---

## ALG-20 — Deterministic Report Generation

- **Business Rules:** `FR-06`, `NFR-01`, `AS-033`.
- **Inputs:** `ScheduleState`, `output_dir: Path`.
- **Outputs:** 8 deterministic UTF-8 LF files (`timetable.csv`, `hall_plan.csv`, `seat_assignments.csv`, `seat_maps.txt`, `invigilation_roster.csv`, `violations.json`, `schedule_state.json`, `change_results.json`).
- **Complexity:** Time $\mathcal{O}(E \log E + M \cdot H \cdot R \cdot \text{Cols})$; Space $\mathcal{O}(E)$.
- **Pseudocode:**
```text
FUNCTION generate_all_reports(state: ScheduleState, out_dir: Path) -> None:
    mkdir_p(out_dir)
    write_csv(out_dir / "timetable.csv",           sorted_timetable_rows(state))
    write_csv(out_dir / "hall_plan.csv",           sorted_hall_plan_rows(state))
    write_csv(out_dir / "seat_assignments.csv",    sorted_seat_rows(state))
    write_txt(out_dir / "seat_maps.txt",           render_sorted_seat_maps(state))
    write_csv(out_dir / "invigilation_roster.csv", sorted_invigilation_rows(state))
    write_json(out_dir / "violations.json",        build_sorted_violations_doc(state))
    write_json(out_dir / "change_results.json",    build_change_results_doc(state))
    write_json(out_dir / "schedule_state.json",    serialise_canonical_state(state))
```
- **Worked Example:** Running twice with `PYTHONHASHSEED=1` and `PYTHONHASHSEED=999` produces identical SHA-256 checksums across all 8 files.
