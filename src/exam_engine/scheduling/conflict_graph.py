"""ALG-03: Student Conflict Graph Construction.

Builds immutable same-session and same-day conflict adjacency maps from
ProblemRegistry enrolments and student backlog-consent flags.

References: BR-01, CN-07, CN-08, EC-06, EC-07, AS-013, AS-014.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


class StudentProtocol(Protocol):
    """Structural contract for M1 Student."""

    register_number: str
    backlog_consent: bool


class EnrolmentProtocol(Protocol):
    """Structural contract for M1 Enrolment."""

    register_number: str
    course_code: str
    is_backlog: bool


class ProblemRegistryProtocol(Protocol):
    """Structural contract for M1 ProblemRegistry."""

    courses: Mapping[str, Any]
    students: Mapping[str, StudentProtocol]
    enrolments_by_student: Mapping[str, Sequence[EnrolmentProtocol]]


@dataclass(frozen=True, slots=True)
class ConflictGraph:
    """Immutable course conflict adjacency maps (ALG-03)."""

    same_session_forbidden: dict[str, frozenset[str]]
    same_day_forbidden: dict[str, frozenset[str]]


def build_conflict_graph(registry: ProblemRegistryProtocol) -> ConflictGraph:
    """Construct ConflictGraph from validated student enrolments (ALG-03)."""
    same_sess: dict[str, set[str]] = {c: set() for c in sorted(registry.courses)}
    same_day: dict[str, set[str]] = {c: set() for c in sorted(registry.courses)}

    for student_id in sorted(registry.enrolments_by_student):
        student = registry.students[student_id]
        enrols = registry.enrolments_by_student[student_id]
        n = len(enrols)
        for i in range(n):
            u = enrols[i].course_code
            for j in range(i + 1, n):
                v = enrols[j].course_code
                if u == v:
                    continue
                same_sess.setdefault(u, set()).add(v)
                same_sess.setdefault(v, set()).add(u)
                consent_ok = student.backlog_consent and (
                    enrols[i].is_backlog or enrols[j].is_backlog
                )
                if not consent_ok:
                    same_day.setdefault(u, set()).add(v)
                    same_day.setdefault(v, set()).add(u)

    return ConflictGraph(
        same_session_forbidden={c: frozenset(same_sess[c]) for c in sorted(same_sess)},
        same_day_forbidden={c: frozenset(same_day[c]) for c in sorted(same_day)},
    )
