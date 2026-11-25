"""Scheduling, conflict detection, and core-gap validation package.

This package implements the Week 2 scheduling modules (M2) for the
University Exam Timetabling and Hall Allocation Engine (AI-040-PS-067):
- ALG-02: Examination session generation (`session_generator`)
- ALG-03: Student conflict graph construction (`conflict_graph`)
- ALG-04: Programme-semester core-course gap validation (`gap_validator`)
- ALG-05: Deterministic course ordering (`ordering`)
- ALG-06: Earliest-feasible-session timetable generation (`scheduler`)
- ALG-07: Supplementary examination eligibility (`supplementary`)
"""

from __future__ import annotations

from exam_engine.scheduling.session_generator import EmptyExamWindowError, generate_sessions

__all__: list[str] = ["EmptyExamWindowError", "generate_sessions"]
