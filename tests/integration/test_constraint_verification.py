"""Integration tests for hard and soft scheduling constraints.

Verifies:
  - Hard Constraints:
    - Same-session student conflict prevention (BR-01, CN-07)
    - Same-day unconsented student conflict prevention (BR-01, CN-08)
    - Backlog consent exception permitting same-day FN+AN (AS-014)
    - Session 90% aggregate capacity ceiling integer floor arithmetic (BR-04, CN-11, AS-001)
    - Supplementary examination window & slot restrictions (BR-12, CN-28, EC-08, TC-085, TC-086)
    - Pluggable hall packability verification (CN-12, ALG-08)
    - Duplicate examination assignment prevention
  - Soft Constraints:
    - Pass 1 strict gap prioritization (choosing later compliant session over earlier non-compliant)
    - Pass 2 controlled core-gap relaxation emitting CORE_GAP_SOFT_VIOLATION (BR-02, CN-09)
    - No false-positive violation generation for valid gaps
    - Hard constraint non-relaxation guarantee during Pass 2
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from exam_engine.scheduling.scheduler import (
    ViolationCategory,
    generate_timetable,
)
from tests.integration.fixtures import (
    IntegrationCourse,
    IntegrationEnrolment,
    IntegrationExamSession,
    IntegrationHall,
    IntegrationRegistry,
    IntegrationStudent,
    SessionSlot,
    assert_hard_constraints_satisfied,
    generate_session_sequence,
)

# ---------------------------------------------------------------------------
# Hard Constraint Integration Tests
# ---------------------------------------------------------------------------


def test_same_session_student_conflict_strictly_prevented() -> None:
    """Multiple courses sharing a student are strictly forbidden from the same session (BR-01, CN-07)."""
    sessions = (
        IntegrationExamSession("S1_FN", 0, date(2025, 12, 1), SessionSlot.FN),
        IntegrationExamSession("S1_AN", 1, date(2025, 12, 1), SessionSlot.AN),
        IntegrationExamSession("S2_FN", 2, date(2025, 12, 2), SessionSlot.FN),
    )

    c1 = IntegrationCourse("C1", credits=3, department="CSE")
    c2 = IntegrationCourse("C2", credits=3, department="ECE")

    # Student R_CLASH takes both C1 and C2 (no backlog consent)
    reg = IntegrationRegistry(
        courses={"C1": c1, "C2": c2},
        students={"R_CLASH": IntegrationStudent("R_CLASH", backlog_consent=False)},
        sessions=sessions,
        halls={"H1": IntegrationHall("H1", capacity=100)},
        enrolments_by_course={
            "C1": [IntegrationEnrolment("R_CLASH", "C1")],
            "C2": [IntegrationEnrolment("R_CLASH", "C2")],
        },
    )

    result = generate_timetable(reg)

    assert "C1" in result.assignments
    assert "C2" in result.assignments
    # C1 in S1_FN, C2 cannot be in S1_FN (same session) or S1_AN (same day) -> must be in S2_FN
    assert result.assignments["C1"].session_id == "S1_FN"
    assert result.assignments["C2"].session_id == "S2_FN"

    assert_hard_constraints_satisfied(result, reg)


def test_same_day_unconsented_student_conflict_strictly_prevented() -> None:
    """Student without backlog consent taking two courses cannot have both on the same day (BR-01, CN-08)."""
    sessions = (
        IntegrationExamSession("S1_FN", 0, date(2025, 12, 1), SessionSlot.FN),
        IntegrationExamSession("S1_AN", 1, date(2025, 12, 1), SessionSlot.AN),
        IntegrationExamSession("S2_FN", 2, date(2025, 12, 2), SessionSlot.FN),
    )

    c_reg1 = IntegrationCourse("REG1", credits=3, department="CSE")
    c_reg2 = IntegrationCourse("REG2", credits=3, department="CSE")

    reg = IntegrationRegistry(
        courses={"REG1": c_reg1, "REG2": c_reg2},
        students={"STU_NOCONSENT": IntegrationStudent("STU_NOCONSENT", backlog_consent=False)},
        sessions=sessions,
        halls={"H1": IntegrationHall("H1", capacity=100)},
        enrolments_by_course={
            "REG1": [IntegrationEnrolment("STU_NOCONSENT", "REG1")],
            "REG2": [IntegrationEnrolment("STU_NOCONSENT", "REG2")],
        },
    )

    result = generate_timetable(reg)

    d1 = reg.sessions_by_id[result.assignments["REG1"].session_id].exam_date
    d2 = reg.sessions_by_id[result.assignments["REG2"].session_id].exam_date
    assert d1 != d2, f"Both exams scheduled on same date {d1} without backlog consent!"

    assert_hard_constraints_satisfied(result, reg)


def test_backlog_consent_permits_same_day_different_sessions() -> None:
    """Student with valid backlog consent is permitted 2 exams on the same date (FN and AN) (AS-014)."""
    sessions = (
        IntegrationExamSession("S1_FN", 0, date(2025, 12, 1), SessionSlot.FN),
        IntegrationExamSession("S1_AN", 1, date(2025, 12, 1), SessionSlot.AN),
        IntegrationExamSession("S2_FN", 2, date(2025, 12, 2), SessionSlot.FN),
    )

    c_reg = IntegrationCourse("C_REG", credits=3, department="CSE")
    c_backlog = IntegrationCourse("C_BACK", credits=3, department="CSE")

    reg = IntegrationRegistry(
        courses={"C_REG": c_reg, "C_BACK": c_backlog},
        students={"STU_CONSENT": IntegrationStudent("STU_CONSENT", backlog_consent=True)},
        sessions=sessions,
        halls={"H1": IntegrationHall("H1", capacity=100)},
        enrolments_by_course={
            "C_REG": [IntegrationEnrolment("STU_CONSENT", "C_REG", is_backlog=False)],
            "C_BACK": [IntegrationEnrolment("STU_CONSENT", "C_BACK", is_backlog=True)],
        },
    )

    result = generate_timetable(reg)

    # Both courses should sit on Day 1 (one in FN, one in AN)
    s1 = result.assignments["C_REG"].session_id
    s2 = result.assignments["C_BACK"].session_id
    assert {s1, s2} == {"S1_FN", "S1_AN"}

    assert_hard_constraints_satisfied(result, reg)


def test_session_capacity_ceiling_strictly_enforced() -> None:
    """Session capacity 90% floor division is strictly enforced across all placements (BR-04, CN-11)."""
    # Hall capacity 100 -> cap_90 = (90 * 100) // 100 = 90
    sessions = (
        IntegrationExamSession("S1_FN", 0, date(2025, 12, 1), SessionSlot.FN),
        IntegrationExamSession("S1_AN", 1, date(2025, 12, 1), SessionSlot.AN),
    )

    c1 = IntegrationCourse("C1", credits=3, department="CSE")
    c2 = IntegrationCourse("C2", credits=3, department="ECE")

    # C1 has 85 students, C2 has 10 students. 85 + 10 = 95 > 90 -> cannot share S1_FN!
    reg = IntegrationRegistry(
        courses={"C1": c1, "C2": c2},
        sessions=sessions,
        halls={"H1": IntegrationHall("H1", capacity=100)},
        enrolments_by_course={
            "C1": [IntegrationEnrolment(f"S1_{i:03d}", "C1") for i in range(85)],
            "C2": [IntegrationEnrolment(f"S2_{i:03d}", "C2") for i in range(10)],
        },
    )

    result = generate_timetable(reg)

    # C1 takes S1_FN (85 <= 90), C2 overflows to S1_AN (10 <= 90)
    assert result.assignments["C1"].session_id == "S1_FN"
    assert result.assignments["C2"].session_id == "S1_AN"

    assert_hard_constraints_satisfied(result, reg)


def test_supplementary_window_and_an_restriction_enforced() -> None:
    """Supplementary courses with <= 50 students are strictly confined to AN in supp window (BR-12, CN-28)."""
    sessions = generate_session_sequence(date(2025, 12, 1), num_days=5, supp_window_days=2)

    c_supp_small = IntegrationCourse("SUPP_S", credits=3, is_supplementary=True)

    reg = IntegrationRegistry(
        courses={"SUPP_S": c_supp_small},
        sessions=sessions,
        halls={"H1": IntegrationHall("H1", capacity=100)},
        enrolments_by_course={
            "SUPP_S": [IntegrationEnrolment(f"S_{i:03d}", "SUPP_S", is_backlog=True) for i in range(30)],
        },
    )

    result = generate_timetable(reg)

    assigned_sess = reg.sessions_by_id[result.assignments["SUPP_S"].session_id]
    assert assigned_sess.is_supplementary_window_date is True
    assert assigned_sess.slot == SessionSlot.AN

    assert_hard_constraints_satisfied(result, reg)


def test_supplementary_large_enrollment_allows_fn_in_window() -> None:
    """Supplementary courses with > 50 students unlock FN slot within supp window (EC-08, TC-086)."""
    sessions = generate_session_sequence(date(2025, 12, 1), num_days=5, supp_window_days=2)

    # 55 students > 50
    c_supp_large = IntegrationCourse("SUPP_L", credits=3, is_supplementary=True)

    reg = IntegrationRegistry(
        courses={"SUPP_L": c_supp_large},
        sessions=sessions,
        halls={"H1": IntegrationHall("H1", capacity=100)},
        enrolments_by_course={
            "SUPP_L": [IntegrationEnrolment(f"S_{i:03d}", "SUPP_L", is_backlog=True) for i in range(55)],
        },
    )

    result = generate_timetable(reg)

    # Earliest supp session is Day 4 FN (index 6, 2025-12-04_FN)
    assigned_sess = reg.sessions_by_id[result.assignments["SUPP_L"].session_id]
    assert assigned_sess.is_supplementary_window_date is True
    assert assigned_sess.slot == SessionSlot.FN

    assert_hard_constraints_satisfied(result, reg)


def test_hall_packability_checker_rejection_strictly_enforced() -> None:
    """Rejection by pluggable HallPackabilityChecker prevents placement and advances search (ALG-08)."""
    sessions = (
        IntegrationExamSession("S1_FN", 0, date(2025, 12, 1), SessionSlot.FN),
        IntegrationExamSession("S1_AN", 1, date(2025, 12, 1), SessionSlot.AN),
    )

    c = IntegrationCourse("COURSE_A", credits=3)
    reg = IntegrationRegistry(
        courses={"COURSE_A": c},
        sessions=sessions,
        halls={"H1": IntegrationHall("H1", capacity=100)},
        enrolments_by_course={"COURSE_A": [IntegrationEnrolment("S1", "COURSE_A")]},
    )

    # Checker rejects COURSE_A from S1_FN
    def pack_checker(sess: Any, c_codes: Any, r: Any, closed: Any = None) -> bool:
        return not (sess.session_id == "S1_FN" and "COURSE_A" in c_codes)

    result = generate_timetable(reg, packability_checker=pack_checker)

    # Forced to S1_AN
    assert result.assignments["COURSE_A"].session_id == "S1_AN"
    assert_hard_constraints_satisfied(result, reg)


# ---------------------------------------------------------------------------
# Soft Constraint Integration Tests
# ---------------------------------------------------------------------------


def test_core_course_gap_pass1_strict_precedence_over_pass2() -> None:
    """Pass 1 prioritizes a later strictly gap-compliant session over an earlier non-compliant session (BR-02)."""
    # 3 examination dates: Dec 01, Dec 02, Dec 03
    sessions = (
        IntegrationExamSession("2025-12-01_FN", 0, date(2025, 12, 1), SessionSlot.FN),
        IntegrationExamSession("2025-12-02_FN", 1, date(2025, 12, 2), SessionSlot.FN),
        IntegrationExamSession("2025-12-03_FN", 2, date(2025, 12, 3), SessionSlot.FN),
    )

    # Two core courses in same programme-semester (4 credits each)
    core1 = IntegrationCourse("CORE1", credits=4, department="CSE", semester=1)
    core2 = IntegrationCourse("CORE2", credits=4, department="CSE", semester=1)

    reg = IntegrationRegistry(
        courses={"CORE1": core1, "CORE2": core2},
        sessions=sessions,
        halls={"H1": IntegrationHall("H1", capacity=100)},
        enrolments_by_course={
            "CORE1": [IntegrationEnrolment(f"S1_{i:03d}", "CORE1") for i in range(20)],
            "CORE2": [IntegrationEnrolment(f"S2_{i:03d}", "CORE2") for i in range(20)],
        },
    )

    result = generate_timetable(reg)

    # CORE1 placed in Dec 01 FN.
    # Dec 02 FN is earlier, but |Dec 02 - Dec 01| = 1 < 2 days.
    # Dec 03 FN is strictly compliant: |Dec 03 - Dec 01| = 2 >= 2 days.
    # CORE2 MUST choose Dec 03 FN in Pass 1 rather than falling back to Dec 02 FN!
    assert result.assignments["CORE1"].session_id == "2025-12-01_FN"
    assert result.assignments["CORE2"].session_id == "2025-12-03_FN"
    assert result.assignments["CORE2"].used_gap_soft_fallback is False
    assert result.violations == []

    assert_hard_constraints_satisfied(result, reg)


def test_core_course_gap_pass2_controlled_relaxation_logs_soft_violation() -> None:
    """When exam window is too short for >= 2 day gap, Pass 2 relaxes gap and records violation (EC-01)."""
    # Only 2 examination dates exist: Dec 01 and Dec 02
    sessions = (
        IntegrationExamSession("2025-12-01_FN", 0, date(2025, 12, 1), SessionSlot.FN),
        IntegrationExamSession("2025-12-02_FN", 1, date(2025, 12, 2), SessionSlot.FN),
    )

    # Two core courses taken by the same cohort students
    core1 = IntegrationCourse("CORE1", credits=4, department="CSE", semester=1)
    core2 = IntegrationCourse("CORE2", credits=4, department="CSE", semester=1)

    reg = IntegrationRegistry(
        courses={"CORE1": core1, "CORE2": core2},
        sessions=sessions,
        halls={"H1": IntegrationHall("H1", capacity=100)},
        enrolments_by_course={
            "CORE1": [IntegrationEnrolment(f"S_{i:03d}", "CORE1") for i in range(20)],
            "CORE2": [IntegrationEnrolment(f"S_{i:03d}", "CORE2") for i in range(20)],
        },
    )

    result = generate_timetable(reg)

    # CORE1 in Dec 01 FN. CORE2 cannot find >= 2 day gap in Pass 1.
    # On Dec 01 FN, CORE2 has student clash with CORE1.
    # Takes Dec 02 FN in Pass 2 with CORE_GAP_SOFT_VIOLATION!
    assert result.assignments["CORE1"].session_id == "2025-12-01_FN"
    assert result.assignments["CORE2"].session_id == "2025-12-02_FN"
    assert result.assignments["CORE2"].used_gap_soft_fallback is True

    assert len(result.violations) == 1
    viol = result.violations[0]
    assert viol.category == ViolationCategory.SOFT_VIOLATION
    assert viol.code == "CORE_GAP_SOFT_VIOLATION"
    assert viol.rule_id == "BR-02"
    assert "CORE2" in viol.entity_ids

    assert_hard_constraints_satisfied(result, reg)


def test_no_false_positive_soft_gap_violations() -> None:
    """Courses with < 4 credits (electives) never generate core-gap violations regardless of date adjacency."""
    sessions = (
        IntegrationExamSession("2025-12-01_FN", 0, date(2025, 12, 1), SessionSlot.FN),
        IntegrationExamSession("2025-12-02_FN", 1, date(2025, 12, 2), SessionSlot.FN),
    )

    # 3 credits each (non-core electives)
    elec1 = IntegrationCourse("ELEC1", credits=3, department="CSE", semester=1)
    elec2 = IntegrationCourse("ELEC2", credits=3, department="CSE", semester=1)

    reg = IntegrationRegistry(
        courses={"ELEC1": elec1, "ELEC2": elec2},
        sessions=sessions,
        halls={"H1": IntegrationHall("H1", capacity=100)},
        enrolments_by_course={
            "ELEC1": [IntegrationEnrolment(f"S1_{i:03d}", "ELEC1") for i in range(20)],
            "ELEC2": [IntegrationEnrolment(f"S2_{i:03d}", "ELEC2") for i in range(20)],
        },
    )

    result = generate_timetable(reg)

    assert result.assignments["ELEC1"].used_gap_soft_fallback is False
    assert result.assignments["ELEC2"].used_gap_soft_fallback is False
    assert result.violations == []


def test_core_gap_relaxation_never_relaxes_hard_constraints() -> None:
    """Pass 2 core-gap fallback never relaxes student clashes or session capacity ceilings (AS-006)."""
    sessions = (
        IntegrationExamSession("2025-12-01_FN", 0, date(2025, 12, 1), SessionSlot.FN),
        IntegrationExamSession("2025-12-02_FN", 1, date(2025, 12, 2), SessionSlot.FN),
    )

    # Core course with shared student
    core1 = IntegrationCourse("CORE1", credits=4, department="CSE", semester=1)
    core2 = IntegrationCourse("CORE2", credits=4, department="CSE", semester=1)

    # Student R_CLASH takes both CORE1 and CORE2 without backlog consent
    reg = IntegrationRegistry(
        courses={"CORE1": core1, "CORE2": core2},
        students={"R_CLASH": IntegrationStudent("R_CLASH", backlog_consent=False)},
        sessions=sessions,
        halls={"H1": IntegrationHall("H1", capacity=100)},
        enrolments_by_course={
            "CORE1": [IntegrationEnrolment("R_CLASH", "CORE1")],
            "CORE2": [IntegrationEnrolment("R_CLASH", "CORE2")],
        },
    )

    result = generate_timetable(reg)

    # CORE1 in Dec 01 FN. CORE2 clashes same-day if placed on Dec 01, but Dec 02 is fine for clashes.
    # In Dec 02, CORE2 has core-gap violation with CORE1, so takes Pass 2 on Dec 02 FN.
    assert result.assignments["CORE1"].session_id == "2025-12-01_FN"
    assert result.assignments["CORE2"].session_id == "2025-12-02_FN"

    assert_hard_constraints_satisfied(result, reg)
