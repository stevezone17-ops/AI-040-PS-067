"""Unit tests for ALG-07: Supplementary Examination Eligibility.

Covers:
  - BR-12: Supplementary examinations temporal constraint
  - CN-28: Hard Temporal Eligibility Constraint
  - EC-08: Final-day FN-only slot boundary
  - AS-015: Final three active examination dates definition
  - TC-085: 50 supplementary students (AN only)
  - TC-086: 51 supplementary students (FN and AN allowed)
  - TC-087: Holiday integration inside final calendar days
  - TC-088: Final day FN-only with <= 50 supplementary students
  - TC-089: Final day FN-only with > 50 supplementary students
  - Immutability of course and session entities
  - Integration with ALG-02 generated session metadata
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

from exam_engine.scheduling.session_generator import generate_sessions
from exam_engine.scheduling.supplementary import is_supplementary_eligible

# ---------------------------------------------------------------------------
# Test-only stubs
# ---------------------------------------------------------------------------


class StubSessionSlot(Enum):
    """Stub SessionSlot matching M1 domain enum."""

    FN = "FN"
    AN = "AN"


@dataclass(frozen=True)
class StubTimeInterval:
    """Stub TimeInterval matching M1 domain value object."""

    start_minute: int
    end_minute: int


@dataclass(frozen=True)
class StubCourse:
    """Minimal stub for domain.Course."""

    course_code: str
    is_supplementary: bool = False
    credits: int = 4
    department: str = "CSE"
    semester: int = 1
    duration_hours: int = 3


@dataclass(frozen=True)
class StubExamSession:
    """Minimal stub for domain.ExamSession."""

    session_id: str
    exam_date: date
    slot: Any  # StubSessionSlot or str
    is_supplementary_window_date: bool
    session_index: int = 0
    base_window: Any = None
    iso_week_key: tuple[int, int] = (2025, 50)


@dataclass(frozen=True)
class StubEnrolment:
    """Minimal stub for domain.Enrolment."""

    register_number: str
    course_code: str
    is_backlog: bool = False


@dataclass
class StubRegistry:
    """Minimal stub for domain.ProblemRegistry."""

    courses: dict[str, StubCourse] = field(default_factory=dict)
    enrolments_by_course: dict[str, list[StubEnrolment]] = field(
        default_factory=dict
    )
    enrolments_by_student: dict[str, list[StubEnrolment]] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class StubExamWindow:
    """Minimal stub for domain.ExamWindow."""

    start_date: date
    end_date: date
    holidays: tuple[date, ...] = ()
    closed_slots: tuple[tuple[date, Any], ...] = ()


def _make_registry(
    course: StubCourse, student_count: int
) -> StubRegistry:
    """Helper to create a registry with a specified student enrolment count."""
    enrolments = [
        StubEnrolment(f"REG_{i:03d}", course.course_code)
        for i in range(student_count)
    ]
    return StubRegistry(
        courses={course.course_code: course},
        enrolments_by_course={course.course_code: enrolments},
    )


# ---------------------------------------------------------------------------
# Scenario 1 to 4: Regular Courses
# ---------------------------------------------------------------------------


def test_regular_course_outside_supplementary_window() -> None:
    """Regular course (is_supplementary=False) is eligible outside supplementary window."""
    course = StubCourse("CS101", is_supplementary=False)
    session_fn = StubExamSession(
        "S1_FN", date(2025, 12, 1), StubSessionSlot.FN, is_supplementary_window_date=False
    )
    session_an = StubExamSession(
        "S1_AN", date(2025, 12, 1), StubSessionSlot.AN, is_supplementary_window_date=False
    )
    registry = _make_registry(course, 30)

    assert is_supplementary_eligible(course, session_fn, registry) is True
    assert is_supplementary_eligible(course, session_an, registry) is True


def test_regular_course_inside_supplementary_window() -> None:
    """Regular course is eligible inside supplementary window."""
    course = StubCourse("CS101", is_supplementary=False)
    session_fn = StubExamSession(
        "S10_FN", date(2025, 12, 10), StubSessionSlot.FN, is_supplementary_window_date=True
    )
    session_an = StubExamSession(
        "S10_AN", date(2025, 12, 10), StubSessionSlot.AN, is_supplementary_window_date=True
    )
    registry = _make_registry(course, 30)

    assert is_supplementary_eligible(course, session_fn, registry) is True
    assert is_supplementary_eligible(course, session_an, registry) is True


def test_regular_course_in_fn_session() -> None:
    """Regular course in FN session returns True regardless of enrolment count."""
    course = StubCourse("CS101", is_supplementary=False)
    session_fn = StubExamSession(
        "S5_FN", date(2025, 12, 5), StubSessionSlot.FN, is_supplementary_window_date=False
    )
    assert is_supplementary_eligible(course, session_fn, enrolment_count=10) is True
    assert is_supplementary_eligible(course, session_fn, enrolment_count=100) is True


def test_regular_course_in_an_session() -> None:
    """Regular course in AN session returns True regardless of enrolment count."""
    course = StubCourse("CS101", is_supplementary=False)
    session_an = StubExamSession(
        "S5_AN", date(2025, 12, 5), StubSessionSlot.AN, is_supplementary_window_date=False
    )
    assert is_supplementary_eligible(course, session_an, enrolment_count=10) is True
    assert is_supplementary_eligible(course, session_an, enrolment_count=100) is True


# ---------------------------------------------------------------------------
# Scenario 5: Supplementary Course Outside Supplementary Window
# ---------------------------------------------------------------------------


def test_supplementary_course_outside_supplementary_window() -> None:
    """Supplementary course outside the supplementary window is strictly rejected."""
    course = StubCourse("SUP101", is_supplementary=True)
    session_fn = StubExamSession(
        "S1_FN", date(2025, 12, 1), StubSessionSlot.FN, is_supplementary_window_date=False
    )
    session_an = StubExamSession(
        "S1_AN", date(2025, 12, 1), StubSessionSlot.AN, is_supplementary_window_date=False
    )

    # Regardless of enrolment count, must be False outside window
    for count in [0, 1, 49, 50, 51, 100]:
        assert is_supplementary_eligible(course, session_fn, enrolment_count=count) is False
        assert is_supplementary_eligible(course, session_an, enrolment_count=count) is False


# ---------------------------------------------------------------------------
# Scenarios 6 to 14: Enrolment Count Thresholds (<= 50 vs > 50)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("count", "expected_fn", "expected_an"),
    [
        (1, False, True),     # Scenario 6, 7: 1 student
        (49, False, True),    # Scenario 8, 9: 49 students
        (50, False, True),    # Scenario 10, 11: 50 students (TC-085 boundary)
        (51, True, True),     # Scenario 12, 13: 51 students (TC-086 boundary)
        (100, True, True),    # Scenario 14: 100 students
        (250, True, True),    # Large course
    ],
)
def test_supplementary_enrolment_thresholds(
    count: int, expected_fn: bool, expected_an: bool
) -> None:
    """Test student count boundaries inside supplementary window."""
    course = StubCourse("SUP_MATH", is_supplementary=True)
    session_fn = StubExamSession(
        "S8_FN", date(2025, 12, 8), StubSessionSlot.FN, is_supplementary_window_date=True
    )
    session_an = StubExamSession(
        "S8_AN", date(2025, 12, 8), StubSessionSlot.AN, is_supplementary_window_date=True
    )
    registry = _make_registry(course, count)

    assert is_supplementary_eligible(course, session_fn, registry) is expected_fn
    assert is_supplementary_eligible(course, session_an, registry) is expected_an


def test_tc_085_exact_50_students_an_only() -> None:
    """TC-085: Exactly 50 supplementary students -> AN only, FN rejected."""
    course = StubCourse("SUP50", is_supplementary=True)
    registry = _make_registry(course, 50)

    session_fn = StubExamSession(
        "S8_FN", date(2025, 12, 8), StubSessionSlot.FN, is_supplementary_window_date=True
    )
    session_an = StubExamSession(
        "S8_AN", date(2025, 12, 8), StubSessionSlot.AN, is_supplementary_window_date=True
    )

    assert is_supplementary_eligible(course, session_fn, registry) is False
    assert is_supplementary_eligible(course, session_an, registry) is True


def test_tc_086_exact_51_students_unlocks_fn() -> None:
    """TC-086: Exactly 51 supplementary students -> both FN and AN unlocked."""
    course = StubCourse("SUP51", is_supplementary=True)
    registry = _make_registry(course, 51)

    session_fn = StubExamSession(
        "S8_FN", date(2025, 12, 8), StubSessionSlot.FN, is_supplementary_window_date=True
    )
    session_an = StubExamSession(
        "S8_AN", date(2025, 12, 8), StubSessionSlot.AN, is_supplementary_window_date=True
    )

    assert is_supplementary_eligible(course, session_fn, registry) is True
    assert is_supplementary_eligible(course, session_an, registry) is True


# ---------------------------------------------------------------------------
# Scenarios 15 & 16: EC-08 Final-Day FN-Only
# ---------------------------------------------------------------------------


def test_ec_08_final_day_fn_only_with_50_students() -> None:
    """EC-08 / TC-088: Final day FN-only session with 50 students is ineligible."""
    course = StubCourse("SUP30", is_supplementary=True)
    registry = _make_registry(course, 50)

    # Final day session that only has FN
    final_day_fn = StubExamSession(
        "Day10_FN", date(2025, 12, 10), StubSessionSlot.FN, is_supplementary_window_date=True
    )

    assert is_supplementary_eligible(course, final_day_fn, registry) is False


def test_ec_08_final_day_fn_only_with_51_students() -> None:
    """EC-08 / TC-089: Final day FN-only session with 51 students is eligible."""
    course = StubCourse("SUP60", is_supplementary=True)
    registry = _make_registry(course, 51)

    final_day_fn = StubExamSession(
        "Day10_FN", date(2025, 12, 10), StubSessionSlot.FN, is_supplementary_window_date=True
    )

    assert is_supplementary_eligible(course, final_day_fn, registry) is True


# ---------------------------------------------------------------------------
# Scenarios 17 to 19: Date Boundaries in Active Window
# ---------------------------------------------------------------------------


def test_supplementary_course_on_first_and_final_eligible_active_dates() -> None:
    """Supplementary course tested on first and final active dates of the 3-day window."""
    course = StubCourse("SUP_HIST", is_supplementary=True)
    registry = _make_registry(course, 40)

    first_supp_date_an = StubExamSession(
        "Day8_AN", date(2025, 12, 8), StubSessionSlot.AN, is_supplementary_window_date=True
    )
    final_supp_date_an = StubExamSession(
        "Day10_AN", date(2025, 12, 10), StubSessionSlot.AN, is_supplementary_window_date=True
    )

    assert is_supplementary_eligible(course, first_supp_date_an, registry) is True
    assert is_supplementary_eligible(course, final_supp_date_an, registry) is True


def test_supplementary_course_immediately_before_eligible_window() -> None:
    """Supplementary course immediately before window (Day 7 of 10) is ineligible."""
    course = StubCourse("SUP_MATH", is_supplementary=True)
    registry = _make_registry(course, 100)  # Even with > 50 students

    day7_fn = StubExamSession(
        "Day7_FN", date(2025, 12, 7), StubSessionSlot.FN, is_supplementary_window_date=False
    )
    day7_an = StubExamSession(
        "Day7_AN", date(2025, 12, 7), StubSessionSlot.AN, is_supplementary_window_date=False
    )

    assert is_supplementary_eligible(course, day7_fn, registry) is False
    assert is_supplementary_eligible(course, day7_an, registry) is False


# ---------------------------------------------------------------------------
# Scenario 20: Compatibility with ALG-02 Generated Sessions
# ---------------------------------------------------------------------------


def test_compatibility_with_alg02_generated_session_metadata() -> None:
    """Direct end-to-end integration with ALG-02 generate_sessions output."""
    window = StubExamWindow(
        start_date=date(2025, 12, 1),
        end_date=date(2025, 12, 6),  # 6 days -> Days 4, 5, 6 are supplementary
    )
    sessions = generate_sessions(
        window,
        session_factory=StubExamSession,
        time_interval_factory=StubTimeInterval,
        slot_enum=StubSessionSlot,
    )

    course_supp_small = StubCourse("SUP_S", is_supplementary=True)
    course_supp_large = StubCourse("SUP_L", is_supplementary=True)
    course_regular = StubCourse("REG_1", is_supplementary=False)

    reg_small = _make_registry(course_supp_small, 30)
    reg_large = _make_registry(course_supp_large, 60)
    reg_regular = _make_registry(course_regular, 30)

    for sess in sessions:
        # Regular courses are always eligible
        assert is_supplementary_eligible(course_regular, sess, reg_regular) is True

        if sess.is_supplementary_window_date:
            slot_str = str(getattr(sess.slot, "value", sess.slot))
            if slot_str == "AN":
                assert is_supplementary_eligible(course_supp_small, sess, reg_small) is True
                assert is_supplementary_eligible(course_supp_large, sess, reg_large) is True
            elif slot_str == "FN":
                assert is_supplementary_eligible(course_supp_small, sess, reg_small) is False
                assert is_supplementary_eligible(course_supp_large, sess, reg_large) is True
        else:
            # Outside supplementary window
            assert is_supplementary_eligible(course_supp_small, sess, reg_small) is False
            assert is_supplementary_eligible(course_supp_large, sess, reg_large) is False


# ---------------------------------------------------------------------------
# Scenario 21: Windows with Fewer Than 3 Active Dates
# ---------------------------------------------------------------------------


def test_window_with_fewer_than_three_active_dates() -> None:
    """When window has only 2 active dates, all sessions are supplementary-eligible."""
    window = StubExamWindow(
        start_date=date(2025, 12, 1),
        end_date=date(2025, 12, 2),  # Only 2 days
    )
    sessions = generate_sessions(
        window,
        session_factory=StubExamSession,
        time_interval_factory=StubTimeInterval,
        slot_enum=StubSessionSlot,
    )

    course_supp = StubCourse("SUP_SHORT", is_supplementary=True)
    registry = _make_registry(course_supp, 40)

    # Every session generated has is_supplementary_window_date=True
    for sess in sessions:
        assert sess.is_supplementary_window_date is True
        slot_str = str(getattr(sess.slot, "value", sess.slot))
        if slot_str == "AN":
            assert is_supplementary_eligible(course_supp, sess, registry) is True
        else:
            assert is_supplementary_eligible(course_supp, sess, registry) is False


# ---------------------------------------------------------------------------
# Scenario 22: Holiday and Closed-Slot Integration Behavior (TC-087)
# ---------------------------------------------------------------------------


def test_tc_087_holiday_inside_final_calendar_days() -> None:
    """TC-087: Window Dec 1-6 with holiday on Dec 5.

    Active dates: Dec 1, 2, 3, 4, 6.
    Final 3 active dates: Dec 3, Dec 4, Dec 6.
    Dec 3 AN must be supplementary eligible!
    """
    window = StubExamWindow(
        start_date=date(2025, 12, 1),
        end_date=date(2025, 12, 6),
        holidays=(date(2025, 12, 5),),
    )
    sessions = generate_sessions(
        window,
        session_factory=StubExamSession,
        time_interval_factory=StubTimeInterval,
        slot_enum=StubSessionSlot,
    )

    course = StubCourse("SUP_HOL", is_supplementary=True)
    registry = _make_registry(course, 40)

    # Find session for Dec 3 AN
    dec3_an = next(
        s for s in sessions if s.exam_date == date(2025, 12, 3) and str(getattr(s.slot, "value", s.slot)) == "AN"
    )
    assert dec3_an.is_supplementary_window_date is True
    assert is_supplementary_eligible(course, dec3_an, registry) is True

    # Dec 2 is outside final 3 active dates -> False
    dec2_an = next(
        s for s in sessions if s.exam_date == date(2025, 12, 2) and str(getattr(s.slot, "value", s.slot)) == "AN"
    )
    assert dec2_an.is_supplementary_window_date is False
    assert is_supplementary_eligible(course, dec2_an, registry) is False


# ---------------------------------------------------------------------------
# Scenario 23: Deterministic Results Across Repeated Calls
# ---------------------------------------------------------------------------


def test_deterministic_across_repeated_calls() -> None:
    """Repeated calls with identical arguments yield identical boolean results."""
    course = StubCourse("SUP_DET", is_supplementary=True)
    session = StubExamSession(
        "S9_AN", date(2025, 12, 9), StubSessionSlot.AN, is_supplementary_window_date=True
    )
    registry = _make_registry(course, 45)

    res1 = is_supplementary_eligible(course, session, registry)
    res2 = is_supplementary_eligible(course, session, registry)
    res3 = is_supplementary_eligible(course, session, registry)

    assert res1 is True
    assert res1 == res2 == res3


# ---------------------------------------------------------------------------
# Scenario 24: Immutability of Course and Session Objects
# ---------------------------------------------------------------------------


def test_course_and_session_objects_remain_unchanged() -> None:
    """Calling is_supplementary_eligible does not mutate inputs."""
    course = StubCourse("SUP_IMMUT", is_supplementary=True, credits=4, department="CSE")
    session = StubExamSession(
        "S9_FN", date(2025, 12, 9), StubSessionSlot.FN, is_supplementary_window_date=True
    )
    registry = _make_registry(course, 50)

    _ = is_supplementary_eligible(course, session, registry)

    assert course.course_code == "SUP_IMMUT"
    assert course.is_supplementary is True
    assert course.credits == 4
    assert course.department == "CSE"

    assert session.session_id == "S9_FN"
    assert session.exam_date == date(2025, 12, 9)
    assert session.slot == StubSessionSlot.FN
    assert session.is_supplementary_window_date is True


# ---------------------------------------------------------------------------
# Scenario 25: Zero-Enrolment Course Behavior
# ---------------------------------------------------------------------------


def test_zero_enrolment_supplementary_course() -> None:
    """Zero-enrolment supplementary course: 0 <= 50 -> AN only, FN rejected."""
    course = StubCourse("SUP_ZERO", is_supplementary=True)
    registry = _make_registry(course, 0)

    session_fn = StubExamSession(
        "S9_FN", date(2025, 12, 9), StubSessionSlot.FN, is_supplementary_window_date=True
    )
    session_an = StubExamSession(
        "S9_AN", date(2025, 12, 9), StubSessionSlot.AN, is_supplementary_window_date=True
    )

    assert is_supplementary_eligible(course, session_fn, registry) is False
    assert is_supplementary_eligible(course, session_an, registry) is True


# ---------------------------------------------------------------------------
# Enrolment Fallback & String Slot Compatibility
# ---------------------------------------------------------------------------


def test_fallback_enrolments_by_student() -> None:
    """When enrolments_by_course is absent, derives count from enrolments_by_student."""
    course = StubCourse("SUP_STUD", is_supplementary=True)

    class StudentRegistry:
        def __init__(self) -> None:
            self.enrolments_by_student = {
                f"S{i}": [StubEnrolment(f"S{i}", "SUP_STUD")] for i in range(55)
            }

    session_fn = StubExamSession(
        "S9_FN", date(2025, 12, 9), StubSessionSlot.FN, is_supplementary_window_date=True
    )
    # 55 students > 50 -> FN eligible
    assert is_supplementary_eligible(course, session_fn, StudentRegistry()) is True


def test_string_slot_compatibility() -> None:
    """Supports plain string slots 'FN', 'AN', 'fn', 'an'."""
    course = StubCourse("SUP_STR", is_supplementary=True)

    sess_fn_str = StubExamSession("S_FN", date(2025, 12, 9), "FN", True)
    sess_an_str = StubExamSession("S_AN", date(2025, 12, 9), "an", True)

    assert is_supplementary_eligible(course, sess_fn_str, enrolment_count=30) is False
    assert is_supplementary_eligible(course, sess_an_str, enrolment_count=30) is True

    assert is_supplementary_eligible(course, sess_fn_str, enrolment_count=60) is True
    assert is_supplementary_eligible(course, sess_an_str, enrolment_count=60) is True
