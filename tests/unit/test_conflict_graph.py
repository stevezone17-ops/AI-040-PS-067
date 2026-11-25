"""Unit tests for ALG-03 student conflict graph construction.

Covers BR-01, CN-07, CN-08, EC-06, EC-07, AS-013, AS-014, and TC-008..TC-013
using isolated test-only domain stubs until M1 (exam_engine.domain) is published.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from exam_engine.scheduling.conflict_graph import ConflictGraph, build_conflict_graph


@dataclass(frozen=True, slots=True)
class StubStudent:
    """Test-only stub for M1 Student entity."""

    register_number: str
    backlog_consent: bool = False


@dataclass(frozen=True, slots=True)
class StubEnrolment:
    """Test-only stub for M1 Enrolment entity."""

    register_number: str
    course_code: str
    is_backlog: bool = False


@dataclass(frozen=True, slots=True)
class StubRegistry:
    """Test-only stub for M1 ProblemRegistry."""

    courses: dict[str, object]
    students: dict[str, StubStudent]
    enrolments_by_student: dict[str, tuple[StubEnrolment, ...]]


def _make_registry(
    course_codes: list[str],
    students: list[StubStudent],
    enrolments: list[StubEnrolment],
) -> StubRegistry:
    by_student: dict[str, list[StubEnrolment]] = {s.register_number: [] for s in students}
    for enrol in enrolments:
        by_student.setdefault(enrol.register_number, []).append(enrol)
    return StubRegistry(
        courses={code: object() for code in course_codes},
        students={s.register_number: s for s in students},
        enrolments_by_student={k: tuple(v) for k, v in by_student.items()},
    )


def test_empty_registry_produces_empty_conflict_graph() -> None:
    """No students and no courses yields empty adjacency maps."""
    registry = _make_registry([], [], [])
    graph = build_conflict_graph(registry)

    assert isinstance(graph, ConflictGraph)
    assert graph.same_session_forbidden == {}
    assert graph.same_day_forbidden == {}


def test_tc_008_disjoint_cohorts_no_conflicts() -> None:
    """TC-008: Courses without shared students have no same-session or same-day conflicts."""
    registry = _make_registry(
        ["CS101", "CS301"],
        [StubStudent("S1"), StubStudent("S2")],
        [StubEnrolment("S1", "CS101"), StubEnrolment("S2", "CS301")],
    )
    graph = build_conflict_graph(registry)

    assert graph.same_session_forbidden == {"CS101": frozenset(), "CS301": frozenset()}
    assert graph.same_day_forbidden == {"CS101": frozenset(), "CS301": frozenset()}


def test_courses_with_no_enrolments_initialized_empty() -> None:
    """Courses with zero enrolments still appear in adjacency maps with empty sets."""
    registry = _make_registry(["CS000", "CS101"], [StubStudent("S1")], [StubEnrolment("S1", "CS101")])
    graph = build_conflict_graph(registry)

    assert graph.same_session_forbidden["CS000"] == frozenset()
    assert graph.same_day_forbidden["CS000"] == frozenset()


def test_tc_009_two_courses_sharing_one_student() -> None:
    """TC-009: Two courses sharing a regular student are forbidden same-session and same-day."""
    registry = _make_registry(
        ["C1", "C2"],
        [StubStudent("S1", backlog_consent=False)],
        [StubEnrolment("S1", "C1"), StubEnrolment("S1", "C2")],
    )
    graph = build_conflict_graph(registry)

    assert graph.same_session_forbidden["C1"] == frozenset({"C2"})
    assert graph.same_session_forbidden["C2"] == frozenset({"C1"})
    assert graph.same_day_forbidden["C1"] == frozenset({"C2"})
    assert graph.same_day_forbidden["C2"] == frozenset({"C1"})


def test_multiple_courses_sharing_one_student_forms_symmetric_clique() -> None:
    """One student in 3 courses creates symmetric pairwise conflicts without self-edges."""
    registry = _make_registry(
        ["C1", "C2", "C3"],
        [StubStudent("S1")],
        [StubEnrolment("S1", "C1"), StubEnrolment("S1", "C2"), StubEnrolment("S1", "C3")],
    )
    graph = build_conflict_graph(registry)

    for code in ("C1", "C2", "C3"):
        others = frozenset({"C1", "C2", "C3"} - {code})
        assert graph.same_session_forbidden[code] == others
        assert graph.same_day_forbidden[code] == others
        assert code not in graph.same_session_forbidden[code]
        assert code not in graph.same_day_forbidden[code]


def test_multiple_students_sharing_same_course_pair_deduplicated() -> None:
    """Multiple students sharing (C1, C2) produce clean symmetric sets without duplicates."""
    registry = _make_registry(
        ["C1", "C2"],
        [StubStudent("S1"), StubStudent("S2")],
        [
            StubEnrolment("S1", "C1"),
            StubEnrolment("S1", "C2"),
            StubEnrolment("S2", "C1"),
            StubEnrolment("S2", "C2"),
        ],
    )
    graph = build_conflict_graph(registry)

    assert graph.same_session_forbidden == {"C1": frozenset({"C2"}), "C2": frozenset({"C1"})}
    assert graph.same_day_forbidden == {"C1": frozenset({"C2"}), "C2": frozenset({"C1"})}


def test_duplicate_enrolment_does_not_create_self_conflict() -> None:
    """Duplicate (student, course) records never create a self-conflict edge."""
    registry = _make_registry(
        ["C1"],
        [StubStudent("S1")],
        [StubEnrolment("S1", "C1"), StubEnrolment("S1", "C1")],
    )
    graph = build_conflict_graph(registry)

    assert graph.same_session_forbidden["C1"] == frozenset()
    assert graph.same_day_forbidden["C1"] == frozenset()
