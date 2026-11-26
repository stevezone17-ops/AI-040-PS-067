"""Unit tests for ALG-10: Small-Course Deferral and Repair.

Covers:
  - BR-05 / CN-16: Mandatory cross-department small-course merging (1 <= enrolment < 10)
  - BR-04 / CN-11 / CN-12: Session aggregate 90% capacity and duration homogeneity
  - BR-01 / CN-07 / CN-08: Student conflict clash prevention (session and day)
  - BR-12 / CN-28 / EC-08: Supplementary window and slot constraints
  - AS-006: Small-course merging when no compatible partner exists in initial session
  - AS-007: Multiple small courses pairing and co-scheduling across departments
  - AS-032: Deterministic repair when greedy placement encounters spatial constraints
  - EC-02: Boundary check for small courses (enrolment 9 vs 10; < 10 threshold)
  - Comprehensive unit test criteria from Phase 6 prompt:
    1. Successful small-course deferral
    2. Successful deferred-course repair (single and paired)
    3. Failed repair and correct diagnostic generation (UNSCHEDULED_COURSE)
    4. Enrolment boundary cases: 0, 1, 9, 10
    5. Multiple deferred courses
    6. Deterministic repair ordering (-enrolment, -credits, course_code)
    7. Student conflict prevention
    8. Supplementary examination restrictions
    9. Capacity and hall-packability restrictions
    10. Preservation of hard constraints
    11. Duplicate assignment prevention
    12. Loop termination
    13. Empty deferred-course collections
    14. Repeated execution producing identical results
    15. Input immutability
    16. Scheduler integration with repair_small_courses flag
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from exam_engine.scheduling.scheduler import (
    ExamAssignment,
    ViolationCategory,
    generate_timetable,
)
from exam_engine.scheduling.small_course_repair import (
    MAX_SMALL_COURSE_ENROLMENT,
    MIN_SMALL_COURSE_ENROLMENT,
    SmallCourseRepairResult,
    is_small_course_eligible,
    repair_deferred_courses,
)

# ---------------------------------------------------------------------------
# Test-only Stubs
# ---------------------------------------------------------------------------


class StubSessionSlot(Enum):
    """Stub SessionSlot enum."""

    FN = "FN"
    AN = "AN"


@dataclass(frozen=True)
class StubCourse:
    """Stub Course entity."""

    course_code: str
    credits: int = 3
    department: str = "CSE"
    duration_hours: int = 3
    is_supplementary: bool = False
    semester: int = 1


@dataclass(frozen=True)
class StubStudent:
    """Stub Student entity."""

    register_number: str
    programme: str = "BTech-CSE"
    semester: int = 1
    backlog_consent: bool = False


@dataclass(frozen=True)
class StubEnrolment:
    """Stub Enrolment entity."""

    register_number: str
    course_code: str
    is_backlog: bool = False


@dataclass(frozen=True)
class StubHall:
    """Stub Hall entity."""

    hall_id: str
    capacity: int = 100
    floor: int = 0
    rows: int = 10
    columns: int = 10


@dataclass(frozen=True)
class StubExamSession:
    """Stub ExamSession entity."""

    session_id: str
    session_index: int
    exam_date: date
    slot: StubSessionSlot
    is_supplementary_window_date: bool = False


@dataclass
class StubRegistry:
    """Stub ProblemRegistry for testing."""

    courses: dict[str, Any] = field(default_factory=dict)
    students: dict[str, Any] = field(default_factory=dict)
    sessions: tuple[Any, ...] = ()
    halls: dict[str, Any] = field(default_factory=dict)
    enrolments_by_course: dict[str, list[StubEnrolment]] = field(
        default_factory=dict
    )
    enrolments_by_student: dict[str, list[StubEnrolment]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.enrolments_by_course and self.enrolments_by_student:
            by_c: dict[str, list[StubEnrolment]] = {}
            for e_list in self.enrolments_by_student.values():
                for e in e_list:
                    by_c.setdefault(e.course_code, []).append(e)
            self.enrolments_by_course = by_c
        elif not self.enrolments_by_student and self.enrolments_by_course:
            by_s: dict[str, list[StubEnrolment]] = {}
            for e_list in self.enrolments_by_course.values():
                for e in e_list:
                    by_s.setdefault(e.register_number, []).append(e)
            self.enrolments_by_student = by_s

        # Ensure every student referenced in enrolments exists in self.students
        for s_id in self.enrolments_by_student:
            if s_id not in self.students:
                self.students[s_id] = StubStudent(register_number=s_id)
        self.sessions_by_id = {s.session_id: s for s in self.sessions}


def make_students(prefix: str, count: int) -> list[StubStudent]:
    """Helper to generate stub students."""
    return [StubStudent(f"{prefix}_{i:03d}") for i in range(count)]


def make_enrolments(prefix: str, count: int, course_code: str) -> list[StubEnrolment]:
    """Helper to generate stub enrolments."""
    return [StubEnrolment(f"{prefix}_{i:03d}", course_code) for i in range(count)]


# ---------------------------------------------------------------------------
# 1. Enrolment Boundary and Eligibility Tests (EC-02)
# ---------------------------------------------------------------------------


def test_is_small_course_eligible_boundary_cases() -> None:
    """Test enrolment boundary cases: 0, 1, 9, 10."""
    # Constants check
    assert MIN_SMALL_COURSE_ENROLMENT == 1
    assert MAX_SMALL_COURSE_ENROLMENT == 9

    # Boundary 0: not eligible
    assert is_small_course_eligible(0) is False
    c0 = StubCourse("C0")
    reg0 = StubRegistry(courses={"C0": c0}, enrolments_by_course={"C0": []})
    assert is_small_course_eligible(c0, reg0) is False

    # Boundary 1: eligible (lower inclusive bound)
    assert is_small_course_eligible(1) is True
    c1 = StubCourse("C1")
    reg1 = StubRegistry(courses={"C1": c1}, enrolments_by_course={"C1": make_enrolments("S1", 1, "C1")})
    assert is_small_course_eligible(c1, reg1) is True

    # Mid-range: eligible
    assert is_small_course_eligible(5) is True

    # Boundary 9: eligible (upper inclusive bound)
    assert is_small_course_eligible(9) is True
    c9 = StubCourse("C9")
    reg9 = StubRegistry(courses={"C9": c9}, enrolments_by_course={"C9": make_enrolments("S9", 9, "C9")})
    assert is_small_course_eligible(c9, reg9) is True

    # Boundary 10: not eligible (standard course)
    assert is_small_course_eligible(10) is False
    c10 = StubCourse("C10")
    reg10 = StubRegistry(courses={"C10": c10}, enrolments_by_course={"C10": make_enrolments("S10", 10, "C10")})
    assert is_small_course_eligible(c10, reg10) is False

    # Negative values: not eligible
    assert is_small_course_eligible(-1) is False


def test_repair_rejects_courses_with_ten_or_more_students() -> None:
    """Courses with enrolment >= 10 must raise ValueError if passed to repair."""
    c_large = StubCourse("LARGE", credits=3)
    reg = StubRegistry(
        courses={"LARGE": c_large},
        enrolments_by_course={"LARGE": make_enrolments("SL", 10, "LARGE")},
    )
    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {}
    violations: list[Any] = []

    with pytest.raises(ValueError, match="not eligible for small-course repair"):
        repair_deferred_courses(
            deferred_courses=[c_large],
            assignments=assignments,
            session_courses=session_courses,
            violations=violations,
            registry=reg,
        )


def test_repair_rejects_courses_with_zero_students() -> None:
    """Courses with 0 students must raise ValueError if passed to repair."""
    c_zero = StubCourse("ZERO", credits=3)
    reg = StubRegistry(
        courses={"ZERO": c_zero},
        enrolments_by_course={"ZERO": []},
    )
    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {}
    violations: list[Any] = []

    with pytest.raises(ValueError, match="not eligible for small-course repair"):
        repair_deferred_courses(
            deferred_courses=[c_zero],
            assignments=assignments,
            session_courses=session_courses,
            violations=violations,
            registry=reg,
        )


# ---------------------------------------------------------------------------
# 2. Empty Collections and Input Immutability Tests
# ---------------------------------------------------------------------------


def test_empty_deferred_courses_collection() -> None:
    """Empty deferred_courses collection returns empty result with zero modifications."""
    reg = StubRegistry()
    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {}
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=(),
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    assert isinstance(result, SmallCourseRepairResult)
    assert result.repaired_courses == ()
    assert result.unrepaired_courses == ()
    assert result.new_assignments == {}
    assert result.new_violations == ()
    assert assignments == {}
    assert violations == []


def test_input_immutability() -> None:
    """repair_deferred_courses does not mutate the passed deferred_courses sequence."""
    c_small1 = StubCourse("S1", department="CSE", duration_hours=3)
    c_small2 = StubCourse("S2", department="ECE", duration_hours=3)
    deferred_list = [c_small1, c_small2]
    original_copy = list(deferred_list)

    sess = StubExamSession("S1_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)
    reg = StubRegistry(
        courses={"S1": c_small1, "S2": c_small2},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "S1": make_enrolments("R1", 5, "S1"),
            "S2": make_enrolments("R2", 4, "S2"),
        },
    )

    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {sess.session_id: []}
    violations: list[Any] = []

    repair_deferred_courses(
        deferred_courses=deferred_list,
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    # Input list remains identical
    assert deferred_list == original_copy


# ---------------------------------------------------------------------------
# 3. Successful Repair: Pass 1 (Single-Course Relocation into Compatible Session)
# ---------------------------------------------------------------------------


def test_successful_repair_single_course_into_existing_compatible_session() -> None:
    """Small course relocates into session with an already placed compatible partner (AS-006)."""
    # Session 0 has C_REG (30 students, department='ECE', duration=3h)
    c_reg = StubCourse("C_REG", department="ECE", duration_hours=3)
    # Deferred small course C_SMALL (5 students, department='CSE', duration=3h)
    c_small = StubCourse("C_SMALL", department="CSE", duration_hours=3)

    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    reg = StubRegistry(
        courses={"C_REG": c_reg, "C_SMALL": c_small},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_REG": make_enrolments("R_reg", 30, "C_REG"),
            "C_SMALL": make_enrolments("R_sm", 5, "C_SMALL"),
        },
    )

    assignments = {"C_REG": ExamAssignment("C_REG", sess.session_id, False)}
    session_courses = {sess.session_id: ["C_REG"]}
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=[c_small],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    assert c_small in result.repaired_courses
    assert result.unrepaired_courses == ()
    assert "C_SMALL" in assignments
    assert assignments["C_SMALL"].session_id == sess.session_id
    assert "C_SMALL" in session_courses[sess.session_id]
    assert result.new_violations == ()


def test_single_course_repair_rejects_session_with_same_department_only() -> None:
    """Small course cannot merge into session where existing course is from SAME department (BR-05)."""
    # Both courses are CSE (same department!)
    c_reg_cse = StubCourse("C_CSE_BIG", department="CSE", duration_hours=3)
    c_small_cse = StubCourse("C_CSE_SMALL", department="CSE", duration_hours=3)

    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    reg = StubRegistry(
        courses={"C_CSE_BIG": c_reg_cse, "C_CSE_SMALL": c_small_cse},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_CSE_BIG": make_enrolments("R_b", 30, "C_CSE_BIG"),
            "C_CSE_SMALL": make_enrolments("R_s", 5, "C_CSE_SMALL"),
        },
    )

    assignments = {"C_CSE_BIG": ExamAssignment("C_CSE_BIG", sess.session_id, False)}
    session_courses = {sess.session_id: ["C_CSE_BIG"]}
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=[c_small_cse],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    # Cannot merge with same department -> remains unrepaired and emits UNSCHEDULED_COURSE
    assert result.repaired_courses == ()
    assert c_small_cse in result.unrepaired_courses
    assert "C_CSE_SMALL" not in assignments
    assert len(result.new_violations) == 1
    assert result.new_violations[0].category == ViolationCategory.UNSCHEDULED_COURSE
    assert result.new_violations[0].code == "UNSCHEDULED_COURSE"


def test_single_course_repair_rejects_session_with_different_duration_only() -> None:
    """Small course (2h) cannot merge into session where existing course is 3h (BR-04, BR-05)."""
    c_reg_3h = StubCourse("C_3H", department="ECE", duration_hours=3)
    c_small_2h = StubCourse("C_2H", department="CSE", duration_hours=2)

    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    reg = StubRegistry(
        courses={"C_3H": c_reg_3h, "C_2H": c_small_2h},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_3H": make_enrolments("R_3h", 30, "C_3H"),
            "C_2H": make_enrolments("R_2h", 5, "C_2H"),
        },
    )

    assignments = {"C_3H": ExamAssignment("C_3H", sess.session_id, False)}
    session_courses = {sess.session_id: ["C_3H"]}
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=[c_small_2h],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    assert result.repaired_courses == ()
    assert c_small_2h in result.unrepaired_courses
    assert "C_2H" not in assignments
    assert len(result.new_violations) == 1
    assert result.new_violations[0].code == "UNSCHEDULED_COURSE"


# ---------------------------------------------------------------------------
# 4. Successful Repair: Pass 2 (Pair Co-Scheduling Across Departments)
# ---------------------------------------------------------------------------


def test_successful_repair_co_scheduling_two_small_courses() -> None:
    """Two small courses of different departments and equal duration co-schedule as pair (AS-007, TC-039)."""
    c_s1 = StubCourse("C_S1", department="CSE", duration_hours=3)
    c_s2 = StubCourse("C_S2", department="ECE", duration_hours=3)

    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    reg = StubRegistry(
        courses={"C_S1": c_s1, "C_S2": c_s2},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_S1": make_enrolments("R1", 7, "C_S1"),
            "C_S2": make_enrolments("R2", 6, "C_S2"),
        },
    )

    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {sess.session_id: []}
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=[c_s1, c_s2],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    assert set(result.repaired_courses) == {c_s1, c_s2}
    assert result.unrepaired_courses == ()
    assert "C_S1" in assignments and "C_S2" in assignments
    assert assignments["C_S1"].session_id == sess.session_id
    assert assignments["C_S2"].session_id == sess.session_id
    assert set(session_courses[sess.session_id]) == {"C_S1", "C_S2"}
    assert result.new_violations == ()


def test_pair_co_scheduling_rejects_same_department_pair() -> None:
    """Two small courses from same department cannot pair together; both remain unscheduled."""
    c_s1 = StubCourse("C_S1", department="MECH", duration_hours=3)
    c_s2 = StubCourse("C_S2", department="MECH", duration_hours=3)

    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    reg = StubRegistry(
        courses={"C_S1": c_s1, "C_S2": c_s2},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_S1": make_enrolments("R1", 7, "C_S1"),
            "C_S2": make_enrolments("R2", 6, "C_S2"),
        },
    )

    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {sess.session_id: []}
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=[c_s1, c_s2],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    assert result.repaired_courses == ()
    assert set(result.unrepaired_courses) == {c_s1, c_s2}
    assert len(result.new_violations) == 2
    assert all(v.code == "UNSCHEDULED_COURSE" for v in result.new_violations)


def test_pair_co_scheduling_rejects_different_duration_pair() -> None:
    """Two small courses of different durations (2h vs 3h) cannot pair together."""
    c_s1 = StubCourse("C_S1", department="CSE", duration_hours=2)
    c_s2 = StubCourse("C_S2", department="ECE", duration_hours=3)

    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    reg = StubRegistry(
        courses={"C_S1": c_s1, "C_S2": c_s2},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_S1": make_enrolments("R1", 7, "C_S1"),
            "C_S2": make_enrolments("R2", 6, "C_S2"),
        },
    )

    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {sess.session_id: []}
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=[c_s1, c_s2],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    assert result.repaired_courses == ()
    assert len(result.new_violations) == 2


# ---------------------------------------------------------------------------
# 5. Hard Constraint Preservation in Small-Course Repair
# ---------------------------------------------------------------------------


def test_student_conflict_prevents_small_course_pair_co_scheduling() -> None:
    """Two small courses sharing a student cannot be co-scheduled in same session (BR-01, CN-07)."""
    c_s1 = StubCourse("C_S1", department="CSE", duration_hours=3)
    c_s2 = StubCourse("C_S2", department="ECE", duration_hours=3)

    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    # Shared student R_SHARED takes both C_S1 and C_S2
    reg = StubRegistry(
        courses={"C_S1": c_s1, "C_S2": c_s2},
        students={"R_SHARED": StubStudent("R_SHARED")},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_S1": [StubEnrolment("R_SHARED", "C_S1")] + make_enrolments("R1", 4, "C_S1"),
            "C_S2": [StubEnrolment("R_SHARED", "C_S2")] + make_enrolments("R2", 4, "C_S2"),
        },
    )

    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {sess.session_id: []}
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=[c_s1, c_s2],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    assert result.repaired_courses == ()
    assert "C_S1" not in assignments
    assert "C_S2" not in assignments
    assert len(result.new_violations) == 2


def test_supplementary_small_course_repair_restricted_to_window_and_an_slot() -> None:
    """Supplementary small course (<= 50 students) can only repair into AN slot in window (BR-12, CN-28)."""
    # 2 sessions: Session 0 is Regular Day 1 FN; Session 1 is Supplementary Window Day 2 AN
    sess_reg_fn = StubExamSession("S_REG_FN", 0, date(2025, 12, 1), StubSessionSlot.FN, False)
    sess_supp_an = StubExamSession("S_SUPP_AN", 1, date(2025, 12, 2), StubSessionSlot.AN, True)

    c_partner = StubCourse("C_PARTNER", department="ECE", duration_hours=3)
    c_supp_small = StubCourse("C_SUPP_S", department="CSE", duration_hours=3, is_supplementary=True)

    hall = StubHall("H1", capacity=100)

    reg = StubRegistry(
        courses={"C_PARTNER": c_partner, "C_SUPP_S": c_supp_small},
        sessions=(sess_reg_fn, sess_supp_an),
        halls={"H1": hall},
        enrolments_by_course={
            "C_PARTNER": make_enrolments("RP", 20, "C_PARTNER"),
            "C_SUPP_S": make_enrolments("RS", 5, "C_SUPP_S"),
        },
    )

    # Both sessions have C_PARTNER
    assignments = {
        "C_PARTNER": ExamAssignment("C_PARTNER", sess_supp_an.session_id, False)
    }
    session_courses = {
        sess_reg_fn.session_id: ["C_PARTNER"],
        sess_supp_an.session_id: ["C_PARTNER"],
    }
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=[c_supp_small],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    # Must be placed in S_SUPP_AN, NOT S_REG_FN
    assert c_supp_small in result.repaired_courses
    assert assignments["C_SUPP_S"].session_id == sess_supp_an.session_id


def test_capacity_threshold_enforcement_in_repair() -> None:
    """Repair rejects session if adding small course exceeds 90% seat capacity ceiling (BR-04, CN-11)."""
    # Hall capacity 100 -> cap_90 = 90
    hall = StubHall("H1", capacity=100)
    # Existing course in session has 88 students
    c_big = StubCourse("C_BIG", department="ECE", duration_hours=3)
    # Small course has 5 students -> 88 + 5 = 93 > 90 -> capacity overflow!
    c_small = StubCourse("C_SMALL", department="CSE", duration_hours=3)

    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)

    reg = StubRegistry(
        courses={"C_BIG": c_big, "C_SMALL": c_small},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_BIG": make_enrolments("RB", 88, "C_BIG"),
            "C_SMALL": make_enrolments("RS", 5, "C_SMALL"),
        },
    )

    assignments = {"C_BIG": ExamAssignment("C_BIG", sess.session_id, False)}
    session_courses = {sess.session_id: ["C_BIG"]}
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=[c_small],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    assert result.repaired_courses == ()
    assert c_small in result.unrepaired_courses
    assert len(result.new_violations) == 1
    assert result.new_violations[0].code == "UNSCHEDULED_COURSE"


def test_hall_packability_checker_integration_in_repair() -> None:
    """Pluggable HallPackabilityChecker rejecting placement causes repair to reject session (ALG-08)."""
    c_partner = StubCourse("C_PARTNER", department="ECE", duration_hours=3)
    c_small = StubCourse("C_SMALL", department="CSE", duration_hours=3)

    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    reg = StubRegistry(
        courses={"C_PARTNER": c_partner, "C_SMALL": c_small},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_PARTNER": make_enrolments("RP", 20, "C_PARTNER"),
            "C_SMALL": make_enrolments("RS", 5, "C_SMALL"),
        },
    )

    assignments = {"C_PARTNER": ExamAssignment("C_PARTNER", sess.session_id, False)}
    session_courses = {sess.session_id: ["C_PARTNER"]}
    violations: list[Any] = []

    # Custom packability checker that rejects C_SMALL
    def rejecting_checker(session: Any, codes: Any, registry: Any, closed: Any = None) -> bool:
        return "C_SMALL" not in codes

    result = repair_deferred_courses(
        deferred_courses=[c_small],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
        packability_checker=rejecting_checker,
    )

    assert result.repaired_courses == ()
    assert c_small in result.unrepaired_courses
    assert "C_SMALL" not in assignments
    assert len(result.new_violations) == 1


# ---------------------------------------------------------------------------
# 6. Determinism, Ordering, and Duplicate Prevention Tests
# ---------------------------------------------------------------------------


def test_deterministic_repair_ordering() -> None:
    """Deferred courses are processed strictly by (-enrolment, -credits, course_code)."""
    # 4 small courses:
    # C1: enrol 8, cr 4
    # C2: enrol 8, cr 3
    # C3: enrol 6, cr 4
    # C4: enrol 4, cr 3
    c1 = StubCourse("C1", credits=4, department="CSE", duration_hours=3)
    c2 = StubCourse("C2", credits=3, department="ECE", duration_hours=3)
    c3 = StubCourse("C3", credits=4, department="MECH", duration_hours=3)
    c4 = StubCourse("C4", credits=3, department="CIVIL", duration_hours=3)

    sess1 = StubExamSession("S1_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    sess2 = StubExamSession("S2_FN", 1, date(2025, 12, 2), StubSessionSlot.FN)
    # Hall capacity 20 -> cap_90 = (90 * 20) // 100 = 18 seats max per session
    hall = StubHall("H1", capacity=20)

    reg = StubRegistry(
        courses={"C1": c1, "C2": c2, "C3": c3, "C4": c4},
        sessions=(sess1, sess2),
        halls={"H1": hall},
        enrolments_by_course={
            "C1": make_enrolments("R1", 8, "C1"),
            "C2": make_enrolments("R2", 8, "C2"),
            "C3": make_enrolments("R3", 6, "C3"),
            "C4": make_enrolments("R4", 4, "C4"),
        },
    )

    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {sess1.session_id: [], sess2.session_id: []}
    violations: list[Any] = []

    # Pass in shuffled / reverse order: [C4, C3, C2, C1]
    result = repair_deferred_courses(
        deferred_courses=[c4, c3, c2, c1],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    # In Pass 2:
    # Priority order is C1 (8, 4), C2 (8, 3), C3 (6, 4), C4 (4, 3)
    # C1 (CSE) pairs with C2 (ECE) in S1_FN (earliest session, 8+8=16 <= 18)
    # C3 (MECH) pairs with C4 (CIVIL) in S2_FN (overflows S1: 16+10=26 > 18; fits S2: 6+4=10 <= 18)
    assert assignments["C1"].session_id == sess1.session_id
    assert assignments["C2"].session_id == sess1.session_id
    assert assignments["C3"].session_id == sess2.session_id
    assert assignments["C4"].session_id == sess2.session_id
    assert len(result.repaired_courses) == 4


def test_duplicate_assignment_prevention() -> None:
    """A course is never assigned more than once even if multiple partners match."""
    c_s1 = StubCourse("C_S1", department="CSE", duration_hours=3)
    c_s2 = StubCourse("C_S2", department="ECE", duration_hours=3)
    c_s3 = StubCourse("C_S3", department="MECH", duration_hours=3)

    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    reg = StubRegistry(
        courses={"C_S1": c_s1, "C_S2": c_s2, "C_S3": c_s3},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_S1": make_enrolments("R1", 7, "C_S1"),
            "C_S2": make_enrolments("R2", 6, "C_S2"),
            "C_S3": make_enrolments("R3", 5, "C_S3"),
        },
    )

    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {sess.session_id: []}
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=[c_s1, c_s2, c_s3],
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    # C_S1 and C_S2 pair together in sess. C_S3 has no second partner in sess and no second session.
    assert "C_S1" in assignments
    assert "C_S2" in assignments
    assert session_courses[sess.session_id].count("C_S1") == 1
    assert session_courses[sess.session_id].count("C_S2") == 1
    # C_S3 remains unplaced
    assert c_s3 in result.unrepaired_courses


def test_loop_termination_with_infeasible_inputs() -> None:
    """Repair terminates cleanly and without infinite loop when no courses can pair."""
    # 5 small courses all from CSE
    courses = [StubCourse(f"CSE_{i}", department="CSE", duration_hours=3) for i in range(5)]
    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)

    reg = StubRegistry(
        courses={c.course_code: c for c in courses},
        sessions=(sess,),
        enrolments_by_course={c.course_code: make_enrolments(f"R{i}", 3, c.course_code) for i, c in enumerate(courses)},
    )

    assignments: dict[str, ExamAssignment] = {}
    session_courses: dict[str, list[str]] = {sess.session_id: []}
    violations: list[Any] = []

    result = repair_deferred_courses(
        deferred_courses=courses,
        assignments=assignments,
        session_courses=session_courses,
        violations=violations,
        registry=reg,
    )

    assert len(result.repaired_courses) == 0
    assert len(result.unrepaired_courses) == 5
    assert len(result.new_violations) == 5


def test_idempotent_repeated_execution() -> None:
    """Repeated execution of repair with identical inputs produces identical results."""
    c_s1 = StubCourse("C_S1", department="CSE", duration_hours=3)
    c_s2 = StubCourse("C_S2", department="ECE", duration_hours=3)
    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    reg = StubRegistry(
        courses={"C_S1": c_s1, "C_S2": c_s2},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_S1": make_enrolments("R1", 7, "C_S1"),
            "C_S2": make_enrolments("R2", 6, "C_S2"),
        },
    )

    # Run 1
    a1: dict[str, ExamAssignment] = {}
    sc1: dict[str, list[str]] = {sess.session_id: []}
    v1: list[Any] = []
    res1 = repair_deferred_courses([c_s1, c_s2], a1, sc1, v1, reg)

    # Run 2 (different input order: [c_s2, c_s1])
    a2: dict[str, ExamAssignment] = {}
    sc2: dict[str, list[str]] = {sess.session_id: []}
    v2: list[Any] = []
    res2 = repair_deferred_courses([c_s2, c_s1], a2, sc2, v2, reg)

    assert a1 == a2
    assert sc1 == sc2
    assert len(v1) == len(v2)
    assert set(res1.repaired_courses) == set(res2.repaired_courses)


# ---------------------------------------------------------------------------
# 7. Scheduler Integration with repair_small_courses Flag
# ---------------------------------------------------------------------------


def test_scheduler_integration_with_repair_flag_disabled_by_default() -> None:
    """generate_timetable with default repair_small_courses=False preserves deferred_courses."""
    c_small = StubCourse("SMALL", department="CSE", credits=4)
    student = StubStudent("R1")

    # Registry with no sessions -> cannot be scheduled
    registry = StubRegistry(
        courses={"SMALL": c_small},
        students={"R1": student},
        sessions=(),
        enrolments_by_course={"SMALL": [StubEnrolment("R1", "SMALL")]},
    )

    result = generate_timetable(registry)

    assert "SMALL" not in result.assignments
    assert result.deferred_courses == [c_small]
    # In Phase 5C default, violations list is empty (awaiting repair)
    assert result.violations == []


def test_scheduler_integration_with_repair_flag_enabled_successfully_repairs() -> None:
    """generate_timetable with repair_small_courses=True repairs small courses into sessions."""
    # Two small courses from different departments (CSE and ECE)
    c_s1 = StubCourse("C_S1", department="CSE", credits=3, duration_hours=3)
    c_s2 = StubCourse("C_S2", department="ECE", credits=3, duration_hours=3)

    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    # Packability checker: requires a small course (< 10) to have a different-department partner
    def merge_pack_checker(s: Any, c_codes: Any, reg: Any, closed: Any = None) -> bool:
        has_small = any(len(reg.enrolments_by_course.get(code, [])) < 10 for code in c_codes)
        if not has_small:
            return True
        depts = {reg.courses[code].department for code in c_codes}
        return len(depts) >= 2  # At least 2 departments required if small course present

    reg = StubRegistry(
        courses={"C_S1": c_s1, "C_S2": c_s2},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_S1": make_enrolments("R_s1", 7, "C_S1"),
            "C_S2": make_enrolments("R_s2", 6, "C_S2"),
        },
    )

    # Without repair flag: both small courses fail Pass 1 & 2 alone and are deferred
    res_no_repair = generate_timetable(reg, packability_checker=merge_pack_checker, repair_small_courses=False)
    assert "C_S1" not in res_no_repair.assignments
    assert "C_S2" not in res_no_repair.assignments
    assert set(res_no_repair.deferred_courses) == {c_s1, c_s2}

    # With repair flag: ALG-10 co-schedules C_S1 and C_S2 as a pair into S_FN!
    res_with_repair = generate_timetable(reg, packability_checker=merge_pack_checker, repair_small_courses=True)
    assert "C_S1" in res_with_repair.assignments
    assert "C_S2" in res_with_repair.assignments
    assert res_with_repair.assignments["C_S1"].session_id == sess.session_id
    assert res_with_repair.assignments["C_S2"].session_id == sess.session_id
    assert set(res_with_repair.session_courses[sess.session_id]) == {"C_S1", "C_S2"}
    assert res_with_repair.deferred_courses == []
    assert res_with_repair.violations == []


def test_scheduler_integration_with_repair_flag_enabled_emits_unscheduled_on_failure() -> None:
    """generate_timetable with repair_small_courses=True emits UNSCHEDULED_COURSE when unrepairable."""
    c_small = StubCourse("SMALL_CSE", department="CSE", credits=3, duration_hours=3)
    sess = StubExamSession("S_FN", 0, date(2025, 12, 1), StubSessionSlot.FN)
    hall = StubHall("H1", capacity=100)

    # Checker requires 2 departments, but only 1 CSE course exists in entire dataset
    def merge_pack_checker(s: Any, c_codes: Any, reg: Any, closed: Any = None) -> bool:
        depts = {reg.courses[code].department for code in c_codes}
        return len(depts) >= 2

    reg = StubRegistry(
        courses={"SMALL_CSE": c_small},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={"SMALL_CSE": make_enrolments("R", 5, "SMALL_CSE")},
    )

    result = generate_timetable(reg, packability_checker=merge_pack_checker, repair_small_courses=True)

    assert "SMALL_CSE" not in result.assignments
    assert c_small in result.deferred_courses
    assert len(result.violations) == 1
    assert result.violations[0].category == ViolationCategory.UNSCHEDULED_COURSE
    assert result.violations[0].code == "UNSCHEDULED_COURSE"
