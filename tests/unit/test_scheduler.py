"""Unit tests for ALG-06: Earliest-Feasible-Session Timetable Scheduler.

Covers:
  - BR-01, CN-07, CN-08: Student clashes (same-session and same-day)
  - BR-02, BR-03, CN-10: Two-pass greedy scheduling and core-course gaps
  - BR-04, CN-11, AS-001, AS-002: Session 90% aggregate capacity
  - BR-12, CN-28, EC-08, AS-015: Supplementary examination eligibility
  - Hall packability verification (coupled ALG-08 contract)
  - Deferred small-course repair handling (AS-006: 1 <= count < 10)
  - Unscheduled course reporting (AS-032: count >= 10)
  - Determinism across repeated runs and input permutations (TC-109)
  - Comprehensive demonstration scenario (Section 19)
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
    ViolationCategory,
    generate_timetable,
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
    """Minimal stub for domain.Course."""

    course_code: str
    credits: int = 4
    department: str = "CSE"
    semester: int = 1
    duration_hours: int = 3
    is_supplementary: bool = False


@dataclass(frozen=True)
class StubExamSession:
    """Minimal stub for domain.ExamSession."""

    session_id: str
    session_index: int
    exam_date: date
    slot: Any  # StubSessionSlot or str
    is_supplementary_window_date: bool = False


@dataclass(frozen=True)
class StubStudent:
    """Minimal stub for domain.Student."""

    register_number: str
    programme: str = "BTech-CSE"
    semester: int = 1
    backlog_consent: bool = False


@dataclass(frozen=True)
class StubEnrolment:
    """Minimal stub for domain.Enrolment."""

    register_number: str
    course_code: str
    is_backlog: bool = False


@dataclass(frozen=True)
class StubHall:
    """Minimal stub for domain.Hall."""

    hall_id: str
    capacity: int


@dataclass
class StubRegistry:
    """Minimal stub for domain.ProblemRegistry."""

    courses: dict[str, StubCourse] = field(default_factory=dict)
    students: dict[str, StubStudent] = field(default_factory=dict)
    sessions: tuple[StubExamSession, ...] = field(default_factory=tuple)
    halls: dict[str, StubHall] = field(default_factory=dict)
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


def _make_sessions(num_days: int, start_day: int = 1) -> tuple[StubExamSession, ...]:
    """Create FN and AN sessions across multiple consecutive December dates."""
    sessions: list[StubExamSession] = []
    idx = 0
    # Last 3 active dates are supplementary window
    supp_cutoff = max(1, num_days - 2)
    for d in range(1, num_days + 1):
        dt = date(2025, 12, start_day + d - 1)
        is_supp = d >= supp_cutoff
        sessions.append(
            StubExamSession(
                session_id=f"{dt.isoformat()}_FN",
                session_index=idx,
                exam_date=dt,
                slot=StubSessionSlot.FN,
                is_supplementary_window_date=is_supp,
            )
        )
        idx += 1
        sessions.append(
            StubExamSession(
                session_id=f"{dt.isoformat()}_AN",
                session_index=idx,
                exam_date=dt,
                slot=StubSessionSlot.AN,
                is_supplementary_window_date=is_supp,
            )
        )
        idx += 1
    return tuple(sessions)


# ---------------------------------------------------------------------------
# A. Basic Scheduling Tests
# ---------------------------------------------------------------------------


def test_empty_course_registry() -> None:
    """Empty course registry produces empty assignments and violations."""
    sessions = _make_sessions(2)
    registry = StubRegistry(courses={}, sessions=sessions)
    result = generate_timetable(registry)

    assert result.assignments == {}
    assert result.violations == []
    assert all(len(courses) == 0 for courses in result.session_courses.values())


def test_single_course_single_valid_session() -> None:
    """Single course is assigned to the earliest chronological session."""
    sessions = _make_sessions(2)
    course = StubCourse("CS101", credits=4)
    student = StubStudent("R001")
    enrolment = StubEnrolment("R001", "CS101")

    registry = StubRegistry(
        courses={"CS101": course},
        students={"R001": student},
        sessions=sessions,
        enrolments_by_course={"CS101": [enrolment]},
    )

    result = generate_timetable(registry)

    assert "CS101" in result.assignments
    assignment = result.assignments["CS101"]
    assert assignment.session_id == sessions[0].session_id
    assert assignment.used_gap_soft_fallback is False
    assert result.session_courses[sessions[0].session_id] == ["CS101"]
    assert result.violations == []


def test_multiple_courses_without_conflicts_pack_in_earliest_session() -> None:
    """Non-conflicting courses can be placed in the same earliest session."""
    sessions = _make_sessions(2)
    c1 = StubCourse("CS101", credits=3)  # elective
    c2 = StubCourse("EE101", credits=3)  # elective
    s1 = StubStudent("R001")
    s2 = StubStudent("R002")

    registry = StubRegistry(
        courses={"CS101": c1, "EE101": c2},
        students={"R001": s1, "R002": s2},
        sessions=sessions,
        enrolments_by_course={
            "CS101": [StubEnrolment("R001", "CS101")],
            "EE101": [StubEnrolment("R002", "EE101")],
        },
    )

    result = generate_timetable(registry)

    # Both non-conflicting electives can share the first session
    assert result.assignments["CS101"].session_id == sessions[0].session_id
    assert result.assignments["EE101"].session_id == sessions[0].session_id
    assert set(result.session_courses[sessions[0].session_id]) == {"CS101", "EE101"}


def test_earliest_feasible_session_selection_order() -> None:
    """Courses are processed strictly in ALG-05 order and get earliest slots."""
    sessions = _make_sessions(3)
    # C_BIG has 50 students; C_SMALL has 15 students
    c_big = StubCourse("C_BIG", credits=4)
    c_small = StubCourse("C_SMALL", credits=4)
    s_shared = StubStudent("R_SHARED")  # Clashing student

    enrols_big = [StubEnrolment(f"R_b{i}", "C_BIG") for i in range(49)] + [
        StubEnrolment("R_SHARED", "C_BIG")
    ]
    enrols_small = [StubEnrolment(f"R_s{i}", "C_SMALL") for i in range(14)] + [
        StubEnrolment("R_SHARED", "C_SMALL")
    ]

    registry = StubRegistry(
        courses={"C_BIG": c_big, "C_SMALL": c_small},
        students={"R_SHARED": s_shared},
        sessions=sessions,
        enrolments_by_course={"C_BIG": enrols_big, "C_SMALL": enrols_small},
    )

    result = generate_timetable(registry)

    # C_BIG must be placed in Day 1 FN (session 0)
    assert result.assignments["C_BIG"].session_id == sessions[0].session_id
    # C_SMALL clashes (same student, no backlog consent), so cannot be in Day 1 FN or Day 1 AN
    # Furthermore, both are 4cr core courses sharing a student (cohort) -> gap requires >= 2 calendar days!
    # Day 1 is Dec 01 -> earliest date with gap >= 2 days is Dec 03 (session 4: Day 3 FN)
    assert result.assignments["C_SMALL"].session_id == sessions[4].session_id


def test_examination_window_with_no_available_sessions() -> None:
    """When no sessions exist, eligible courses >= 10 are recorded as UNSCHEDULED."""
    c1 = StubCourse("CS101", credits=4)
    students = [StubStudent(f"R{i}") for i in range(15)]
    enrolments = [StubEnrolment(f"R{i}", "CS101") for i in range(15)]

    registry = StubRegistry(
        courses={"CS101": c1},
        students={s.register_number: s for s in students},
        sessions=(),  # No sessions available
        enrolments_by_course={"CS101": enrolments},
    )

    result = generate_timetable(registry)

    assert result.assignments == {}
    assert len(result.violations) == 1
    assert result.violations[0].category == ViolationCategory.UNSCHEDULED_COURSE
    assert result.violations[0].entity_ids == ("CS101",)


# ---------------------------------------------------------------------------
# B. Student Conflict Enforcement Tests
# ---------------------------------------------------------------------------


def test_same_session_conflict_rejection() -> None:
    """Courses sharing a student cannot occupy the same session."""
    sessions = _make_sessions(2)
    c1 = StubCourse("C1", credits=2)
    c2 = StubCourse("C2", credits=2)
    student = StubStudent("R_CLASH")

    registry = StubRegistry(
        courses={"C1": c1, "C2": c2},
        students={"R_CLASH": student},
        sessions=sessions,
        enrolments_by_course={
            "C1": [StubEnrolment("R_CLASH", "C1")],
            "C2": [StubEnrolment("R_CLASH", "C2")],
        },
    )

    result = generate_timetable(registry)

    assert result.assignments["C1"].session_id != result.assignments["C2"].session_id


def test_same_day_conflict_rejection_without_consent() -> None:
    """Regular student enrolled in two courses blocks both same-session and same-day (AN)."""
    sessions = _make_sessions(3)
    c1 = StubCourse("C1", credits=2)
    c2 = StubCourse("C2", credits=2)
    student = StubStudent("R001", backlog_consent=False)

    registry = StubRegistry(
        courses={"C1": c1, "C2": c2},
        students={"R001": student},
        sessions=sessions,
        enrolments_by_course={
            "C1": [StubEnrolment("R001", "C1", is_backlog=False)],
            "C2": [StubEnrolment("R001", "C2", is_backlog=False)],
        },
    )

    result = generate_timetable(registry)

    # C1 in Day 1 FN (sessions[0]); C2 cannot be in Day 1 AN (sessions[1]) due to same-day rule
    # Earliest next date is Day 2 FN (sessions[2])
    assert result.assignments["C1"].session_id == sessions[0].session_id
    assert result.assignments["C2"].session_id == sessions[2].session_id


def test_valid_backlog_consent_allows_same_day_different_sessions() -> None:
    """TC-011: Backlog student with consent allows regular (FN) and backlog (AN) on same day."""
    sessions = _make_sessions(3)
    c_reg = StubCourse("C_REG", credits=2)
    c_back = StubCourse("C_BACK", credits=2)
    student = StubStudent("R_CONSENT", backlog_consent=True)

    registry = StubRegistry(
        courses={"C_REG": c_reg, "C_BACK": c_back},
        students={"R_CONSENT": student},
        sessions=sessions,
        enrolments_by_course={
            "C_REG": [StubEnrolment("R_CONSENT", "C_REG", is_backlog=False)],
            "C_BACK": [StubEnrolment("R_CONSENT", "C_BACK", is_backlog=True)],
        },
    )

    result = generate_timetable(registry)

    # With consent: C_BACK in Day 1 FN (session 0), C_REG allowed in Day 1 AN (session 1)
    assert result.assignments["C_BACK"].session_id == sessions[0].session_id
    assert result.assignments["C_REG"].session_id == sessions[1].session_id


def test_backlog_consent_never_permits_same_session() -> None:
    """TC-013: Backlog consent never allows both courses in the EXACT same session."""
    sessions = (StubExamSession("S1_FN", 0, date(2025, 12, 1), StubSessionSlot.FN),)
    c_reg = StubCourse("C_REG", credits=2)
    c_back = StubCourse("C_BACK", credits=2)
    student = StubStudent("R001", backlog_consent=True)

    # Only one session exists in window
    registry = StubRegistry(
        courses={"C_REG": c_reg, "C_BACK": c_back},
        students={"R001": student},
        sessions=sessions,
        enrolments_by_course={
            "C_REG": [StubEnrolment("R001", "C_REG", is_backlog=False)],
            "C_BACK": [StubEnrolment("R001", "C_BACK", is_backlog=True)],
        },
    )

    result = generate_timetable(registry)

    # Only one can take S1_FN, other cannot fit
    assigned = list(result.assignments.keys())
    assert len(assigned) == 1


# ---------------------------------------------------------------------------
# C. Core-Course Gap Enforcement Tests (BR-02, BR-03, EC-01)
# ---------------------------------------------------------------------------


def test_strict_pass_satisfies_minimum_two_day_gap() -> None:
    """TC-014: Two core courses sharing a cohort separated by >= 2 calendar days."""
    sessions = _make_sessions(4)
    c1 = StubCourse("CORE1", credits=4)
    c2 = StubCourse("CORE2", credits=4)
    student = StubStudent("R001", programme="BTech-CSE", semester=2)

    registry = StubRegistry(
        courses={"CORE1": c1, "CORE2": c2},
        students={"R001": student},
        sessions=sessions,
        enrolments_by_course={
            "CORE1": [StubEnrolment("R001", "CORE1")],
            "CORE2": [StubEnrolment("R001", "CORE2")],
        },
    )

    result = generate_timetable(registry)

    s1 = registry.sessions_by_id[result.assignments["CORE1"].session_id]
    s2 = registry.sessions_by_id[result.assignments["CORE2"].session_id]

    # Calendar gap must be >= 2 days
    assert abs((s2.exam_date - s1.exam_date).days) >= 2
    assert result.violations == []


def test_pass2_controlled_relaxation_records_soft_violation() -> None:
    """EC-01 / TC-016 / TC-017: When only consecutive days exist, Pass 2 relaxes gap and records violation."""
    # Window has only 2 days: Dec 01 and Dec 02 (max gap = 1 day)
    sessions = _make_sessions(2)
    c1 = StubCourse("AIML601", credits=4)
    c2 = StubCourse("AIML602", credits=4)
    student = StubStudent("R001", programme="BTech-AIML", semester=6)

    registry = StubRegistry(
        courses={"AIML601": c1, "AIML602": c2},
        students={"R001": student},
        sessions=sessions,
        enrolments_by_course={
            "AIML601": [StubEnrolment("R001", "AIML601")],
            "AIML602": [StubEnrolment("R001", "AIML602")],
        },
    )

    result = generate_timetable(registry)

    assert "AIML601" in result.assignments
    assert "AIML602" in result.assignments

    # One of them used gap soft fallback
    a1 = result.assignments["AIML601"]
    a2 = result.assignments["AIML602"]
    fallback_assign = a1 if a1.used_gap_soft_fallback else a2
    assert fallback_assign.used_gap_soft_fallback is True

    # Exactly one soft violation recorded
    assert len(result.violations) == 1
    viol = result.violations[0]
    assert viol.category == ViolationCategory.SOFT_VIOLATION
    assert viol.code == "CORE_GAP_SOFT_VIOLATION"
    assert viol.rule_id == "BR-02"


def test_later_strictly_feasible_session_preferred_over_earlier_gap_violating_session() -> None:
    """Scheduler must not prematurely relax gap in Pass 1 if a later strictly feasible slot exists."""
    # Window has 4 days: Dec 01, Dec 02, Dec 03, Dec 04
    sessions = _make_sessions(4)
    c1 = StubCourse("CORE_A", credits=4)
    c2 = StubCourse("CORE_B", credits=4)
    student = StubStudent("R001")

    registry = StubRegistry(
        courses={"CORE_A": c1, "CORE_B": c2},
        students={"R001": student},
        sessions=sessions,
        enrolments_by_course={
            "CORE_A": [StubEnrolment("R001", "CORE_A")],
            "CORE_B": [StubEnrolment("R001", "CORE_B")],
        },
    )

    result = generate_timetable(registry)

    # CORE_A in Day 1 FN (Dec 01). Day 2 (Dec 02) violates gap. Day 3 (Dec 03) satisfies gap!
    # Pass 1 must choose Dec 03 (session index 4) with zero soft violations!
    assert result.assignments["CORE_B"].session_id == sessions[4].session_id
    assert result.assignments["CORE_B"].used_gap_soft_fallback is False
    assert result.violations == []


# ---------------------------------------------------------------------------
# D. Supplementary Examination Tests (BR-12, CN-28, EC-08)
# ---------------------------------------------------------------------------


def test_supplementary_course_rejected_outside_supplementary_window() -> None:
    """Supplementary course cannot be scheduled outside final 3 active dates."""
    # 5-day window -> Days 3, 4, 5 are supplementary window; Days 1, 2 are not
    sessions = _make_sessions(5)
    supp_course = StubCourse("SUP101", credits=3, is_supplementary=True)
    student = StubStudent("R001")

    registry = StubRegistry(
        courses={"SUP101": supp_course},
        students={"R001": student},
        sessions=sessions,
        enrolments_by_course={"SUP101": [StubEnrolment("R001", "SUP101")]},
    )

    result = generate_timetable(registry)

    # Must be placed in Day 3 AN (session index 5) or later, NOT in Days 1 or 2
    assigned_sess = registry.sessions_by_id[result.assignments["SUP101"].session_id]
    assert assigned_sess.is_supplementary_window_date is True
    assert assigned_sess.session_index >= 4  # Day 3 starts at index 4


def test_supplementary_course_50_students_restricted_to_an() -> None:
    """TC-085: Supplementary course with <= 50 students strictly restricted to AN."""
    sessions = _make_sessions(4)  # Days 2, 3, 4 are supplementary
    supp_course = StubCourse("SUP50", credits=3, is_supplementary=True)
    students = [StubStudent(f"R{i}") for i in range(50)]
    enrolments = [StubEnrolment(f"R{i}", "SUP50") for i in range(50)]

    registry = StubRegistry(
        courses={"SUP50": supp_course},
        students={s.register_number: s for s in students},
        sessions=sessions,
        enrolments_by_course={"SUP50": enrolments},
    )

    result = generate_timetable(registry)

    assigned_sess = registry.sessions_by_id[result.assignments["SUP50"].session_id]
    assert assigned_sess.is_supplementary_window_date is True
    assert assigned_sess.slot == StubSessionSlot.AN


def test_supplementary_course_51_students_unlocks_fn() -> None:
    """TC-086: Supplementary course with 51 students can take earliest FN in window."""
    sessions = _make_sessions(4)  # Day 2 is first supplementary date
    supp_course = StubCourse("SUP51", credits=3, is_supplementary=True)
    students = [StubStudent(f"R{i}") for i in range(51)]
    enrolments = [StubEnrolment(f"R{i}", "SUP51") for i in range(51)]

    registry = StubRegistry(
        courses={"SUP51": supp_course},
        students={s.register_number: s for s in students},
        sessions=sessions,
        enrolments_by_course={"SUP51": enrolments},
    )

    result = generate_timetable(registry)

    assigned_sess = registry.sessions_by_id[result.assignments["SUP51"].session_id]
    # First supplementary date is Day 2 (session 2 is Day 2 FN)
    assert assigned_sess.session_id == sessions[2].session_id
    assert assigned_sess.slot == StubSessionSlot.FN


def test_supplementary_eligibility_enforced_during_pass2() -> None:
    """Pass 2 core-gap relaxation must NEVER relax supplementary eligibility."""
    # Window has only 1 date, which is NOT flagged supplementary
    sess = (StubExamSession("S1_FN", 0, date(2025, 12, 1), StubSessionSlot.FN, False),)
    supp_course = StubCourse("SUP_FAIL", credits=4, is_supplementary=True)
    student = StubStudent("R001")

    registry = StubRegistry(
        courses={"SUP_FAIL": supp_course},
        students={"R001": student},
        sessions=sess,
        enrolments_by_course={"SUP_FAIL": [StubEnrolment("R001", "SUP_FAIL")]},
    )

    result = generate_timetable(registry)

    # Course must remain unassigned
    assert "SUP_FAIL" not in result.assignments


# ---------------------------------------------------------------------------
# E. Capacity and Packability Tests (BR-04, CN-11, AS-001, AS-002)
# ---------------------------------------------------------------------------


def test_session_capacity_under_and_at_threshold() -> None:
    """Sessions enforce 90% floor capacity limit (AS-002)."""
    sessions = _make_sessions(2)
    # Hall capacity = 100 -> cap_90 = (90 * 100) // 100 = 90
    hall = StubHall("H1", capacity=100)

    c1 = StubCourse("C1", credits=2)
    students = [StubStudent(f"R{i}") for i in range(90)]
    enrolments = [StubEnrolment(f"R{i}", "C1") for i in range(90)]

    registry = StubRegistry(
        courses={"C1": c1},
        students={s.register_number: s for s in students},
        sessions=sessions,
        halls={"H1": hall},
        enrolments_by_course={"C1": enrolments},
    )

    result = generate_timetable(registry)
    # 90 <= 90 -> accepted in session 0
    assert result.assignments["C1"].session_id == sessions[0].session_id


def test_session_capacity_above_threshold_overflows_to_next_session() -> None:
    """Placing students exceeding 90% capacity forces course to next session."""
    sessions = _make_sessions(2)
    # Hall capacity = 100 -> cap_90 = 90
    hall = StubHall("H1", capacity=100)

    c1 = StubCourse("C1", credits=2)
    c2 = StubCourse("C2", credits=2)
    # C1 has 50 students; C2 has 45 students. 50 + 45 = 95 > 90 -> C2 must move to session 1
    enrols_1 = [StubEnrolment(f"R1_{i}", "C1") for i in range(50)]
    enrols_2 = [StubEnrolment(f"R2_{i}", "C2") for i in range(45)]

    registry = StubRegistry(
        courses={"C1": c1, "C2": c2},
        sessions=sessions,
        halls={"H1": hall},
        enrolments_by_course={"C1": enrols_1, "C2": enrols_2},
    )

    result = generate_timetable(registry)

    assert result.assignments["C1"].session_id == sessions[0].session_id
    assert result.assignments["C2"].session_id == sessions[1].session_id


def test_packability_checker_rejection_moves_to_next_session() -> None:
    """Packability checker rejecting session forces scheduler to seek alternative."""
    sessions = _make_sessions(3)
    c1 = StubCourse("C1", credits=2)

    registry = StubRegistry(
        courses={"C1": c1},
        sessions=sessions,
        enrolments_by_course={"C1": [StubEnrolment("R1", "C1")]},
    )

    # Test double: reject session 0, accept session 1
    def mock_checker(session: Any, courses: Any, reg: Any, closed: Any = None) -> bool:
        return session.session_id != sessions[0].session_id

    result = generate_timetable(registry, packability_checker=mock_checker)

    # Must skip session 0 and land on session 1
    assert result.assignments["C1"].session_id == sessions[1].session_id


# ---------------------------------------------------------------------------
# F. Deferred Small Courses and Unscheduled Course Tests
# ---------------------------------------------------------------------------


def test_small_course_deferred_repair_pathway() -> None:
    """Course with 1 <= enrolment < 10 with no feasible session enters deferred_courses."""
    c_small = StubCourse("SMALL", credits=4)
    student = StubStudent("R1")

    # Registry has no sessions -> impossible to place
    registry = StubRegistry(
        courses={"SMALL": c_small},
        students={"R1": student},
        sessions=(),
        enrolments_by_course={"SMALL": [StubEnrolment("R1", "SMALL")]},
    )

    result = generate_timetable(registry)

    assert "SMALL" not in result.assignments
    assert result.deferred_courses == [c_small]
    # Small courses are preserved for ALG-10 repair, not immediately marked UNSCHEDULED
    assert result.violations == []


def test_course_ten_or_more_students_marked_unscheduled() -> None:
    """Course with enrolment >= 10 with no feasible session is marked UNSCHEDULED_COURSE."""
    c_large = StubCourse("LARGE", credits=4)
    students = [StubStudent(f"R{i}") for i in range(12)]
    enrolments = [StubEnrolment(f"R{i}", "LARGE") for i in range(12)]

    registry = StubRegistry(
        courses={"LARGE": c_large},
        students={s.register_number: s for s in students},
        sessions=(),  # No sessions available
        enrolments_by_course={"LARGE": enrolments},
    )

    result = generate_timetable(registry)

    assert "LARGE" not in result.assignments
    assert result.deferred_courses == []
    assert len(result.violations) == 1
    viol = result.violations[0]
    assert viol.category == ViolationCategory.UNSCHEDULED_COURSE
    assert viol.code == "UNSCHEDULED_COURSE"
    assert viol.entity_ids == ("LARGE",)


def test_zero_enrolment_course_behavior() -> None:
    """Course with 0 enrolled students is placed in earliest session with 0 seats."""
    sessions = _make_sessions(2)
    c_zero = StubCourse("ZERO", credits=2)

    registry = StubRegistry(
        courses={"ZERO": c_zero},
        sessions=sessions,
        enrolments_by_course={"ZERO": []},
    )

    result = generate_timetable(registry)

    assert "ZERO" in result.assignments
    assert result.assignments["ZERO"].session_id == sessions[0].session_id
    assert result.violations == []


# ---------------------------------------------------------------------------
# G. Determinism, Immutability & Demonstration Scenario (Section 19)
# ---------------------------------------------------------------------------


def test_deterministic_across_repeated_runs_and_permutations() -> None:
    """TC-109: Results are 100% identical across runs and input dictionary permutations."""
    sessions = _make_sessions(3)
    c1 = StubCourse("CS101", credits=4)
    c2 = StubCourse("CS102", credits=4)
    c3 = StubCourse("MA201", credits=3)

    enrols_40 = [StubEnrolment(f"R_{i}", "CS101") for i in range(40)]
    enrols_30 = [StubEnrolment(f"R_{i}", "CS102") for i in range(30)]
    enrols_20 = [StubEnrolment(f"R_{i}", "MA201") for i in range(20)]

    reg_a = StubRegistry(
        courses={"CS101": c1, "CS102": c2, "MA201": c3},
        sessions=sessions,
        enrolments_by_course={
            "CS101": enrols_40,
            "CS102": enrols_30,
            "MA201": enrols_20,
        },
    )

    reg_b = StubRegistry(
        courses={"MA201": c3, "CS102": c2, "CS101": c1},
        sessions=sessions,
        enrolments_by_course={
            "MA201": enrols_20,
            "CS102": enrols_30,
            "CS101": enrols_40,
        },
    )

    res_a1 = generate_timetable(reg_a)
    res_a2 = generate_timetable(reg_a)
    res_b = generate_timetable(reg_b)

    assert res_a1.assignments == res_a2.assignments == res_b.assignments
    assert res_a1.session_courses == res_a2.session_courses == res_b.session_courses
    assert res_a1.violations == res_a2.violations == res_b.violations


def test_demonstration_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    """Demonstration scenario meeting all criteria of Section 19 of prompt.

    Demonstrates:
    - Multiple examination dates (Dec 01, Dec 02, Dec 03).
    - FN and AN sessions.
    - Regular courses (CSE, ECE, MECH, CIVIL).
    - Core courses (credits >= 4) with 2-day gap enforcement.
    - Supplementary courses (<= 50 students in AN; > 50 in FN/AN).
    - Shared-student conflict clashing.
    - Capacity overflow and packability rejection.
    - Core-gap fallback (Pass 2) triggering CORE_GAP_SOFT_VIOLATION.
    - Deferred small course (1 <= count < 10).
    - Unscheduled course (count >= 10 when sessions exhausted).
    """
    # 3 examination dates: Dec 01, Dec 02, Dec 03 (Sessions 0 to 5)
    sessions = (
        StubExamSession("2025-12-01_FN", 0, date(2025, 12, 1), StubSessionSlot.FN, False),
        StubExamSession("2025-12-01_AN", 1, date(2025, 12, 1), StubSessionSlot.AN, False),
        StubExamSession("2025-12-02_FN", 2, date(2025, 12, 2), StubSessionSlot.FN, True),
        StubExamSession("2025-12-02_AN", 3, date(2025, 12, 2), StubSessionSlot.AN, True),
        StubExamSession("2025-12-03_FN", 4, date(2025, 12, 3), StubSessionSlot.FN, True),
        StubExamSession("2025-12-03_AN", 5, date(2025, 12, 3), StubSessionSlot.AN, True),
    )

    # Hall H1 with capacity 100 -> cap_90 = 90
    hall = StubHall("H1", capacity=100)

    # 1. UNSCHED_BIG: 100 students (exceeds 90 capacity everywhere) -> UNSCHEDULED
    c_unsched = StubCourse("UNSCHED_BIG", credits=3, department="CIVIL")
    # 2. SUPP_LARGE: 55 students (> 50) -> unlocks FN on final 3 days
    c_supp_l = StubCourse("SUPP_LARGE", credits=3, is_supplementary=True)
    # 3. CORE_101: 50 students, 4 cr, BTech-CSE Sem 2 -> Day 1 FN
    c_core1 = StubCourse("CORE_101", credits=4, department="CSE", semester=2)
    # 4. CORE_102: 45 students, 4 cr, BTech-CSE Sem 2 -> Day 3 FN (gap >= 2 days to CORE_101)
    c_core2 = StubCourse("CORE_102", credits=4, department="CSE", semester=2)
    # 5. CORE_GAP_FALLBACK: 40 students, 4 cr, BTech-CSE Sem 2 -> Pass 2 fallback on Day 2 FN!
    c_core_gap = StubCourse("CORE_GAP_FALLBACK", credits=4, department="CSE", semester=2)
    # 6. SUPP_SMALL: 30 students (<= 50) -> restricted to AN in supplementary window
    c_supp_s = StubCourse("SUPP_SMALL", credits=3, is_supplementary=True)
    # 7. CLASH_STUDENT: 20 students, regular course sharing student with CORE_101
    c_clash = StubCourse("CLASH_STUDENT", credits=2, department="ECE", semester=2)
    # 8. SMALL_DEF: 5 students, packability rejected -> deferred_courses
    c_small_def = StubCourse("SMALL_DEF", credits=2, department="MECH")

    # Shared student between CORE_101 and CLASH_STUDENT
    s_clash = StubStudent("R_CLASH", programme="BTech-CSE", semester=2)
    # Cohort student shared across CORE_101, CORE_102, and CORE_GAP_FALLBACK
    s_cohort = StubStudent("R_COHORT", programme="BTech-CSE", semester=2)
    students = {"R_CLASH": s_clash, "R_COHORT": s_cohort}

    enrolments_by_course = {
        "UNSCHED_BIG": [StubEnrolment(f"R_u{i:03d}", "UNSCHED_BIG") for i in range(100)],
        "SUPP_LARGE": [StubEnrolment(f"R_sl{i:03d}", "SUPP_LARGE") for i in range(55)],
        "CORE_101": [StubEnrolment(f"R_c1_{i:03d}", "CORE_101") for i in range(48)]
        + [StubEnrolment("R_CLASH", "CORE_101"), StubEnrolment("R_COHORT", "CORE_101")],
        "CORE_102": [StubEnrolment(f"R_c2_{i:03d}", "CORE_102") for i in range(44)]
        + [StubEnrolment("R_COHORT", "CORE_102")],
        "CORE_GAP_FALLBACK": [StubEnrolment(f"R_cg_{i:03d}", "CORE_GAP_FALLBACK") for i in range(29)]
        + [StubEnrolment("R_COHORT", "CORE_GAP_FALLBACK")],
        "SUPP_SMALL": [StubEnrolment(f"R_ss{i:03d}", "SUPP_SMALL") for i in range(30)],
        "CLASH_STUDENT": [StubEnrolment("R_CLASH", "CLASH_STUDENT")]
        + [StubEnrolment(f"R_cs_{i:03d}", "CLASH_STUDENT") for i in range(19)],
        "SMALL_DEF": [StubEnrolment(f"R_sd{i:03d}", "SMALL_DEF") for i in range(5)],
    }

    registry = StubRegistry(
        courses={
            "UNSCHED_BIG": c_unsched,
            "SUPP_LARGE": c_supp_l,
            "CORE_101": c_core1,
            "CORE_102": c_core2,
            "CORE_GAP_FALLBACK": c_core_gap,
            "SUPP_SMALL": c_supp_s,
            "CLASH_STUDENT": c_clash,
            "SMALL_DEF": c_small_def,
        },
        students=students,
        sessions=sessions,
        halls={"H1": hall},
        enrolments_by_course=enrolments_by_course,
    )

    # Custom packability checker to reject SMALL_DEF from all sessions
    def pack_checker(sess: Any, c_codes: Any, reg: Any, closed: Any = None) -> bool:
        return "SMALL_DEF" not in c_codes

    result = generate_timetable(registry, packability_checker=pack_checker)

    # Print the resulting timetable table for verification and report
    print("\n" + "=" * 105)
    print(f"{'Course Code':<18} | {'Enrol':<5} | {'Date':<10} | {'Slot':<4} | {'Status':<12} | {'Details'}")
    print("-" * 105)

    all_courses = [
        c_unsched,
        c_supp_l,
        c_core1,
        c_core2,
        c_core_gap,
        c_supp_s,
        c_clash,
        c_small_def,
    ]
    for c in all_courses:
        code = c.course_code
        enrol = len(enrolments_by_course[code])
        if code in result.assignments:
            assign = result.assignments[code]
            sess_obj = registry.sessions_by_id[assign.session_id]
            date_str = sess_obj.exam_date.isoformat()
            slot_str = str(getattr(sess_obj.slot, "value", sess_obj.slot))
            status = "SCHEDULED*" if assign.used_gap_soft_fallback else "SCHEDULED"
            details = "Pass 2 Soft Fallback" if assign.used_gap_soft_fallback else "Pass 1 Strict"
            print(f"{code:<18} | {enrol:<5} | {date_str:<10} | {slot_str:<4} | {status:<12} | {details}")
        elif c in result.deferred_courses:
            print(f"{code:<18} | {enrol:<5} | {'-':<10} | {'-':<4} | {'DEFERRED':<12} | Awaiting ALG-10 Small Merge Repair")
        else:
            viols = [v for v in result.violations if code in v.entity_ids]
            viol_msg = viols[0].code if viols else "UNSCHEDULED"
            print(f"{code:<18} | {enrol:<5} | {'-':<10} | {'-':<4} | {'UNSCHEDULED':<12} | {viol_msg}")
    print("=" * 105 + "\n")

    # Assertions on expected outcomes:
    # 1. UNSCHED_BIG exceeds 90 capacity everywhere -> UNSCHEDULED_COURSE violation
    assert "UNSCHED_BIG" not in result.assignments
    assert any(v.code == "UNSCHEDULED_COURSE" and "UNSCHED_BIG" in v.entity_ids for v in result.violations)

    # 2. SMALL_DEF (5 students) rejected by packability -> deferred_courses
    assert "SMALL_DEF" not in result.assignments
    assert c_small_def in result.deferred_courses

    # 3. CORE_101 scheduled in Day 1 FN (Dec 01)
    assert result.assignments["CORE_101"].session_id == "2025-12-01_FN"

    # 4. CORE_102 has core gap >= 2 days to CORE_101 -> Day 3 FN (Dec 03)
    assert result.assignments["CORE_102"].session_id == "2025-12-03_FN"

    # 5. CORE_GAP_FALLBACK cannot satisfy >= 2 day gap to both Dec 01 and Dec 03 in 3-day window!
    # In Pass 2, Day 1 and Day 3 clash with cohort student; thus scheduled on Day 2 FN with CORE_GAP_SOFT_VIOLATION!
    assert result.assignments["CORE_GAP_FALLBACK"].session_id == "2025-12-02_FN"
    assert result.assignments["CORE_GAP_FALLBACK"].used_gap_soft_fallback is True
    assert any(v.code == "CORE_GAP_SOFT_VIOLATION" and "CORE_GAP_FALLBACK" in v.entity_ids for v in result.violations)

    # 6. SUPP_LARGE (55 students > 50) -> FN in supplementary window (Dec 02 FN)
    assert result.assignments["SUPP_LARGE"].session_id == "2025-12-02_FN"

    # 7. SUPP_SMALL (30 students <= 50) -> AN in supplementary window (Dec 02 AN)
    assert "SUPP_SMALL" in result.assignments
    supp_s_sess = registry.sessions_by_id[result.assignments["SUPP_SMALL"].session_id]
    assert supp_s_sess.is_supplementary_window_date is True
    assert str(getattr(supp_s_sess.slot, "value", supp_s_sess.slot)) == "AN"

    # 8. CLASH_STUDENT cannot be on Day 1 (shares student with CORE_101) -> Day 2 AN
    assert "CLASH_STUDENT" in result.assignments
    assert result.assignments["CLASH_STUDENT"].session_id == "2025-12-02_AN"
