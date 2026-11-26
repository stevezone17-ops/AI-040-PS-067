"""Integration and scalability benchmark tests across realistic examination datasets.

Benchmarks:
  - Scenario A: Small examination dataset (10 courses, 50 students, 5 dates, 10 sessions)
  - Scenario B: Medium examination dataset (30 courses, 300 students, 10 dates, 20 sessions)
  - Scenario C: Large examination dataset (100 courses, 1000 students, 15 dates, 30 sessions)
  - Scenario D: Deliberately infeasible examination dataset (unplaced courses & diagnostics)

Measures and asserts:
  - Wall-clock runtime via time.perf_counter
  - Peak memory allocation via tracemalloc
  - Hard constraint compliance via independent dual-oracle assertions
  - Diagnostic generation and state integrity
"""

from __future__ import annotations

import sys
import time
import tracemalloc
from dataclasses import dataclass
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
    assert_hard_constraints_satisfied,
    build_scenario_a_small,
    build_scenario_b_medium,
    build_scenario_c_large,
    build_scenario_d_infeasible,
)


@dataclass
class BenchmarkMetrics:
    """Performance and scheduling outcome record."""

    scenario_name: str
    num_courses: int
    num_students: int
    num_enrolments: int
    num_sessions: int
    scheduled_courses: int
    deferred_courses: int
    repaired_courses: int
    unscheduled_courses: int
    soft_violations: int
    execution_time_sec: float
    peak_memory_mb: float


def test_scenario_a_small_benchmark() -> None:
    """Benchmark Scenario A (Small dataset: 10 courses, 50 students)."""
    reg = build_scenario_a_small(seed=42)
    total_enrolments = sum(len(e) for e in reg.enrolments_by_course.values())

    tracemalloc.start()
    t0 = time.perf_counter()
    result = generate_timetable(reg, repair_small_courses=True)
    t1 = time.perf_counter()
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    duration = t1 - t0
    peak_mb = peak_bytes / (1024 * 1024)

    scheduled = len(result.assignments)
    unscheduled = sum(
        1 for v in result.violations if v.category == ViolationCategory.UNSCHEDULED_COURSE
    )
    soft_viols = sum(
        1 for v in result.violations if v.category == ViolationCategory.SOFT_VIOLATION
    )

    metrics = BenchmarkMetrics(
        scenario_name="Scenario A (Small)",
        num_courses=len(reg.courses),
        num_students=len(reg.students),
        num_enrolments=total_enrolments,
        num_sessions=len(reg.sessions),
        scheduled_courses=scheduled,
        deferred_courses=len(result.deferred_courses),
        repaired_courses=2,  # SMALL_MEC and SMALL_CIV were repaired
        unscheduled_courses=unscheduled,
        soft_violations=soft_viols,
        execution_time_sec=duration,
        peak_memory_mb=peak_mb,
    )

    print(f"\n[BENCHMARK] {metrics.scenario_name}: {duration * 1000:.2f} ms, Peak RAM: {peak_mb:.2f} MB")
    print(f"  Scheduled: {scheduled}/{len(reg.courses)}, Soft Viols: {soft_viols}, Unscheduled: {unscheduled}")

    # Invariants
    assert scheduled == 10
    assert unscheduled == 0
    assert duration < 1.0, f"Scenario A took too long: {duration:.3f} s"
    assert_hard_constraints_satisfied(result, reg)


def test_scenario_b_medium_benchmark() -> None:
    """Benchmark Scenario B (Medium dataset: 30 courses, 300 students, 20 sessions)."""
    reg = build_scenario_b_medium(seed=101)
    total_enrolments = sum(len(e) for e in reg.enrolments_by_course.values())

    tracemalloc.start()
    t0 = time.perf_counter()
    result = generate_timetable(reg, repair_small_courses=True)
    t1 = time.perf_counter()
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    duration = t1 - t0
    peak_mb = peak_bytes / (1024 * 1024)

    scheduled = len(result.assignments)
    unscheduled = sum(
        1 for v in result.violations if v.category == ViolationCategory.UNSCHEDULED_COURSE
    )
    soft_viols = sum(
        1 for v in result.violations if v.category == ViolationCategory.SOFT_VIOLATION
    )

    metrics = BenchmarkMetrics(
        scenario_name="Scenario B (Medium)",
        num_courses=len(reg.courses),
        num_students=len(reg.students),
        num_enrolments=total_enrolments,
        num_sessions=len(reg.sessions),
        scheduled_courses=scheduled,
        deferred_courses=len(result.deferred_courses),
        repaired_courses=0,
        unscheduled_courses=unscheduled,
        soft_violations=soft_viols,
        execution_time_sec=duration,
        peak_memory_mb=peak_mb,
    )

    print(f"\n[BENCHMARK] {metrics.scenario_name}: {duration * 1000:.2f} ms, Peak RAM: {peak_mb:.2f} MB")
    print(f"  Scheduled: {scheduled}/{len(reg.courses)}, Soft Viols: {soft_viols}, Unscheduled: {unscheduled}")

    # Medium dataset should complete in < 2.0s
    assert duration < 2.0, f"Scenario B took too long: {duration:.3f} s"
    assert scheduled > 0
    assert scheduled + unscheduled == len(reg.courses)
    assert_hard_constraints_satisfied(result, reg)


def test_scenario_c_large_benchmark() -> None:
    """Benchmark Scenario C (Large dataset: 100 courses, 1,000 students, 30 sessions)."""
    reg = build_scenario_c_large(seed=777)
    total_enrolments = sum(len(e) for e in reg.enrolments_by_course.values())

    tracemalloc.start()
    t0 = time.perf_counter()
    result = generate_timetable(reg, repair_small_courses=True)
    t1 = time.perf_counter()
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    duration = t1 - t0
    peak_mb = peak_bytes / (1024 * 1024)

    scheduled = len(result.assignments)
    unscheduled = sum(
        1 for v in result.violations if v.category == ViolationCategory.UNSCHEDULED_COURSE
    )
    soft_viols = sum(
        1 for v in result.violations if v.category == ViolationCategory.SOFT_VIOLATION
    )

    metrics = BenchmarkMetrics(
        scenario_name="Scenario C (Large)",
        num_courses=len(reg.courses),
        num_students=len(reg.students),
        num_enrolments=total_enrolments,
        num_sessions=len(reg.sessions),
        scheduled_courses=scheduled,
        deferred_courses=len(result.deferred_courses),
        repaired_courses=0,
        unscheduled_courses=unscheduled,
        soft_violations=soft_viols,
        execution_time_sec=duration,
        peak_memory_mb=peak_mb,
    )

    print(f"\n[BENCHMARK] {metrics.scenario_name}: {duration * 1000:.2f} ms, Peak RAM: {peak_mb:.2f} MB")
    print(f"  Scheduled: {scheduled}/{len(reg.courses)}, Soft Viols: {soft_viols}, Unscheduled: {unscheduled}")

    # Large dataset (100 courses, 1000 students) should finish comfortably in < 5.0s
    assert duration < 5.0, f"Scenario C took too long: {duration:.3f} s"
    assert scheduled > 0
    assert scheduled + unscheduled == len(reg.courses)
    assert_hard_constraints_satisfied(result, reg)


def test_scenario_d_deliberately_infeasible_verification() -> None:
    """Scenario D: Infeasible dataset correctly reports diagnostics without crashing or relaxing rules."""
    reg = build_scenario_d_infeasible()

    # Under BR-05, small courses (<10) require a multi-department pairing partner to be packable
    def br05_partner_packability_checker(
        sess: Any, c_codes: Any, r: Any, closed: Any = None
    ) -> bool:
        small_codes = [c for c in c_codes if len(r.enrolments_by_course.get(c, [])) < 10]
        if not small_codes:
            return True
        depts = {r.courses[c].department for c in c_codes}
        return len(depts) >= 2

    result = generate_timetable(
        reg,
        packability_checker=br05_partner_packability_checker,
        repair_small_courses=True,
    )

    # In Scenario D:
    # OVERFLOW_100 (100 students) cannot fit in SMALL_HALL (capacity 80 -> cap_90 = 72)
    # ISOLATED_SMALL (5 students, CSE) has no other departments to merge with
    assert "OVERFLOW_100" not in result.assignments
    assert "ISOLATED_SMALL" not in result.assignments

    # Both courses must have UNSCHEDULED_COURSE violations
    unsched_viols = [
        v for v in result.violations if v.category == ViolationCategory.UNSCHEDULED_COURSE
    ]
    assert len(unsched_viols) == 2
    unsched_codes = {v.entity_ids[0] for v in unsched_viols}
    assert unsched_codes == {"OVERFLOW_100", "ISOLATED_SMALL"}

    # No courses are silently lost
    total_accounted = len(result.assignments) + len(unsched_viols)
    assert total_accounted == len(reg.courses)

    # Hard constraints remain satisfied on whatever was scheduled (empty schedule is trivially valid)
    assert_hard_constraints_satisfied(result, reg)
