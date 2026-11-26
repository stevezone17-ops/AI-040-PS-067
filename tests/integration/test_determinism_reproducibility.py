"""Integration tests for determinism, stability, and input-order independence.

Verifies:
  - Repeated executions with identical inputs produce bit-for-bit identical schedules
  - Shuffled course catalog insertion order produces identical assignments
  - Shuffled student registration order produces identical conflict graphs and schedules
  - Shuffled enrolment records produce identical course ordering and schedules
  - Stable violation ordering
  - Stable deferred-course ordering
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from exam_engine.scheduling.scheduler import generate_timetable
from tests.integration.fixtures import (
    IntegrationRegistry,
    assert_hard_constraints_satisfied,
    build_scenario_a_small,
    build_scenario_b_medium,
)


def test_repeated_execution_is_strictly_idempotent() -> None:
    """Repeated calls to generate_timetable on the same registry produce identical output."""
    reg = build_scenario_a_small(seed=42)

    res1 = generate_timetable(reg, repair_small_courses=True)
    res2 = generate_timetable(reg, repair_small_courses=True)

    assert res1.assignments == res2.assignments
    assert res1.session_courses == res2.session_courses
    assert res1.violations == res2.violations
    assert res1.deferred_courses == res2.deferred_courses


def test_course_dictionary_insertion_order_invariance() -> None:
    """Permuting the insertion order of courses in the registry produces identical timetable."""
    base_reg = build_scenario_a_small(seed=42)
    course_items = list(base_reg.courses.items())

    # Generate 5 randomized permutations of course catalog
    rng = random.Random(12345)
    base_result = generate_timetable(base_reg, repair_small_courses=True)

    for i in range(5):
        shuffled_items = list(course_items)
        rng.shuffle(shuffled_items)
        shuffled_courses = dict(shuffled_items)

        shuffled_reg = IntegrationRegistry(
            courses=shuffled_courses,
            students=base_reg.students,
            sessions=base_reg.sessions,
            halls=base_reg.halls,
            enrolments_by_course=base_reg.enrolments_by_course,
        )

        perm_result = generate_timetable(shuffled_reg, repair_small_courses=True)

        assert perm_result.assignments == base_result.assignments, (
            f"Course permutation {i} produced mismatched assignments!"
        )
        assert perm_result.session_courses == base_result.session_courses
        assert perm_result.violations == base_result.violations
        assert perm_result.deferred_courses == base_result.deferred_courses


def test_student_dictionary_insertion_order_invariance() -> None:
    """Permuting student dictionary insertion order produces identical timetable."""
    base_reg = build_scenario_a_small(seed=42)
    student_items = list(base_reg.students.items())

    rng = random.Random(54321)
    base_result = generate_timetable(base_reg, repair_small_courses=True)

    for i in range(3):
        shuffled_students = list(student_items)
        rng.shuffle(shuffled_students)

        shuffled_reg = IntegrationRegistry(
            courses=base_reg.courses,
            students=dict(shuffled_students),
            sessions=base_reg.sessions,
            halls=base_reg.halls,
            enrolments_by_course=base_reg.enrolments_by_course,
        )

        perm_result = generate_timetable(shuffled_reg, repair_small_courses=True)

        assert perm_result.assignments == base_result.assignments
        assert perm_result.session_courses == base_result.session_courses
        assert perm_result.violations == base_result.violations


def test_enrolment_record_order_invariance() -> None:
    """Shuffling enrolment record lists per course produces identical conflict graphs and timetable."""
    base_reg = build_scenario_b_medium(seed=101)
    base_result = generate_timetable(base_reg, repair_small_courses=True)

    rng = random.Random(999)
    shuffled_enrolments: dict[str, Any] = {}
    for code, enr_list in base_reg.enrolments_by_course.items():
        shuffled_list = list(enr_list)
        rng.shuffle(shuffled_list)
        shuffled_enrolments[code] = shuffled_list

    shuffled_reg = IntegrationRegistry(
        courses=base_reg.courses,
        students=base_reg.students,
        sessions=base_reg.sessions,
        halls=base_reg.halls,
        enrolments_by_course=shuffled_enrolments,
    )

    perm_result = generate_timetable(shuffled_reg, repair_small_courses=True)

    assert perm_result.assignments == base_result.assignments
    assert perm_result.session_courses == base_result.session_courses
    assert perm_result.violations == base_result.violations
    assert perm_result.deferred_courses == base_result.deferred_courses


def test_stable_violation_and_diagnostic_ordering() -> None:
    """Violation lists maintain deterministic ordering across repeated runs."""
    base_reg = build_scenario_a_small(seed=42)

    res1 = generate_timetable(base_reg, repair_small_courses=True)
    res2 = generate_timetable(base_reg, repair_small_courses=True)

    # Identical violation order and contents
    assert len(res1.violations) == len(res2.violations)
    for v1, v2 in zip(res1.violations, res2.violations):
        assert v1.violation_id == v2.violation_id
        assert v1.category == v2.category
        assert v1.code == v2.code
        assert v1.entity_ids == v2.entity_ids

    assert_hard_constraints_satisfied(res1, base_reg)
