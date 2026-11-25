"""ALG-04: Programme-Semester Core-Course Gap Validation.

Implements the minimum calendar-day gap rule (BR-02) between core-course
examinations that share a programme-semester cohort.

Public interface
----------------
build_cohorts_map(registry)
    Pre-compute a mapping from every course code to the frozenset of
    (programme, semester) pairs derived from its regular (non-backlog)
    enrolments.  Call once before the scheduling loop.

check_core_gap(course, cand_session, exam_assignments, cohorts_map, registry)
    Check whether placing *course* in *cand_session* would violate the
    minimum two-calendar-day gap rule against any already-assigned core
    course that shares a cohort with *course*.

Constraints implemented
-----------------------
BR-02   Core examinations (credits >= 4) for the same programme-semester
        cohort must be separated by at least two calendar days.
        |exam_date_A - exam_date_B|_days >= 2 is required.
        Same-day (|d|=0) and consecutive-day (|d|=1) placements both violate.
        Holidays count as calendar days toward the gap.

CN-09   Minimum gap check is applied only to core courses (credits >= 4).
        Elective courses (credits < 4) always pass the gap check.

EC-01   Violations are *reported* as (False, violating_codes); the scheduling
        policy (ALG-06 Pass 2 soft relaxation) is a separate concern.

AS-011  Cohort definition:
        cohorts_map[c] = {(student.programme, student.semester)} across all
        regular (is_backlog=False) enrolments.
        Fallback: if course has zero regular enrolments use
        {(course.department, course.semester)}.

Dependencies
------------
Production (M1): exam_engine.domain — NOT yet published as of Week 2.
Unit-test layer: Structural Protocol classes defined below; test stubs
                 supplied via test fixtures only.

See docs/09_ALGORITHM_DESIGN.md §ALG-04 and docs/04_BUSINESS_RULE_REGISTER.md §BR-02.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import (
    Protocol,
    runtime_checkable,
)

# ---------------------------------------------------------------------------
# Structural Protocol classes (M1 compatibility layer)
# ---------------------------------------------------------------------------
# These Protocols mirror the documented domain contracts in
# docs/08_DOMAIN_MODEL.md.  They allow ALG-04 to operate against either the
# production exam_engine.domain types (when M1 is published) or against
# isolated test-only stubs, without duplicating production entities.
# ---------------------------------------------------------------------------


@runtime_checkable
class CourseProtocol(Protocol):
    """Structural mirror of domain.Course (M1)."""

    course_code: str
    credits: int
    department: str
    semester: int


@runtime_checkable
class StudentProtocol(Protocol):
    """Structural mirror of domain.Student (M1)."""

    register_number: str
    programme: str
    semester: int


@runtime_checkable
class EnrolmentProtocol(Protocol):
    """Structural mirror of domain.Enrolment (M1)."""

    register_number: str
    course_code: str
    is_backlog: bool


@runtime_checkable
class ExamAssignmentProtocol(Protocol):
    """Structural mirror of domain.ExamAssignment (M1)."""

    course_code: str
    session_id: str


@runtime_checkable
class CandSessionProtocol(Protocol):
    """Structural mirror of domain.ExamSession (M1) used as a candidate slot."""

    session_id: str
    exam_date: date


@runtime_checkable
class ProblemRegistryProtocol(Protocol):
    """Structural mirror of domain.ProblemRegistry (M1)."""

    courses: Mapping[str, CourseProtocol]
    students: Mapping[str, StudentProtocol]
    enrolments_by_student: Mapping[str, Sequence[EnrolmentProtocol]]
    sessions_by_id: Mapping[str, CandSessionProtocol]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Minimum gap in calendar days required between core-course examinations
# for the same programme-semester cohort (BR-02).
_MIN_GAP_DAYS: int = 2


def is_core(course: CourseProtocol) -> bool:
    """Return True when *course* is a core course (credits >= 4).

    CN-09: Only core courses are subject to the minimum gap constraint.
    Elective courses (credits < 4) are exempt.
    """
    return course.credits >= 4


# ---------------------------------------------------------------------------
# ALG-04 public functions
# ---------------------------------------------------------------------------


def build_cohorts_map(
    registry: ProblemRegistryProtocol,
) -> dict[str, frozenset[tuple[str, int]]]:
    """Pre-compute programme-semester cohort sets for every course.

    For each course code *c* in the registry the returned mapping stores:

        cohorts_map[c] = frozenset of (programme, semester) pairs

    drawn from every *regular* (is_backlog=False) enrolment of that course.
    When a course has zero regular enrolments (backlog-only or no enrolments
    at all) the fallback cohort ``{(course.department, course.semester)}`` is
    used (AS-011).

    The iteration order over ``registry.courses`` is sorted to ensure
    deterministic output irrespective of the underlying mapping order.

    Parameters
    ----------
    registry:
        A ProblemRegistry-compatible object exposing ``courses``,
        ``students``, and ``enrolments_by_student``.

    Returns
    -------
    dict[str, frozenset[tuple[str, int]]]
        Keyed by ``course_code``; values are non-empty frozensets of
        ``(programme, semester)`` tuples.
    """
    # Build a fast lookup: course_code -> list[EnrolmentProtocol]
    # from the per-student view in the registry.
    course_enrolments: dict[str, list[EnrolmentProtocol]] = {}
    for enrolments in registry.enrolments_by_student.values():
        for enrolment in enrolments:
            course_enrolments.setdefault(enrolment.course_code, []).append(enrolment)

    result: dict[str, frozenset[tuple[str, int]]] = {}

    for code in sorted(registry.courses):
        course = registry.courses[code]
        cohort_pairs: list[tuple[str, int]] = []

        for enrolment in course_enrolments.get(code, []):
            if enrolment.is_backlog:
                # Senior backlog repeaters are excluded from cohort computation
                # (AS-011): they may sit the same exam as a younger cohort but
                # are not part of the scheduling cohort.
                continue
            student = registry.students.get(enrolment.register_number)
            if student is not None:
                cohort_pairs.append((student.programme, student.semester))

        if cohort_pairs:
            result[code] = frozenset(cohort_pairs)
        else:
            # Fallback: zero regular enrolments → use course's own
            # (department, semester) as a singleton cohort (AS-011).
            result[code] = frozenset({(course.department, course.semester)})

    return result


def check_core_gap(
    course: CourseProtocol,
    cand_session: CandSessionProtocol,
    exam_assignments: Mapping[str, ExamAssignmentProtocol],
    cohorts_map: dict[str, frozenset[tuple[str, int]]],
    registry: ProblemRegistryProtocol,
) -> tuple[bool, tuple[str, ...]]:
    """Check whether placing *course* in *cand_session* violates BR-02.

    Parameters
    ----------
    course:
        The course being considered for scheduling.
    cand_session:
        The candidate ExamSession being evaluated.
    exam_assignments:
        Already-committed assignments: course_code -> ExamAssignment.
        This mapping is *not* mutated.
    cohorts_map:
        Pre-computed output of :func:`build_cohorts_map`.
    registry:
        The problem registry (used to look up other courses and sessions).

    Returns
    -------
    (is_valid, violating_courses)
        ``is_valid`` is True when no gap violation exists.
        ``violating_courses`` is an empty tuple when ``is_valid`` is True,
        otherwise a sorted tuple of the course codes whose already-assigned
        sessions are within the minimum gap distance of *cand_session*.

    Algorithm (BR-02 / CN-09 / EC-01 / AS-011)
    --------------------------------------------
    1. If course.credits < 4 → return (True, ()) immediately (elective exempt).
    2. Retrieve my_cohorts = cohorts_map[course.course_code].
    3. For each (other_code, assignment) in sorted(exam_assignments.items()):
       a. Skip if other_code == course.course_code.
       b. Skip if registry.courses[other_code].credits < 4 (elective).
       c. Skip if cohorts_map[other_code] ∩ my_cohorts is empty (disjoint).
       d. Compute |cand_session.exam_date − other_session.exam_date|_days.
       e. If < 2: add other_code to violators.
    4. Return (len(violators) == 0, tuple(violators)).

    Gap is computed as pure calendar-day arithmetic; holidays and closed
    slots count toward the gap because they are still calendar days (BR-02).
    FN and AN on the same date share exam_date so |gap| = 0, which violates.
    """
    # CN-09: elective courses are exempt from the gap constraint.
    if not is_core(course):
        return (True, ())

    my_cohorts: frozenset[tuple[str, int]] = cohorts_map[course.course_code]
    cand_date: date = cand_session.exam_date
    violators: list[str] = []

    for other_code, assignment in sorted(exam_assignments.items()):
        # Skip self-comparison
        if other_code == course.course_code:
            continue

        other_course = registry.courses[other_code]

        # CN-09: other course must also be core
        if not is_core(other_course):
            continue

        # AS-011: courses must share at least one programme-semester cohort
        if not (my_cohorts & cohorts_map[other_code]):
            continue

        # BR-02: compute absolute calendar-day gap
        other_session = registry.sessions_by_id[assignment.session_id]
        gap_days: int = abs((cand_date - other_session.exam_date).days)

        if gap_days < _MIN_GAP_DAYS:
            violators.append(other_code)

    return (len(violators) == 0, tuple(violators))
