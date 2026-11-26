"""ALG-06: Earliest-Feasible-Session Timetable Generator.

Implements the deterministic greedy timetable scheduling engine (BR-03, BR-04,
CN-10, CN-11, AS-001, AS-002, AS-006, AS-032).

Integrates:
- ALG-02: Examination session generation (`session_generator`)
- ALG-03: Student conflict graph construction (`conflict_graph`)
- ALG-04: Programme-semester core-course gap validation (`gap_validator`)
- ALG-05: Deterministic course ordering (`ordering`)
- ALG-07: Supplementary examination eligibility (`supplementary`)

Public interface
----------------
generate_timetable(registry, conflict_graph=None, cohorts_map=None, *,
                   packability_checker=None, closed_halls=frozenset())
    Schedules all courses in the problem registry into their earliest
    feasible examination session using the two-pass heuristic (BR-03).

Scheduling passes
-----------------
Pass 1 (Strict):
    For each course in deterministic order (-enrolment, -credits, code):
    find the earliest chronological session that satisfies all hard rules:
    - Supplementary eligibility (BR-12, CN-28, EC-08, ALG-07)
    - Same-session student conflicts (BR-01, CN-07, ALG-03)
    - Same-day student conflicts (BR-01, CN-08, ALG-03)
    - Session 90% aggregate capacity (BR-04, CN-11, AS-001, AS-002)
    - Exact hall packability (ALG-08 / HallPackabilityChecker)
    AND satisfies the minimum two-calendar-day core gap (BR-02, ALG-04).

Pass 2 (Controlled Core-Gap Relaxation):
    If Pass 1 fails to find a slot, search all sessions again enforcing
    ALL hard constraints, but relaxing the core-course gap requirement.
    If a hard-feasible session is found, record a CORE_GAP_SOFT_VIOLATION.

Unsuccessful placement:
    - Courses with 1 <= enrolment < 10 are preserved in deferred_small
      for downstream small-course co-scheduling repair (ALG-10).
    - Courses with enrolment >= 10 (or 0) are recorded as UNSCHEDULED_COURSE.

Complexity
----------
Time:   O(C * M * (C_sess + H log H)) where:
        C = number of courses, M = number of sessions,
        C_sess = courses assigned per session, H = available halls.
Space:  O(C + M * H) auxiliary memory for assignments, occupancy, and violations.

See docs/09_ALGORITHM_DESIGN.md §ALG-06, docs/04_BUSINESS_RULE_REGISTER.md §BR-03,
and docs/06_CONSTRAINT_CATALOGUE.md §CN-10.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import (
    Any,
    Protocol,
    runtime_checkable,
)

from exam_engine.scheduling.conflict_graph import ConflictGraph, build_conflict_graph
from exam_engine.scheduling.gap_validator import build_cohorts_map, check_core_gap
from exam_engine.scheduling.ordering import order_courses
from exam_engine.scheduling.session_generator import generate_sessions
from exam_engine.scheduling.supplementary import (
    get_course_enrolment_count,
    is_supplementary_eligible,
)

# ---------------------------------------------------------------------------
# Enums and Value Objects (matching docs/08_DOMAIN_MODEL.md)
# ---------------------------------------------------------------------------


class ViolationCategory(Enum):
    """Taxonomy of violations from docs/08_DOMAIN_MODEL.md §2."""

    SOFT_VIOLATION = "SOFT_VIOLATION"
    RESOURCE_SHORTAGE = "RESOURCE_SHORTAGE"
    UNSCHEDULED_COURSE = "UNSCHEDULED_COURSE"
    DISPLACEMENT_NOTICE = "DISPLACEMENT_NOTICE"
    REJECTED_CHANGE = "REJECTED_CHANGE"


@dataclass(frozen=True)
class ExamAssignment:
    """Records assignment of one Course to one ExamSession (docs/08_DOMAIN_MODEL.md §4.1)."""

    course_code: str
    session_id: str
    used_gap_soft_fallback: bool = False
    displaced_by_change_id: str | None = None


@dataclass(frozen=True)
class Violation:
    """Structured audit record for violations.json (docs/08_DOMAIN_MODEL.md §4.5)."""

    category: ViolationCategory | str
    code: str
    rule_id: str
    entity_ids: tuple[str, ...]
    message: str
    session_id: str | None = None
    source_command_id: str | None = None
    violation_id: str = ""


@dataclass
class TimetableResult:
    """Container holding the results of generate_timetable (ALG-06).

    Supports unpacking as `(assignments, session_courses, violations)`.
    """

    assignments: dict[str, ExamAssignment]
    session_courses: dict[str, list[str]]
    violations: list[Violation]
    deferred_courses: list[Any] = field(default_factory=list)

    def __iter__(self):
        yield self.assignments
        yield self.session_courses
        yield self.violations

    def __len__(self) -> int:
        return 3


# ---------------------------------------------------------------------------
# Structural Protocol classes (M1 & M3 compatibility layer)
# ---------------------------------------------------------------------------


@runtime_checkable
class CourseProtocol(Protocol):
    """Structural mirror of domain.Course."""

    course_code: str
    credits: int
    is_supplementary: bool


@runtime_checkable
class ExamSessionProtocol(Protocol):
    """Structural mirror of domain.ExamSession."""

    session_id: str
    session_index: int
    exam_date: date
    slot: Any
    is_supplementary_window_date: bool


@runtime_checkable
class HallProtocol(Protocol):
    """Structural mirror of domain.Hall."""

    hall_id: str
    capacity: int


@runtime_checkable
class ProblemRegistryProtocol(Protocol):
    """Structural mirror of domain.ProblemRegistry."""

    courses: Mapping[str, Any]
    students: Mapping[str, Any]
    enrolments_by_student: Mapping[str, Sequence[Any]]
    enrolments_by_course: Mapping[str, Sequence[Any]]


@runtime_checkable
class HallPackabilityChecker(Protocol):
    """Protocol for ALG-08 packability checker (owned by allocation package)."""

    def __call__(
        self,
        session: ExamSessionProtocol,
        course_codes: Sequence[str],
        registry: ProblemRegistryProtocol,
        closed_halls: frozenset[tuple[str, str]] = frozenset(),
    ) -> Any:
        ...


# ---------------------------------------------------------------------------
# Feasibility Evaluation (ALG-06 sub-routine)
# ---------------------------------------------------------------------------


def _evaluate_packability(
    packability_checker: Any,
    session: ExamSessionProtocol,
    proposed_courses: Sequence[str],
    registry: ProblemRegistryProtocol,
    closed_halls: frozenset[tuple[str, str]],
) -> bool:
    """Invoke packability checker and return a boolean feasibility result."""
    if hasattr(packability_checker, "check_and_pack_session"):
        result = packability_checker.check_and_pack_session(
            session, proposed_courses, registry, closed_halls
        )
    else:
        # Callable protocol
        try:
            result = packability_checker(
                session, proposed_courses, registry, closed_halls
            )
        except TypeError:
            # Fallback if checker doesn't accept closed_halls
            result = packability_checker(session, proposed_courses, registry)

    if hasattr(result, "is_feasible"):
        return bool(result.is_feasible)
    return bool(result)


def is_hard_feasible(
    course: CourseProtocol,
    session: ExamSessionProtocol,
    session_courses: Mapping[str, Sequence[str]],
    registry: ProblemRegistryProtocol,
    conflict_graph: ConflictGraph,
    sessions_by_date: Mapping[date, Sequence[ExamSessionProtocol]],
    packability_checker: Callable[..., Any] | None = None,
    closed_halls: frozenset[tuple[str, str]] = frozenset(),
) -> bool:
    """Evaluate all hard scheduling constraints for candidate placement.

    Checks:
    1. Supplementary eligibility (BR-12, CN-28, EC-08, ALG-07).
    2. Same-session student conflicts (BR-01, CN-07, ALG-03).
    3. Same-day student conflicts (BR-01, CN-08, ALG-03).
    4. Session aggregate 90% capacity (BR-04, CN-11, AS-001, AS-002).
    5. Exact hall packability if packability_checker is provided (ALG-08).

    Returns True iff all applicable hard constraints are satisfied.
    """
    # 1. Supplementary eligibility check
    if not is_supplementary_eligible(course, session, registry):
        return False

    c_code = course.course_code
    current_in_session = session_courses.get(session.session_id, [])

    # 2. Same-session conflict check
    session_forbidden = conflict_graph.same_session_forbidden.get(c_code, frozenset())
    for other_c in current_in_session:
        if other_c in session_forbidden:
            return False

    # 3. Same-day conflict check (against sibling sessions on the same date)
    day_forbidden = conflict_graph.same_day_forbidden.get(c_code, frozenset())
    for sibling in sessions_by_date.get(session.exam_date, []):
        if sibling.session_id != session.session_id:
            for other_c in session_courses.get(sibling.session_id, []):
                if other_c in day_forbidden:
                    return False

    # 4. Session aggregate 90% capacity check (BR-04, AS-001, AS-002)
    halls = getattr(registry, "halls", None)
    if halls:
        avail_halls = [
            h
            for h in halls.values()
            if (session.session_id, getattr(h, "hall_id", "")) not in closed_halls
        ]
        if avail_halls:
            total_cap = sum(getattr(h, "capacity", 0) for h in avail_halls)
            cap_90 = (90 * total_cap) // 100
            current_students = sum(
                get_course_enrolment_count(c, registry) for c in current_in_session
            )
            candidate_students = get_course_enrolment_count(c_code, registry)
            if current_students + candidate_students > cap_90:
                return False
        else:
            # All halls closed in this session
            if get_course_enrolment_count(c_code, registry) > 0:
                return False

    # 5. Exact hall packability check (ALG-08 / HallPackabilityChecker)
    if packability_checker is not None:
        proposed_courses = list(current_in_session) + [c_code]
        if not _evaluate_packability(
            packability_checker, session, proposed_courses, registry, closed_halls
        ):
            return False

    return True


# ---------------------------------------------------------------------------
# Main Timetable Scheduler (ALG-06)
# ---------------------------------------------------------------------------


def generate_timetable(
    registry: ProblemRegistryProtocol,
    conflict_graph: ConflictGraph | None = None,
    cohorts_map: dict[str, frozenset[tuple[str, int]]] | None = None,
    *,
    packability_checker: Callable[..., Any] | None = None,
    closed_halls: frozenset[tuple[str, str]] = frozenset(),
) -> TimetableResult:
    """Generate a deterministic timetable using the two-pass greedy heuristic (ALG-06).

    Parameters
    ----------
    registry:
        The problem registry providing courses, students, enrolments, and sessions.
    conflict_graph:
        Precomputed ConflictGraph from ALG-03 (computed if omitted).
    cohorts_map:
        Precomputed cohorts mapping from ALG-04 (computed if omitted).
    packability_checker:
        Optional ALG-08 packability checker implementation or callable.
    closed_halls:
        Optional set of (session_id, hall_id) pairs closed under BR-10.

    Returns
    -------
    TimetableResult
        Container holding `assignments`, `session_courses`, `violations`,
        and `deferred_courses`. Unpacks directly as (assignments, session_courses, violations).
    """
    # 1. Resolve sessions list from registry
    raw_sessions = getattr(registry, "sessions", None)
    if not raw_sessions and hasattr(registry, "exam_window"):
        raw_sessions = generate_sessions(registry.exam_window)

    if isinstance(raw_sessions, Mapping):
        sessions = tuple(raw_sessions.values())
    elif raw_sessions is not None:
        sessions = tuple(raw_sessions)
    else:
        sessions = ()

    # Sort sessions strictly chronologically by index / date
    sessions = tuple(
        sorted(
            sessions,
            key=lambda s: (
                getattr(s, "session_index", 0),
                getattr(s, "exam_date", date.min),
            ),
        )
    )

    # 2. Build index of sessions on each date
    sessions_by_date: dict[date, list[ExamSessionProtocol]] = {}
    sessions_by_id: dict[str, ExamSessionProtocol] = {}
    for s in sessions:
        sessions_by_date.setdefault(s.exam_date, []).append(s)
        sessions_by_id[s.session_id] = s

    # Ensure registry exposes sessions_by_id for ALG-04 check_core_gap
    if not hasattr(registry, "sessions_by_id"):
        try:
            registry.sessions_by_id = sessions_by_id
        except (AttributeError, TypeError):
            class _RegistryProxy:
                def __init__(self, target: Any, s_by_id: dict[str, Any]) -> None:
                    self._target = target
                    self.sessions_by_id = s_by_id

                def __getattr__(self, name: str) -> Any:
                    return getattr(self._target, name)

            registry = _RegistryProxy(registry, sessions_by_id)

    # 3. Resolve conflict graph and cohorts map if omitted
    if conflict_graph is None:
        conflict_graph = build_conflict_graph(registry)

    if cohorts_map is None:
        cohorts_map = build_cohorts_map(registry)

    # 4. Determine deterministic course processing order (ALG-05)
    ordered_courses = order_courses(registry)

    # 5. Initialize working state
    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {s.session_id: [] for s in sessions}
    violations: list[Violation] = []
    deferred_small: list[Any] = []

    # 6. Process courses sequentially in strict priority order
    for course in ordered_courses:
        c_code = course.course_code
        enrol_cnt = get_course_enrolment_count(c_code, registry)

        chosen_session: ExamSessionProtocol | None = None
        is_fallback = False
        violators: tuple[str, ...] = ()

        # --- PASS 1: Hard Rules + Core Gap (BR-02) ---
        for sess in sessions:
            if is_hard_feasible(
                course,
                sess,
                session_courses,
                registry,
                conflict_graph,
                sessions_by_date,
                packability_checker,
                closed_halls,
            ):
                gap_ok, _ = check_core_gap(
                    course, sess, assignments, cohorts_map, registry
                )
                if gap_ok:
                    chosen_session = sess
                    is_fallback = False
                    break

        # --- PASS 2: Hard Rules Only (Controlled Core-Gap Fallback) ---
        if chosen_session is None:
            for sess in sessions:
                if is_hard_feasible(
                    course,
                    sess,
                    session_courses,
                    registry,
                    conflict_graph,
                    sessions_by_date,
                    packability_checker,
                    closed_halls,
                ):
                    _, violators = check_core_gap(
                        course, sess, assignments, cohorts_map, registry
                    )
                    chosen_session = sess
                    is_fallback = True
                    break

        # --- RECORD PLACEMENT OR FAILURE ---
        if chosen_session is not None:
            assignment = ExamAssignment(
                course_code=c_code,
                session_id=chosen_session.session_id,
                used_gap_soft_fallback=is_fallback,
            )
            assignments[c_code] = assignment
            session_courses[chosen_session.session_id].append(c_code)

            if is_fallback:
                viol_id = f"VIOL-{len(violations) + 1:04d}"
                violations.append(
                    Violation(
                        violation_id=viol_id,
                        category=ViolationCategory.SOFT_VIOLATION,
                        code="CORE_GAP_SOFT_VIOLATION",
                        rule_id="BR-02",
                        session_id=chosen_session.session_id,
                        entity_ids=(c_code, *violators),
                        message=(
                            f"Core course {c_code} placed in session {chosen_session.session_id} "
                            f"on {chosen_session.exam_date} with < 2 calendar day gap against: "
                            f"{', '.join(violators)}."
                        ),
                    )
                )

        elif 1 <= enrol_cnt < 10:
            # Small courses (< 10 students) are preserved for ALG-10 merge repair (AS-006)
            deferred_small.append(course)

        else:
            # Courses with >= 10 (or 0) students that cannot be placed are unscheduled
            is_supp = getattr(course, "is_supplementary", False)
            code = "UNSCHEDULED_SUPPLEMENTARY_NO_SLOT" if is_supp else "UNSCHEDULED_COURSE"
            rule_id = "CN-28" if is_supp else "CN-10"
            viol_id = f"VIOL-{len(violations) + 1:04d}"
            violations.append(
                Violation(
                    violation_id=viol_id,
                    category=ViolationCategory.UNSCHEDULED_COURSE,
                    code=code,
                    rule_id=rule_id,
                    session_id=None,
                    entity_ids=(c_code,),
                    message=f"Course {c_code} could not be scheduled in any feasible session.",
                )
            )

    return TimetableResult(
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        deferred_courses=deferred_small,
    )
