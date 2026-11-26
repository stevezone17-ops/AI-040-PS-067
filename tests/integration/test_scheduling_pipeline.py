"""Integration test for the end-to-end scheduling pipeline.

Verifies that all 6 Week 2 scheduling algorithms cooperate seamlessly:
  1. ALG-02: Examination session generation (generate_sessions)
  2. ALG-03: Student conflict graph construction (build_conflict_graph)
  3. ALG-04: Programme-semester cohort mapping (build_cohorts_map)
  4. ALG-05: Deterministic course ordering (order_courses)
  5. ALG-07: Supplementary examination eligibility (is_supplementary_eligible)
  6. ALG-06: Timetable generation (generate_timetable)
  7. ALG-10: Small-course deferral and repair integration (repair_deferred_courses)
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from exam_engine.scheduling.conflict_graph import build_conflict_graph
from exam_engine.scheduling.gap_validator import build_cohorts_map
from exam_engine.scheduling.ordering import order_courses
from exam_engine.scheduling.scheduler import (
    ExamAssignment,
    TimetableResult,
    generate_timetable,
)
from exam_engine.scheduling.session_generator import generate_sessions
from exam_engine.scheduling.small_course_repair import repair_deferred_courses
from exam_engine.scheduling.supplementary import is_supplementary_eligible
from tests.integration.fixtures import (
    IntegrationExamWindow,
    IntegrationGeneratedSession,
    IntegrationTimeInterval,
    SessionSlot,
    assert_hard_constraints_satisfied,
    build_scenario_a_small,
)


def test_step_by_step_pipeline_cooperation() -> None:
    """Verify explicit sequential execution of all 6 scheduling algorithms (ALG-02..ALG-10)."""
    registry = build_scenario_a_small(seed=42)

    # 1. ALG-02: Verify session generation from exam window
    exam_window = IntegrationExamWindow(
        start_date=date(2025, 12, 1),
        end_date=date(2025, 12, 5),
    )
    generated_sessions = generate_sessions(
        exam_window,
        session_factory=IntegrationGeneratedSession,
        time_interval_factory=IntegrationTimeInterval,
        slot_enum=SessionSlot,
    )
    assert len(generated_sessions) == 10  # 5 days * 2 slots

    # 2. ALG-03: Build student conflict graph
    conflict_graph = build_conflict_graph(registry)
    assert len(conflict_graph.same_session_forbidden) == len(registry.courses)
    # Students sharing courses should be forbidden in the same session
    assert "CSE102" in conflict_graph.same_session_forbidden["CSE101"]

    # 3. ALG-04: Build cohorts mapping
    cohorts_map = build_cohorts_map(registry)
    assert "CSE101" in cohorts_map
    assert ("BTech-CSE", 1) in cohorts_map["CSE101"]

    # 4. ALG-05: Determine deterministic course ordering
    ordered = order_courses(registry)
    assert len(ordered) == len(registry.courses)
    # Top course should have maximum enrolment
    assert ordered[0].course_code in ("CSE101", "CSE102")

    # 5. ALG-07: Verify supplementary eligibility on generated sessions
    supp_course = registry.courses["SUPP_CSE"]
    reg_fn_session = registry.sessions[0]
    supp_an_session = registry.sessions[-1]
    assert is_supplementary_eligible(supp_course, reg_fn_session, registry) is False
    assert is_supplementary_eligible(supp_course, supp_an_session, registry) is True

    # 6. ALG-06: Generate timetable with precomputed conflict graph & cohorts map
    result = generate_timetable(
        registry,
        conflict_graph=conflict_graph,
        cohorts_map=cohorts_map,
        repair_small_courses=False,
    )
    assert isinstance(result, TimetableResult)
    assert len(result.assignments) > 0

    # 7. ALG-10: Process deferred small courses if any
    if result.deferred_courses:
        repair_result = repair_deferred_courses(
            deferred_courses=result.deferred_courses,
            assignments=result.assignments,
            session_courses=result.session_courses,
            violations=result.violations,
            registry=registry,
            conflict_graph=conflict_graph,
            cohorts_map=cohorts_map,
        )
        assert len(repair_result.repaired_courses) + len(repair_result.unrepaired_courses) == len(
            result.deferred_courses
        )

    # 8. Dual-Oracle: Assert all hard constraints satisfied
    assert_hard_constraints_satisfied(result, registry)


def test_scenario_a_end_to_end_integrated_pipeline() -> None:
    """Verify Scenario A execution directly through generate_timetable with repair enabled."""
    registry = build_scenario_a_small(seed=42)

    result = generate_timetable(registry, repair_small_courses=True)

    # Verify all 10 courses are accounted for
    total_accounted = len(result.assignments) + len(result.deferred_courses)
    assert total_accounted == len(registry.courses)

    # Assert all hard constraints satisfied via independent dual-oracle validator
    assert_hard_constraints_satisfied(result, registry)

    # Verify assignments structure
    for code, assign in result.assignments.items():
        assert isinstance(assign, ExamAssignment)
        assert assign.course_code == code
        assert assign.session_id in registry.sessions_by_id


def test_precomputed_vs_dynamic_pipeline_consistency() -> None:
    """Verify passing precomputed conflict graph and cohorts map produces identical output."""
    registry = build_scenario_a_small(seed=99)

    # Run 1: Dynamic internal computation
    result1 = generate_timetable(registry, repair_small_courses=True)

    # Run 2: Precomputed external computation
    cg = build_conflict_graph(registry)
    cm = build_cohorts_map(registry)
    result2 = generate_timetable(
        registry,
        conflict_graph=cg,
        cohorts_map=cm,
        repair_small_courses=True,
    )

    assert result1.assignments == result2.assignments
    assert result1.session_courses == result2.session_courses
    assert result1.violations == result2.violations
    assert result1.deferred_courses == result2.deferred_courses
