"""Unit tests for ALG-04: Programme-Semester Core-Course Gap Validation.

Covers:
  - build_cohorts_map: regular-enrolment cohort derivation, backlog exclusion,
    fallback when zero regular enrolments.
  - check_core_gap: elective exemption, minimum calendar-day gap enforcement,
    same-cohort matching, edge cases, determinism, and no mutation.

Test case traceability
----------------------
TC-014  Core vs core, same cohort, gap satisfied (|Dec03 - Dec01| = 2 days)
TC-015  Holiday counts as a calendar day (gap remains 2 days → satisfied)
TC-016  Consecutive-day gap violated (|Dec02 - Dec01| = 1 day)
TC-017  Soft-gap fallback: ALG-04 reports False; relaxation is ALG-06's job
TC-018  Backlog-only cohort uses department/semester fallback
TC-019  Backlog enrolments excluded from cohort computation

M1 dependency status
--------------------
exam_engine.domain is NOT yet published as of Week 2.
All tests use isolated structural stubs consistent with the documented
domain contracts (docs/08_DOMAIN_MODEL.md).  These stubs do NOT duplicate
production entities; they are test-only fixtures.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from exam_engine.scheduling.gap_validator import (
    build_cohorts_map,
    check_core_gap,
    is_core,
)

# ---------------------------------------------------------------------------
# Test-only stubs (structural protocol implementations)
# ---------------------------------------------------------------------------


@dataclass
class StubCourse:
    """Minimal stub for domain.Course."""

    course_code: str
    credits: int
    department: str
    semester: int


@dataclass
class StubStudent:
    """Minimal stub for domain.Student."""

    register_number: str
    programme: str
    semester: int


@dataclass
class StubEnrolment:
    """Minimal stub for domain.Enrolment."""

    register_number: str
    course_code: str
    is_backlog: bool = False


@dataclass
class StubExamAssignment:
    """Minimal stub for domain.ExamAssignment."""

    course_code: str
    session_id: str


@dataclass
class StubSession:
    """Minimal stub for domain.ExamSession."""

    session_id: str
    exam_date: date


@dataclass
class StubRegistry:
    """Minimal stub for domain.ProblemRegistry.

    Builds ``enrolments_by_student`` from a flat list of enrolments.
    """

    courses: dict[str, StubCourse]
    students: dict[str, StubStudent]
    sessions_by_id: dict[str, StubSession]
    _enrolments: list[StubEnrolment] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        # Build the per-student enrolment index expected by build_cohorts_map.
        by_student: dict[str, list[StubEnrolment]] = {}
        for e in self._enrolments:
            by_student.setdefault(e.register_number, []).append(e)
        self.enrolments_by_student: dict[str, list[StubEnrolment]] = by_student


# ---------------------------------------------------------------------------
# Shared helper factories
# ---------------------------------------------------------------------------


def _make_registry(
    courses: list[StubCourse],
    students: list[StubStudent],
    enrolments: list[StubEnrolment],
    sessions: list[StubSession] | None = None,
) -> StubRegistry:
    return StubRegistry(
        courses={c.course_code: c for c in courses},
        students={s.register_number: s for s in students},
        sessions_by_id={s.session_id: s for s in (sessions or [])},
        _enrolments=enrolments,
    )


# ---------------------------------------------------------------------------
# Tests for is_core helper
# ---------------------------------------------------------------------------


def test_credits_exactly_4_is_core() -> None:
    course = StubCourse("C1", credits=4, department="CS", semester=2)
    assert is_core(course) is True


def test_credits_3_is_not_core() -> None:
    course = StubCourse("C1", credits=3, department="CS", semester=2)
    assert is_core(course) is False


def test_credits_5_is_core() -> None:
    course = StubCourse("C1", credits=5, department="CS", semester=2)
    assert is_core(course) is True


# ---------------------------------------------------------------------------
# Tests for build_cohorts_map
# ---------------------------------------------------------------------------


def test_build_cohorts_map_single_regular_enrolment() -> None:
    """Regular enrolment maps to (programme, semester) pair."""
    student = StubStudent("R001", programme="BTech-CSE", semester=2)
    course = StubCourse("C1", credits=4, department="CS", semester=2)
    enrolment = StubEnrolment("R001", "C1", is_backlog=False)
    registry = _make_registry([course], [student], [enrolment])

    cohorts = build_cohorts_map(registry)
    assert cohorts["C1"] == frozenset({("BTech-CSE", 2)})


def test_build_cohorts_map_multiple_students_same_cohort() -> None:
    """Multiple students with the same (programme, semester) produce one pair."""
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    s2 = StubStudent("R002", programme="BTech-CSE", semester=2)
    course = StubCourse("C1", credits=4, department="CS", semester=2)
    enrolments = [
        StubEnrolment("R001", "C1"),
        StubEnrolment("R002", "C1"),
    ]
    registry = _make_registry([course], [s1, s2], enrolments)
    cohorts = build_cohorts_map(registry)
    assert cohorts["C1"] == frozenset({("BTech-CSE", 2)})


def test_build_cohorts_map_multiple_programmes() -> None:
    """Students from different programmes produce multiple cohort pairs."""
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    s2 = StubStudent("R002", programme="BTech-AIML", semester=2)
    course = StubCourse("C1", credits=4, department="CS", semester=2)
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R002", "C1")]
    registry = _make_registry([course], [s1, s2], enrolments)
    cohorts = build_cohorts_map(registry)
    assert cohorts["C1"] == frozenset({("BTech-CSE", 2), ("BTech-AIML", 2)})


def test_tc_018_backlog_only_cohort_uses_fallback() -> None:
    """TC-018: Course with zero regular enrolments falls back to (dept, sem)."""
    student = StubStudent("R001", programme="BTech-CSE", semester=4)
    course = StubCourse("C1", credits=4, department="CS", semester=2)
    # Only backlog enrolment → no regular cohort
    enrolment = StubEnrolment("R001", "C1", is_backlog=True)
    registry = _make_registry([course], [student], [enrolment])

    cohorts = build_cohorts_map(registry)
    assert cohorts["C1"] == frozenset({("CS", 2)})


def test_tc_019_backlog_enrolment_excluded_from_cohort() -> None:
    """TC-019: is_backlog=True students are excluded from cohort computation."""
    regular_student = StubStudent("R001", programme="BTech-CSE", semester=2)
    backlog_student = StubStudent("R002", programme="BTech-EEE", semester=4)
    course = StubCourse("C1", credits=4, department="CS", semester=2)
    enrolments = [
        StubEnrolment("R001", "C1", is_backlog=False),
        StubEnrolment("R002", "C1", is_backlog=True),
    ]
    registry = _make_registry([course], [regular_student, backlog_student], enrolments)

    cohorts = build_cohorts_map(registry)
    # Only the regular student's (programme, semester) should appear
    assert cohorts["C1"] == frozenset({("BTech-CSE", 2)})
    assert ("BTech-EEE", 4) not in cohorts["C1"]


def test_mixed_regular_and_backlog_enrolments() -> None:
    """Only regular enrolments count toward the cohort."""
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    s2 = StubStudent("R002", programme="BTech-AIML", semester=2)
    s3 = StubStudent("R003", programme="BTech-EEE", semester=4)
    course = StubCourse("C1", credits=4, department="CS", semester=2)
    enrolments = [
        StubEnrolment("R001", "C1", is_backlog=False),
        StubEnrolment("R002", "C1", is_backlog=False),
        StubEnrolment("R003", "C1", is_backlog=True),
    ]
    registry = _make_registry([course], [s1, s2, s3], enrolments)
    cohorts = build_cohorts_map(registry)
    assert cohorts["C1"] == frozenset({("BTech-CSE", 2), ("BTech-AIML", 2)})


def test_zero_enrolment_course_fallback_cohort() -> None:
    """Course with no enrolments at all uses (department, semester) fallback."""
    course = StubCourse("C_EMPTY", credits=4, department="MATH", semester=3)
    registry = _make_registry([course], [], [])
    cohorts = build_cohorts_map(registry)
    assert cohorts["C_EMPTY"] == frozenset({("MATH", 3)})


def test_deterministic_across_reordered_enrolments() -> None:
    """Reordering enrolments must not change the resulting cohorts_map."""
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    s2 = StubStudent("R002", programme="BTech-AIML", semester=2)
    course = StubCourse("C1", credits=4, department="CS", semester=2)
    enrolments_a = [StubEnrolment("R001", "C1"), StubEnrolment("R002", "C1")]
    enrolments_b = [StubEnrolment("R002", "C1"), StubEnrolment("R001", "C1")]

    reg_a = _make_registry([course], [s1, s2], enrolments_a)
    reg_b = _make_registry([course], [s1, s2], enrolments_b)

    assert build_cohorts_map(reg_a)["C1"] == build_cohorts_map(reg_b)["C1"]


# ---------------------------------------------------------------------------
# Tests for check_core_gap — elective exemptions
# ---------------------------------------------------------------------------


def test_elective_course_always_passes() -> None:
    """Elective (credits=3) skips the gap check entirely → (True, ())."""
    course = StubCourse("ELEC", credits=3, department="CS", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 1))
    registry = _make_registry([course], [], [])
    cohorts = build_cohorts_map(registry)
    result = check_core_gap(course, cand, {}, cohorts, registry)
    assert result == (True, ())


def test_two_electives_no_gap_check() -> None:
    """Both courses are electives → gap check irrelevant → (True, ())."""
    c1 = StubCourse("E1", credits=2, department="CS", semester=2)
    c2 = StubCourse("E2", credits=3, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 2))
    s2 = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [StubEnrolment("R001", "E1"), StubEnrolment("R001", "E2")]
    registry = _make_registry([c1, c2], [s1], enrolments, [cand, s2])
    cohorts = build_cohorts_map(registry)
    assignments = {"E2": StubExamAssignment("E2", "S_OTHER")}
    result = check_core_gap(c1, cand, assignments, cohorts, registry)
    assert result == (True, ())


def test_core_vs_elective_no_gap_check() -> None:
    """Core course vs already-assigned elective → no gap required → (True, ())."""
    core = StubCourse("CORE1", credits=4, department="CS", semester=2)
    elec = StubCourse("ELEC1", credits=3, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 2))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [
        StubEnrolment("R001", "CORE1"),
        StubEnrolment("R001", "ELEC1"),
    ]
    registry = _make_registry([core, elec], [s1], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    assignments = {"ELEC1": StubExamAssignment("ELEC1", "S_OTHER")}
    result = check_core_gap(core, cand, assignments, cohorts, registry)
    assert result == (True, ())


# ---------------------------------------------------------------------------
# Tests for check_core_gap — gap boundary enforcement
# ---------------------------------------------------------------------------


def test_tc_014_core_vs_core_same_cohort_gap_satisfied() -> None:
    """TC-014: |Dec03 - Dec01| = 2 days satisfies BR-02 gap requirement."""
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 3))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R001", "C2")]
    registry = _make_registry([c1, c2], [s1], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    assignments = {"C2": StubExamAssignment("C2", "S_OTHER")}
    is_valid, violators = check_core_gap(c1, cand, assignments, cohorts, registry)
    assert is_valid is True
    assert violators == ()


def test_tc_015_holiday_counts_in_gap() -> None:
    """TC-015: Holiday on Dec02 does NOT reduce calendar-day gap.

    C1 on Dec01, C2 candidate Dec03: |gap| = 2 days (calendar arithmetic).
    Dec02 may be a holiday but that does not remove it from the calendar.
    Result: (True, ()) — gap satisfied.
    """
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 3))
    s_assigned = StubSession("S_ASSIGNED", date(2025, 12, 1))
    # Dec 2 is a holiday — the gap_validator uses only calendar math,
    # so the holiday is irrelevant to the check.
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R001", "C2")]
    registry = _make_registry([c1, c2], [s1], enrolments, [cand, s_assigned])
    cohorts = build_cohorts_map(registry)
    assignments = {"C1": StubExamAssignment("C1", "S_ASSIGNED")}
    is_valid, violators = check_core_gap(c2, cand, assignments, cohorts, registry)
    assert is_valid is True
    assert violators == ()


def test_tc_016_consecutive_days_gap_violated() -> None:
    """TC-016: |Dec02 - Dec01| = 1 day violates BR-02 gap requirement."""
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 2))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R001", "C2")]
    registry = _make_registry([c1, c2], [s1], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    assignments = {"C2": StubExamAssignment("C2", "S_OTHER")}
    is_valid, violators = check_core_gap(c1, cand, assignments, cohorts, registry)
    assert is_valid is False
    assert "C2" in violators


def test_same_day_fn_and_an_violates_gap() -> None:
    """FN and AN on the same date share exam_date → |gap| = 0 → violation."""
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    same_date = date(2025, 12, 1)
    cand = StubSession("S_FN", same_date)   # FN slot
    s_an = StubSession("S_AN", same_date)   # AN slot — same exam_date
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R001", "C2")]
    registry = _make_registry([c1, c2], [s1], enrolments, [cand, s_an])
    cohorts = build_cohorts_map(registry)
    assignments = {"C2": StubExamAssignment("C2", "S_AN")}
    is_valid, violators = check_core_gap(c1, cand, assignments, cohorts, registry)
    assert is_valid is False
    assert "C2" in violators


def test_gap_exactly_two_days_satisfies() -> None:
    """Gap of exactly 2 calendar days satisfies BR-02 (strict < 2 check)."""
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 3))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R001", "C2")]
    registry = _make_registry([c1, c2], [s1], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    assignments = {"C2": StubExamAssignment("C2", "S_OTHER")}
    is_valid, violators = check_core_gap(c1, cand, assignments, cohorts, registry)
    assert is_valid is True
    assert violators == ()


def test_gap_more_than_two_days_satisfies() -> None:
    """|Dec05 - Dec01| = 4 days → well above minimum → (True, ())."""
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 5))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R001", "C2")]
    registry = _make_registry([c1, c2], [s1], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    assignments = {"C2": StubExamAssignment("C2", "S_OTHER")}
    is_valid, violators = check_core_gap(c1, cand, assignments, cohorts, registry)
    assert is_valid is True
    assert violators == ()


# ---------------------------------------------------------------------------
# Tests for check_core_gap — cohort matching
# ---------------------------------------------------------------------------


def test_different_programmes_no_shared_cohort() -> None:
    """Different programme cohorts → no cohort overlap → (True, ())."""
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s_cse = StubStudent("R001", programme="BTech-CSE", semester=2)
    s_aiml = StubStudent("R002", programme="BTech-AIML", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 2))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    # C1 only has CSE student; C2 only has AIML student → disjoint cohorts
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R002", "C2")]
    registry = _make_registry([c1, c2], [s_cse, s_aiml], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    assignments = {"C2": StubExamAssignment("C2", "S_OTHER")}
    is_valid, violators = check_core_gap(c1, cand, assignments, cohorts, registry)
    assert is_valid is True
    assert violators == ()


def test_different_semesters_no_shared_cohort() -> None:
    """Same programme, different semester → different cohort → (True, ())."""
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=4)
    s_sem2 = StubStudent("R001", programme="BTech-CSE", semester=2)
    s_sem4 = StubStudent("R002", programme="BTech-CSE", semester=4)
    cand = StubSession("S_CAND", date(2025, 12, 2))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R002", "C2")]
    registry = _make_registry([c1, c2], [s_sem2, s_sem4], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    assignments = {"C2": StubExamAssignment("C2", "S_OTHER")}
    is_valid, violators = check_core_gap(c1, cand, assignments, cohorts, registry)
    assert is_valid is True
    assert violators == ()


def test_cross_programme_common_core_course() -> None:
    """AS-011: Course shared by two programmes creates a union cohort.

    C1 is taken by BTech-AIML Sem2 AND BTech-CSE Sem2.
    C2 is CSE-only Sem2.
    Both share the (BTech-CSE, 2) pair → gap must be enforced.
    """
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s_aiml = StubStudent("R001", programme="BTech-AIML", semester=2)
    s_cse = StubStudent("R002", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 2))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [
        StubEnrolment("R001", "C1"),   # AIML student in C1
        StubEnrolment("R002", "C1"),   # CSE student in C1
        StubEnrolment("R002", "C2"),   # CSE student in C2 (CSE-only)
    ]
    registry = _make_registry([c1, c2], [s_aiml, s_cse], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    # C1 cohort = {(BTech-AIML, 2), (BTech-CSE, 2)}; C2 cohort = {(BTech-CSE, 2)}
    # Intersection = {(BTech-CSE, 2)} → non-empty → gap check applies
    assignments = {"C2": StubExamAssignment("C2", "S_OTHER")}
    is_valid, violators = check_core_gap(c1, cand, assignments, cohorts, registry)
    # Dec02 vs Dec01 = 1 day → violation
    assert is_valid is False
    assert "C2" in violators


# ---------------------------------------------------------------------------
# Tests for check_core_gap — multiple violators, no mutation, determinism
# ---------------------------------------------------------------------------


def test_multiple_violators_all_reported() -> None:
    """Multiple assigned core courses within gap distance all appear in tuple."""
    c_target = StubCourse("CT", credits=4, department="CS", semester=2)
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 2))
    s_a = StubSession("S_A", date(2025, 12, 1))
    s_b = StubSession("S_B", date(2025, 12, 2))
    enrolments = [
        StubEnrolment("R001", "CT"),
        StubEnrolment("R001", "C1"),
        StubEnrolment("R001", "C2"),
    ]
    registry = _make_registry(
        [c_target, c1, c2], [s1], enrolments, [cand, s_a, s_b]
    )
    cohorts = build_cohorts_map(registry)
    assignments = {
        "C1": StubExamAssignment("C1", "S_A"),   # gap = 1 → violation
        "C2": StubExamAssignment("C2", "S_B"),   # gap = 0 → violation
    }
    is_valid, violators = check_core_gap(c_target, cand, assignments, cohorts, registry)
    assert is_valid is False
    assert "C1" in violators
    assert "C2" in violators
    assert len(violators) == 2


def test_exam_assignments_unchanged_after_call() -> None:
    """check_core_gap must not mutate the exam_assignments mapping."""
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 2))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R001", "C2")]
    registry = _make_registry([c1, c2], [s1], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    assignments: dict[str, StubExamAssignment] = {
        "C2": StubExamAssignment("C2", "S_OTHER")
    }
    original_keys = set(assignments.keys())
    check_core_gap(c1, cand, assignments, cohorts, registry)
    assert set(assignments.keys()) == original_keys


def test_deterministic_across_repeated_calls() -> None:
    """Calling check_core_gap twice with identical inputs gives identical output."""
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 2))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R001", "C2")]
    registry = _make_registry([c1, c2], [s1], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    assignments = {"C2": StubExamAssignment("C2", "S_OTHER")}
    r1 = check_core_gap(c1, cand, assignments, cohorts, registry)
    r2 = check_core_gap(c1, cand, assignments, cohorts, registry)
    assert r1 == r2


# ---------------------------------------------------------------------------
# Tests for check_core_gap — edge cases
# ---------------------------------------------------------------------------


def test_no_existing_assignments_returns_valid() -> None:
    """Empty exam_assignments → no violators → (True, ())."""
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 1))
    registry = _make_registry([c1], [], [])
    cohorts = build_cohorts_map(registry)
    result = check_core_gap(c1, cand, {}, cohorts, registry)
    assert result == (True, ())


def test_course_does_not_check_against_itself() -> None:
    """When exam_assignments contains the same course, no self-violation is raised."""
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 1))
    s_self = StubSession("S_SELF", date(2025, 12, 1))
    enrolments = [StubEnrolment("R001", "C1")]
    registry = _make_registry([c1], [s1], enrolments, [cand, s_self])
    cohorts = build_cohorts_map(registry)
    # Same course already in assignments (should be skipped)
    assignments = {"C1": StubExamAssignment("C1", "S_SELF")}
    is_valid, violators = check_core_gap(c1, cand, assignments, cohorts, registry)
    assert is_valid is True
    assert violators == ()


def test_tc_017_soft_gap_fallback_scenario() -> None:
    """TC-017: ALG-04 reports False; relaxation is ALG-06's responsibility.

    This validates EC-01: check_core_gap only detects and reports violations.
    It does not resolve them or apply soft-constraint relaxation.
    The calling scheduler (ALG-06) decides how to handle the returned violators.
    """
    c1 = StubCourse("C1", credits=5, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    cand = StubSession("S_CAND", date(2025, 12, 2))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R001", "C2")]
    registry = _make_registry([c1, c2], [s1], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    assignments = {"C2": StubExamAssignment("C2", "S_OTHER")}
    is_valid, violators = check_core_gap(c1, cand, assignments, cohorts, registry)
    # Gap = 1 day → violation detected and reported; relaxation is ALG-06's job
    assert is_valid is False
    assert "C2" in violators


def test_closed_date_counts_in_gap() -> None:
    """Closed examination slots do not reduce calendar-day gap.

    gap_validator computes gap as pure calendar arithmetic; whether a date
    has a closed slot does not affect the gap.  |Dec03 - Dec01| = 2 days
    regardless of Dec02 being closed.
    """
    c1 = StubCourse("C1", credits=4, department="CS", semester=2)
    c2 = StubCourse("C2", credits=4, department="CS", semester=2)
    s1 = StubStudent("R001", programme="BTech-CSE", semester=2)
    # Dec01 assigned; Dec02 closed (not represented in sessions); candidate Dec03
    cand = StubSession("S_CAND", date(2025, 12, 3))
    s_other = StubSession("S_OTHER", date(2025, 12, 1))
    enrolments = [StubEnrolment("R001", "C1"), StubEnrolment("R001", "C2")]
    registry = _make_registry([c1, c2], [s1], enrolments, [cand, s_other])
    cohorts = build_cohorts_map(registry)
    assignments = {"C2": StubExamAssignment("C2", "S_OTHER")}
    is_valid, violators = check_core_gap(c1, cand, assignments, cohorts, registry)
    assert is_valid is True
    assert violators == ()
