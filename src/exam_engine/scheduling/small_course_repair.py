"""Small-Course Deferral and Repair Engine (ALG-10).

Covers:
  - BR-05 / CN-16: Mandatory cross-department small-course merging (1 <= enrolment < 10)
  - BR-04 / CN-11 / CN-12: Session aggregate 90% capacity and duration homogeneity
  - BR-01 / CN-07 / CN-08: Student conflict clash prevention (session and day)
  - BR-12 / CN-28 / EC-08: Supplementary window and slot constraints
  - AS-006: Small-course merging when no compatible partner exists in initial session
  - AS-007: Multiple small courses pairing and co-scheduling across departments
  - AS-032: Deterministic repair when greedy placement encounters spatial constraints
  - EC-02: Boundary check for small courses (enrolment 9 vs 10; < 10 threshold)
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import (
    Any,
)

from exam_engine.scheduling.conflict_graph import (
    ConflictGraph,
    build_conflict_graph,
)
from exam_engine.scheduling.gap_validator import (
    build_cohorts_map,
    check_core_gap,
)
from exam_engine.scheduling.scheduler import (
    ExamAssignment,
    ExamSessionProtocol,
    ProblemRegistryProtocol,
    Violation,
    ViolationCategory,
    _evaluate_packability,
    get_course_enrolment_count,
    is_hard_feasible,
)
from exam_engine.scheduling.session_generator import generate_sessions
from exam_engine.scheduling.supplementary import is_supplementary_eligible

# Boundary constants for small courses (BR-05, EC-02)
MIN_SMALL_COURSE_ENROLMENT: int = 1
MAX_SMALL_COURSE_ENROLMENT: int = 9


def is_small_course_eligible(course_or_enrolment: Any, registry: Any = None) -> bool:
    """Check whether a course or enrolment count qualifies for small-course deferral and repair.

    Under BR-05, EC-02, and AS-006, a course qualifies as a small course if and only if
    its total enrolled student count is strictly fewer than 10 and at least 1
    (i.e. 1 <= count <= 9). Courses with 0 students or >= 10 students are not eligible.

    Parameters
    ----------
    course_or_enrolment:
        Course entity, course code string, or raw integer enrolment count.
    registry:
        Optional ProblemRegistry used to look up enrolments if an entity/code is provided.

    Returns
    -------
    bool
        True if 1 <= count <= 9, False otherwise.
    """
    if isinstance(course_or_enrolment, int):
        cnt = course_or_enrolment
    else:
        c_code = getattr(course_or_enrolment, "course_code", str(course_or_enrolment))
        cnt = get_course_enrolment_count(c_code, registry)
    return MIN_SMALL_COURSE_ENROLMENT <= cnt <= MAX_SMALL_COURSE_ENROLMENT


@dataclass(frozen=True)
class SmallCourseRepairResult:
    """Outcome container for the ALG-10 small-course repair process.

    Attributes
    ----------
    repaired_courses:
        Tuple of small course objects successfully scheduled during repair.
    unrepaired_courses:
        Tuple of small course objects that could not be repaired and remain unplaced.
    new_assignments:
        Mapping of course_code -> ExamAssignment for courses placed during repair.
    new_violations:
        Tuple of newly generated violations (e.g. UNSCHEDULED_COURSE or soft gap violations).
    """

    repaired_courses: tuple[Any, ...]
    unrepaired_courses: tuple[Any, ...]
    new_assignments: dict[str, ExamAssignment]
    new_violations: tuple[Violation, ...]

    def __iter__(self) -> Any:
        """Allow unpacking as (repaired_courses, unrepaired_courses, new_violations)."""
        return iter((self.repaired_courses, self.unrepaired_courses, self.new_violations))


def repair_deferred_courses(
    deferred_courses: Sequence[Any],
    assignments: dict[str, ExamAssignment],
    session_courses: dict[str, list[str]],
    violations: list[Violation],
    registry: ProblemRegistryProtocol,
    conflict_graph: ConflictGraph | None = None,
    cohorts_map: dict[str, frozenset[tuple[str, int]]] | None = None,
    sessions: Sequence[ExamSessionProtocol] | None = None,
    sessions_by_date: Mapping[date, Sequence[ExamSessionProtocol]] | None = None,
    *,
    packability_checker: Callable[..., Any] | None = None,
    closed_halls: frozenset[tuple[str, str]] = frozenset(),
) -> SmallCourseRepairResult:
    """Repair deferred small courses by deterministic relocation or pair co-scheduling (ALG-10).

    This function implements the repair mechanism for small courses (1 <= enrolment < 10)
    that could not be scheduled during initial greedy passes of ALG-06 (AS-006, AS-007, AS-032).

    Processing Workflow
    -------------------
    1. Validate eligibility: Any course with enrolment < 1 or >= 10 is strictly ineligible;
       raises ValueError to prevent improper invocation.
    2. Deterministic sort: Eligible small courses are ordered strictly by
       `(-enrolment_count, -credits, course_code)` (BR-03, AS-007).
    3. Pass 1 (Relocation into existing compatible sessions):
       Each deferred course sequentially scans chronologically ordered sessions to find
       the earliest session that already contains a compatible merge partner
       (different department, identical duration) satisfying all hard constraints.
    4. Pass 2 (Cross-department pair co-scheduling):
       Remaining unplaced small courses are paired with each other (different department,
       identical duration, no student conflict) and co-scheduled into the earliest session
       capable of hosting both courses.
    5. Pass 3 (Diagnostic emission):
       Any small course that remains infeasible across all sessions is assigned an
       `UNSCHEDULED_COURSE` violation (rule CN-16 / CN-28).

    Parameters
    ----------
    deferred_courses:
        Collection of courses deferred from ALG-06.
    assignments:
        Active assignment dictionary mapping course_code -> ExamAssignment (updated in place).
    session_courses:
        Active session assignment dictionary mapping session_id -> list[course_code] (updated in place).
    violations:
        Active list of violations (appended to in place).
    registry:
        Problem registry containing courses, students, halls, and sessions.
    conflict_graph:
        Precomputed ConflictGraph (computed if None).
    cohorts_map:
        Precomputed cohorts mapping (computed if None).
    sessions:
        Ordered sequence of ExamSession objects (derived from registry if None).
    sessions_by_date:
        Mapping of date -> sessions on that date (derived from sessions if None).
    packability_checker:
        Optional ALG-08 packability checker implementation.
    closed_halls:
        Optional set of (session_id, hall_id) pairs closed under BR-10.

    Returns
    -------
    SmallCourseRepairResult
        Container detailing repaired courses, unrepaired courses, and new diagnostics.
    """
    if not deferred_courses:
        return SmallCourseRepairResult(
            repaired_courses=(),
            unrepaired_courses=(),
            new_assignments={},
            new_violations=(),
        )

    # 1. Validate eligibility and bounds (EC-02)
    # Courses with enrolment < 1 or >= 10 must not enter small-course repair.
    for c in deferred_courses:
        c_code = getattr(c, "course_code", str(c))
        enrol = get_course_enrolment_count(c_code, registry)
        if not (MIN_SMALL_COURSE_ENROLMENT <= enrol <= MAX_SMALL_COURSE_ENROLMENT):
            raise ValueError(
                f"Course {c_code} with enrolment {enrol} is not eligible for small-course "
                f"repair (must be between {MIN_SMALL_COURSE_ENROLMENT} and {MAX_SMALL_COURSE_ENROLMENT})."
            )

    # 2. Resolve sessions and supporting indices
    if sessions is None:
        raw_sessions = getattr(registry, "sessions", None)
        if not raw_sessions and hasattr(registry, "exam_window"):
            raw_sessions = generate_sessions(registry.exam_window)
        if isinstance(raw_sessions, Mapping):
            sessions = tuple(raw_sessions.values())
        elif raw_sessions is not None:
            sessions = tuple(raw_sessions)
        else:
            sessions = ()

    sessions = tuple(
        sorted(
            sessions,
            key=lambda s: (
                getattr(s, "session_index", 0),
                getattr(s, "exam_date", date.min),
            ),
        )
    )

    if sessions_by_date is None:
        s_by_date: dict[date, list[ExamSessionProtocol]] = {}
        for s in sessions:
            s_by_date.setdefault(s.exam_date, []).append(s)
        sessions_by_date = s_by_date

    if conflict_graph is None:
        conflict_graph = build_conflict_graph(registry)

    if cohorts_map is None:
        cohorts_map = build_cohorts_map(registry)

    # 3. Deterministic ordering of deferred courses (-enrolment, -credits, course_code)
    sorted_deferred = sorted(
        deferred_courses,
        key=lambda c: (
            -get_course_enrolment_count(getattr(c, "course_code", str(c)), registry),
            -getattr(c, "credits", 3),
            getattr(c, "course_code", ""),
        ),
    )

    unplaced: list[Any] = list(sorted_deferred)
    repaired_courses: list[Any] = []
    new_assignments: dict[str, ExamAssignment] = {}
    new_violations: list[Violation] = []

    # -----------------------------------------------------------------------
    # PASS 1: Single-course placement into session with existing partner
    # -----------------------------------------------------------------------
    for c1 in list(unplaced):
        c1_code = getattr(c1, "course_code", str(c1))
        if c1_code in assignments:
            unplaced.remove(c1)
            continue

        c1_dept = getattr(c1, "department", "")
        c1_dur = getattr(c1, "duration_hours", 3)

        for sess in sessions:
            # Check hard feasibility for c1
            if not is_hard_feasible(
                c1,
                sess,
                session_courses,
                registry,
                conflict_graph,
                sessions_by_date,
                packability_checker,
                closed_halls,
            ):
                continue

            current_codes = session_courses.get(sess.session_id, [])

            # When packability_checker is not supplied, enforce BR-05 partner presence
            if packability_checker is None:
                has_partner = False
                for existing_code in current_codes:
                    reg_courses = getattr(registry, "courses", {})
                    existing_c = (
                        reg_courses.get(existing_code)
                        if isinstance(reg_courses, Mapping)
                        else None
                    )
                    if existing_c is not None:
                        ex_dept = getattr(existing_c, "department", "")
                        ex_dur = getattr(existing_c, "duration_hours", 3)
                        if ex_dept != c1_dept and ex_dur == c1_dur:
                            has_partner = True
                            break
                if not has_partner:
                    continue

            # Core gap check: soft fallback allowed if needed (consistent with Pass 2)
            gap_ok, violators = check_core_gap(
                c1, sess, assignments, cohorts_map, registry
            )
            is_fallback = not gap_ok

            assignment = ExamAssignment(
                course_code=c1_code,
                session_id=sess.session_id,
                used_gap_soft_fallback=is_fallback,
            )
            assignments[c1_code] = assignment
            session_courses.setdefault(sess.session_id, []).append(c1_code)
            repaired_courses.append(c1)
            new_assignments[c1_code] = assignment

            if is_fallback:
                viol_id = f"VIOL-{len(violations) + 1:04d}"
                v = Violation(
                    violation_id=viol_id,
                    category=ViolationCategory.SOFT_VIOLATION,
                    code="CORE_GAP_SOFT_VIOLATION",
                    rule_id="BR-02",
                    session_id=sess.session_id,
                    entity_ids=(c1_code, *violators),
                    message=(
                        f"Repaired small course {c1_code} placed in session {sess.session_id} "
                        f"with < 2 calendar day gap against: {', '.join(violators)}."
                    ),
                )
                violations.append(v)
                new_violations.append(v)

            unplaced.remove(c1)
            break

    # -----------------------------------------------------------------------
    # PASS 2: Co-scheduling pairs of remaining unplaced small courses
    # -----------------------------------------------------------------------
    i = 0
    while i < len(unplaced):
        c1 = unplaced[i]
        c1_code = getattr(c1, "course_code", str(c1))
        if c1_code in assignments:
            i += 1
            continue

        c1_dept = getattr(c1, "department", "")
        c1_dur = getattr(c1, "duration_hours", 3)

        partner_found = False
        for j in range(i + 1, len(unplaced)):
            c2 = unplaced[j]
            c2_code = getattr(c2, "course_code", str(c2))
            if c2_code in assignments:
                continue

            c2_dept = getattr(c2, "department", "")
            c2_dur = getattr(c2, "duration_hours", 3)

            # Check cross-department and duration homogeneity (BR-04, BR-05, AS-007)
            if c1_dept == c2_dept:
                continue
            if c1_dur != c2_dur:
                continue

            # Student clash between c1 and c2 (BR-01, CN-07)
            if c2_code in conflict_graph.same_session_forbidden.get(c1_code, frozenset()):
                continue

            # Scan sessions chronologically for earliest session accommodating both
            for sess in sessions:
                current_in_session = session_courses.get(sess.session_id, [])

                # Supplementary window and slot constraints for both
                if not is_supplementary_eligible(c1, sess, registry):
                    continue
                if not is_supplementary_eligible(c2, sess, registry):
                    continue

                # Same-session student clash with existing courses
                s_forbid_c1 = conflict_graph.same_session_forbidden.get(c1_code, frozenset())
                s_forbid_c2 = conflict_graph.same_session_forbidden.get(c2_code, frozenset())
                if any(ec in s_forbid_c1 or ec in s_forbid_c2 for ec in current_in_session):
                    continue

                # Same-day clash against sibling sessions on the same exam date
                day_forbid_c1 = conflict_graph.same_day_forbidden.get(c1_code, frozenset())
                day_forbid_c2 = conflict_graph.same_day_forbidden.get(c2_code, frozenset())
                clash_day = False
                for sibling in sessions_by_date.get(sess.exam_date, []):
                    if sibling.session_id != sess.session_id:
                        for oc in session_courses.get(sibling.session_id, []):
                            if oc in day_forbid_c1 or oc in day_forbid_c2:
                                clash_day = True
                                break
                    if clash_day:
                        break
                if clash_day:
                    continue

                # Capacity check for current + c1 + c2 (BR-04, CN-11, AS-001)
                halls = getattr(registry, "halls", None)
                if halls:
                    avail_halls = [
                        h
                        for h in halls.values()
                        if (sess.session_id, getattr(h, "hall_id", "")) not in closed_halls
                    ]
                    if avail_halls:
                        total_cap = sum(getattr(h, "capacity", 0) for h in avail_halls)
                        cap_90 = (90 * total_cap) // 100
                        current_stu = sum(
                            get_course_enrolment_count(c, registry)
                            for c in current_in_session
                        )
                        cand_stu = (
                            get_course_enrolment_count(c1_code, registry)
                            + get_course_enrolment_count(c2_code, registry)
                        )
                        if current_stu + cand_stu > cap_90:
                            continue
                    else:
                        continue

                # Packability check if checker provided (ALG-08)
                if packability_checker is not None:
                    proposed_courses = list(current_in_session) + [c1_code, c2_code]
                    if not _evaluate_packability(
                        packability_checker, sess, proposed_courses, registry, closed_halls
                    ):
                        continue

                # Both courses are feasible in sess!
                gap1_ok, v1 = check_core_gap(c1, sess, assignments, cohorts_map, registry)
                gap2_ok, v2 = check_core_gap(c2, sess, assignments, cohorts_map, registry)

                a1 = ExamAssignment(
                    c1_code, sess.session_id, used_gap_soft_fallback=not gap1_ok
                )
                a2 = ExamAssignment(
                    c2_code, sess.session_id, used_gap_soft_fallback=not gap2_ok
                )

                assignments[c1_code] = a1
                assignments[c2_code] = a2
                session_courses.setdefault(sess.session_id, []).extend([c1_code, c2_code])

                repaired_courses.extend([c1, c2])
                new_assignments[c1_code] = a1
                new_assignments[c2_code] = a2

                if not gap1_ok:
                    viol_id = f"VIOL-{len(violations) + 1:04d}"
                    v = Violation(
                        violation_id=viol_id,
                        category=ViolationCategory.SOFT_VIOLATION,
                        code="CORE_GAP_SOFT_VIOLATION",
                        rule_id="BR-02",
                        session_id=sess.session_id,
                        entity_ids=(c1_code, *v1),
                        message=f"Repaired small course {c1_code} placed with < 2 day gap.",
                    )
                    violations.append(v)
                    new_violations.append(v)

                if not gap2_ok:
                    viol_id = f"VIOL-{len(violations) + 1:04d}"
                    v = Violation(
                        violation_id=viol_id,
                        category=ViolationCategory.SOFT_VIOLATION,
                        code="CORE_GAP_SOFT_VIOLATION",
                        rule_id="BR-02",
                        session_id=sess.session_id,
                        entity_ids=(c2_code, *v2),
                        message=f"Repaired small course {c2_code} placed with < 2 day gap.",
                    )
                    violations.append(v)
                    new_violations.append(v)

                partner_found = True
                break  # Session loop completed

            if partner_found:
                break  # Partner search loop completed

        i += 1

    # -----------------------------------------------------------------------
    # PASS 3: Generate UNSCHEDULED diagnostics for remaining unplaced courses
    # -----------------------------------------------------------------------
    unrepaired = tuple(c for c in sorted_deferred if getattr(c, "course_code", str(c)) not in assignments)
    for c in unrepaired:
        c_code = getattr(c, "course_code", str(c))
        enrol_cnt = get_course_enrolment_count(c_code, registry)
        is_supp = getattr(c, "is_supplementary", False)
        code = "UNSCHEDULED_SUPPLEMENTARY_NO_SLOT" if is_supp else "UNSCHEDULED_COURSE"
        rule_id = "CN-28" if is_supp else "CN-16"
        viol_id = f"VIOL-{len(violations) + 1:04d}"
        v = Violation(
            violation_id=viol_id,
            category=ViolationCategory.UNSCHEDULED_COURSE,
            code=code,
            rule_id=rule_id,
            session_id=None,
            entity_ids=(c_code,),
            message=(
                f"Small course {c_code} ({enrol_cnt} students) could not be scheduled "
                "in any feasible session with a compatible merge partner."
            ),
        )
        violations.append(v)
        new_violations.append(v)

    return SmallCourseRepairResult(
        repaired_courses=tuple(repaired_courses),
        unrepaired_courses=unrepaired,
        new_assignments=new_assignments,
        new_violations=tuple(new_violations),
    )


# Alias matching docs/09_ALGORITHM_DESIGN.md pseudocode naming
coschedule_deferred_small_courses = repair_deferred_courses
