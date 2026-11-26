"""Scheduling, conflict detection, and core-gap validation package.

This package implements the Week 2 scheduling modules (M2) for the
University Exam Timetabling and Hall Allocation Engine (AI-040-PS-067):
- ALG-02: Examination session generation (`session_generator`)
- ALG-03: Student conflict graph construction (`conflict_graph`)
- ALG-04: Programme-semester core-course gap validation (`gap_validator`)
- ALG-05: Deterministic course ordering (`ordering`)
- ALG-06: Earliest-feasible-session timetable generation (`scheduler`)
- ALG-07: Supplementary examination eligibility (`supplementary`)
- ALG-10: Small-course deferral and repair (`small_course_repair`)
"""

from __future__ import annotations

from exam_engine.scheduling.conflict_graph import ConflictGraph, build_conflict_graph
from exam_engine.scheduling.gap_validator import build_cohorts_map, check_core_gap
from exam_engine.scheduling.ordering import order_courses
from exam_engine.scheduling.scheduler import (
    ExamAssignment,
    HallPackabilityChecker,
    TimetableResult,
    Violation,
    ViolationCategory,
    generate_timetable,
)
from exam_engine.scheduling.session_generator import (
    EmptyExamWindowError,
    generate_sessions,
)
from exam_engine.scheduling.small_course_repair import (
    MAX_SMALL_COURSE_ENROLMENT,
    MIN_SMALL_COURSE_ENROLMENT,
    SmallCourseRepairResult,
    coschedule_deferred_small_courses,
    is_small_course_eligible,
    repair_deferred_courses,
)
from exam_engine.scheduling.supplementary import is_supplementary_eligible

__all__: list[str] = [
    "MAX_SMALL_COURSE_ENROLMENT",
    "MIN_SMALL_COURSE_ENROLMENT",
    "ConflictGraph",
    "EmptyExamWindowError",
    "ExamAssignment",
    "HallPackabilityChecker",
    "SmallCourseRepairResult",
    "TimetableResult",
    "Violation",
    "ViolationCategory",
    "build_cohorts_map",
    "build_conflict_graph",
    "check_core_gap",
    "coschedule_deferred_small_courses",
    "generate_sessions",
    "generate_timetable",
    "is_small_course_eligible",
    "is_supplementary_eligible",
    "order_courses",
    "repair_deferred_courses",
]
