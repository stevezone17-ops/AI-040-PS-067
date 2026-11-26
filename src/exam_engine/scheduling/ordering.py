"""ALG-05: Deterministic Course Ordering.

Implements the deterministic course ordering heuristic (BR-03, CN-10).

Public interface
----------------
order_courses(registry)
    Returns a tuple of Course objects sorted deterministically by the
    three-level priority key:
        1. Enrolment count descending (-enrolment_count)
        2. Credit value descending (-credits)
        3. Course code ascending (course_code)

Constraints and specifications
------------------------------
BR-03   Deterministic Scheduling Heuristic:
        Sort courses by: (1) Descending enrolment, (2) Descending credits,
        (3) Ascending course code.
        Do not replace this heuristic with alternative optimization algorithms.

CN-10   Deterministic Policy:
        Courses must be processed strictly in the order returned by ALG-05.
        Deterministic tie-breaking ensures identical outputs across runs and
        permutation invariance across input record orders (TC-109).

Dependencies
------------
Production (M1): exam_engine.domain — NOT yet published as of Week 2.
Unit-test layer: Structural Protocol classes defined below; test stubs
                 supplied via test fixtures only.

Complexity
----------
Time:  O(C log C + E) where C = number of courses, E = total enrolments.
       Building or verifying the enrolment counts takes O(E) if derived from
       enrolments_by_course / enrolments_by_student, and sorting takes O(C log C).
Space: O(C) auxiliary space to construct the sorted tuple of courses.

See docs/09_ALGORITHM_DESIGN.md §ALG-05, docs/04_BUSINESS_RULE_REGISTER.md §BR-03,
and docs/06_CONSTRAINT_CATALOGUE.md §CN-10.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import (
    Protocol,
    TypeVar,
    runtime_checkable,
)

# ---------------------------------------------------------------------------
# Structural Protocol classes (M1 compatibility layer)
# ---------------------------------------------------------------------------


@runtime_checkable
class CourseProtocol(Protocol):
    """Structural mirror of domain.Course (M1)."""

    course_code: str
    credits: int


CourseType = TypeVar("CourseType", bound=CourseProtocol)


@runtime_checkable
class EnrolmentProtocol(Protocol):
    """Structural mirror of domain.Enrolment (M1)."""

    register_number: str
    course_code: str


@runtime_checkable
class ProblemRegistryProtocol(Protocol):
    """Structural mirror of domain.ProblemRegistry (M1)."""

    courses: Mapping[str, CourseProtocol]
    # May have enrolments_by_course or enrolments_by_student or both
    enrolments_by_course: Mapping[str, Sequence[EnrolmentProtocol]]


# ---------------------------------------------------------------------------
# ALG-05 public function
# ---------------------------------------------------------------------------


def order_courses(
    registry: ProblemRegistryProtocol,
) -> tuple[CourseProtocol, ...]:
    """Deterministically order all courses according to BR-03 / CN-10.

    Courses are sorted by the three-level priority key:
        Priority 1: Student enrolment count (descending)
        Priority 2: Course credits (descending)
        Priority 3: Course code (ascending, lexical tie-breaker)

    Both regular and backlog enrolments count toward the course's student
    enrolment count, as every enrolled student requires a seat and invigilation
    resource regardless of backlog status.

    Courses with 0 enrolments are assigned an enrolment count of 0 and sorted
    consistently by credits and course code (TC-040).

    Neither the input registry nor the course objects within it are mutated.
    The algorithm is strictly deterministic and permutation-invariant with
    respect to the dictionary iteration order of registry.courses.

    Parameters
    ----------
    registry:
        A ProblemRegistry-compatible object providing:
        - `courses`: Mapping[str, Course]
        - `enrolments_by_course`: Mapping[str, Sequence[Enrolment]] (optional or primary)
          or if absent, derivable from `enrolments_by_student`.

    Returns
    -------
    tuple[Course, ...]
        Immutable tuple of Course objects sorted by (-enrolment_count, -credits, course_code).
    """
    # Defensive lookup for enrolment counts:
    # 1. Check if registry provides enrolments_by_course (documented M1 view)
    # 2. Fall back to scanning enrolments_by_student if enrolments_by_course is absent
    enrolments_by_course = getattr(registry, "enrolments_by_course", None)

    if enrolments_by_course is not None:
        def get_count(code: str) -> int:
            enrols = enrolments_by_course.get(code)
            return len(enrols) if enrols is not None else 0

    else:
        # Fallback for minimal test stubs lacking enrolments_by_course
        enrolments_by_student = getattr(registry, "enrolments_by_student", None)
        counts: dict[str, int] = {}
        if enrolments_by_student is not None:
            for enrol_list in enrolments_by_student.values():
                for enrol in enrol_list:
                    counts[enrol.course_code] = counts.get(enrol.course_code, 0) + 1

        def get_count(code: str) -> int:
            return counts.get(code, 0)

    # Sort courses deterministically
    # registry.courses may be iterated in arbitrary dict order, but the key ensures
    # a strict total ordering because course_code is a unique primary key.
    sorted_courses = sorted(
        registry.courses.values(),
        key=lambda c: (-get_count(c.course_code), -c.credits, c.course_code),
    )

    return tuple(sorted_courses)
