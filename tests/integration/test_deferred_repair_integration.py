"""Integration tests for the deferred-course repair integration pathway (ALG-10).

Verifies:
  - Boundary cases: 1, 9 (eligible for deferral) vs 10 (not eligible) (EC-02)
  - Multiple deferred small courses paired deterministically
  - State integrity maintained when repair attempts are rejected
  - Correct final unscheduled-course diagnostic reporting
  - No duplicate assignments introduced by repair
  - Zero hard constraint violations introduced by repair
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
from exam_engine.scheduling.small_course_repair import (
    is_small_course_eligible,
    repair_deferred_courses,
)
from tests.integration.fixtures import (
    IntegrationCourse,
    IntegrationEnrolment,
    IntegrationExamSession,
    IntegrationHall,
    IntegrationRegistry,
    SessionSlot,
    assert_hard_constraints_satisfied,
    build_scenario_a_small,
)


def test_boundary_enrolment_one_and_nine_deferred_ten_not_deferred() -> None:
    """Courses with 1 and 9 students enter deferral; courses with 10 students do not (EC-02)."""
    sessions = (
        IntegrationExamSession("S1_FN", 0, date(2025, 12, 1), SessionSlot.FN),
    )
    # Zero available capacity to force all courses to fail Pass 1 and Pass 2
    hall = IntegrationHall("H0", capacity=0)

    c_one = IntegrationCourse("C_ONE", credits=3, department="CSE")
    c_nine = IntegrationCourse("C_NINE", credits=3, department="ECE")
    c_ten = IntegrationCourse("C_TEN", credits=3, department="MECH")

    reg = IntegrationRegistry(
        courses={"C_ONE": c_one, "C_NINE": c_nine, "C_TEN": c_ten},
        sessions=sessions,
        halls={"H0": hall},
        enrolments_by_course={
            "C_ONE": [IntegrationEnrolment("S1", "C_ONE")],
            "C_NINE": [IntegrationEnrolment(f"S9_{i}", "C_NINE") for i in range(9)],
            "C_TEN": [IntegrationEnrolment(f"S10_{i}", "C_TEN") for i in range(10)],
        },
    )

    # Pre-check eligibility function
    assert is_small_course_eligible(c_one, reg) is True
    assert is_small_course_eligible(c_nine, reg) is True
    assert is_small_course_eligible(c_ten, reg) is False

    # Execute timetable generation without repair flag
    result = generate_timetable(reg, repair_small_courses=False)

    # C_ONE and C_NINE enter deferred_courses
    deferred_codes = [c.course_code for c in result.deferred_courses]
    assert "C_ONE" in deferred_codes
    assert "C_NINE" in deferred_codes
    assert "C_TEN" not in deferred_codes

    # C_TEN must be immediately marked UNSCHEDULED_COURSE
    unsched_codes = [
        v.entity_ids[0]
        for v in result.violations
        if v.category == ViolationCategory.UNSCHEDULED_COURSE
    ]
    assert "C_TEN" in unsched_codes
    assert "C_ONE" not in unsched_codes
    assert "C_NINE" not in unsched_codes


def test_multiple_deferred_courses_repaired_across_sessions() -> None:
    """Multiple small courses are paired and repaired deterministically across sessions."""
    sessions = (
        IntegrationExamSession("S1_FN", 0, date(2025, 12, 1), SessionSlot.FN),
        IntegrationExamSession("S2_FN", 1, date(2025, 12, 2), SessionSlot.FN),
    )
    # Capacity 20 -> cap_90 = 18 seats per session
    hall = IntegrationHall("H1", capacity=20)

    # 4 small courses:
    # C1 (CSE, 8), C2 (ECE, 8) -> combined 16 <= 18 in S1_FN
    # C3 (MECH, 6), C4 (CIVIL, 4) -> combined 10 <= 18 in S2_FN
    c1 = IntegrationCourse("C1", credits=4, department="CSE", duration_hours=3)
    c2 = IntegrationCourse("C2", credits=3, department="ECE", duration_hours=3)
    c3 = IntegrationCourse("C3", credits=4, department="MECH", duration_hours=3)
    c4 = IntegrationCourse("C4", credits=3, department="CIVIL", duration_hours=3)

    # Pluggable checker: requires >= 2 courses in a session to pack
    def pair_pack_checker(s: Any, codes: Any, r: Any, closed: Any = None) -> bool:
        return len(codes) >= 2

    reg = IntegrationRegistry(
        courses={"C1": c1, "C2": c2, "C3": c3, "C4": c4},
        sessions=sessions,
        halls={"H1": hall},
        enrolments_by_course={
            "C1": [IntegrationEnrolment(f"S1_{i}", "C1") for i in range(8)],
            "C2": [IntegrationEnrolment(f"S2_{i}", "C2") for i in range(8)],
            "C3": [IntegrationEnrolment(f"S3_{i}", "C3") for i in range(6)],
            "C4": [IntegrationEnrolment(f"S4_{i}", "C4") for i in range(4)],
        },
    )

    # With repair_small_courses=True, all 4 courses should be co-scheduled as pairs
    result = generate_timetable(reg, packability_checker=pair_pack_checker, repair_small_courses=True)

    assert len(result.assignments) == 4
    assert result.deferred_courses == []
    # C1 and C2 pair in S1_FN (earliest session, combined 16 <= 18)
    assert result.assignments["C1"].session_id == "S1_FN"
    assert result.assignments["C2"].session_id == "S1_FN"
    # C3 and C4 pair in S2_FN (combined 10 <= 18)
    assert result.assignments["C3"].session_id == "S2_FN"
    assert result.assignments["C4"].session_id == "S2_FN"

    assert_hard_constraints_satisfied(result, reg)


def test_unsuccessful_repair_maintains_state_integrity() -> None:
    """When a small course cannot be repaired, existing assignments remain intact and diagnostic is emitted."""
    sessions = (
        IntegrationExamSession("S1_FN", 0, date(2025, 12, 1), SessionSlot.FN),
    )
    hall = IntegrationHall("H1", capacity=100)

    # Regular course already scheduled
    c_reg = IntegrationCourse("C_REG", credits=3, department="CSE", duration_hours=3)
    # Small course from SAME department (cannot merge with CSE under BR-05)
    c_small_same_dept = IntegrationCourse("C_SM_CSE", credits=3, department="CSE", duration_hours=3)

    reg = IntegrationRegistry(
        courses={"C_REG": c_reg, "C_SM_CSE": c_small_same_dept},
        sessions=sessions,
        halls={"H1": hall},
        enrolments_by_course={
            "C_REG": [IntegrationEnrolment(f"R_{i}", "C_REG") for i in range(30)],
            "C_SM_CSE": [IntegrationEnrolment(f"S_{i}", "C_SM_CSE") for i in range(5)],
        },
    )

    # Checker: requires >= 2 distinct departments
    def merge_pack_checker(s: Any, codes: Any, r: Any, closed: Any = None) -> bool:
        depts = {r.courses[code].department for code in codes}
        return len(depts) >= 2 or all(len(r.enrolments_by_course.get(c, [])) >= 10 for c in codes)

    result = generate_timetable(reg, packability_checker=merge_pack_checker, repair_small_courses=True)

    # C_REG assignment is intact
    assert "C_REG" in result.assignments
    assert result.assignments["C_REG"].session_id == "S1_FN"
    # C_SM_CSE could not be repaired
    assert "C_SM_CSE" not in result.assignments
    assert c_small_same_dept in result.deferred_courses

    # Diagnostic emitted
    unsched_viols = [
        v for v in result.violations
        if v.category == ViolationCategory.UNSCHEDULED_COURSE and "C_SM_CSE" in v.entity_ids
    ]
    assert len(unsched_viols) == 1
    assert unsched_viols[0].code == "UNSCHEDULED_COURSE"

    assert_hard_constraints_satisfied(result, reg)


def test_no_duplicate_assignments_after_repair() -> None:
    """Verify that multiple repair passes never assign a course more than once."""
    c_s1 = IntegrationCourse("C_S1", department="CSE", duration_hours=3)
    c_s2 = IntegrationCourse("C_S2", department="ECE", duration_hours=3)

    sess = IntegrationExamSession("S1_FN", 0, date(2025, 12, 1), SessionSlot.FN)
    hall = IntegrationHall("H1", capacity=100)

    reg = IntegrationRegistry(
        courses={"C_S1": c_s1, "C_S2": c_s2},
        sessions=(sess,),
        halls={"H1": hall},
        enrolments_by_course={
            "C_S1": [IntegrationEnrolment(f"S1_{i}", "C_S1") for i in range(5)],
            "C_S2": [IntegrationEnrolment(f"S2_{i}", "C_S2") for i in range(5)],
        },
    )

    assignments: dict[str, Any] = {}
    session_courses: dict[str, list[str]] = {"S1_FN": []}
    violations: list[Any] = []

    # Run repair pass
    res1 = repair_deferred_courses([c_s1, c_s2], assignments, session_courses, violations, reg)
    assert len(res1.repaired_courses) == 2

    # Attempt second repair pass on same list
    res2 = repair_deferred_courses([c_s1, c_s2], assignments, session_courses, violations, reg)
    # Already assigned courses should not be assigned again
    assert len(res2.repaired_courses) == 0
    assert session_courses["S1_FN"].count("C_S1") == 1
    assert session_courses["S1_FN"].count("C_S2") == 1


def test_scenario_a_small_course_repair_integration() -> None:
    """Scenario A small courses (SMALL_MEC and SMALL_CIV) are repaired cleanly without violations."""
    registry = build_scenario_a_small(seed=42)

    result = generate_timetable(registry, repair_small_courses=True)

    # Both SMALL_MEC (6 students) and SMALL_CIV (6 students) should be scheduled
    assert "SMALL_MEC" in result.assignments
    assert "SMALL_CIV" in result.assignments

    # Dual-oracle check
    assert_hard_constraints_satisfied(result, registry)
