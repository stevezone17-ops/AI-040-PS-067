"""ALG-02: Deterministic Examination Session Generation.

Expands an ExamWindow into chronologically ordered ExamSession objects
for morning (FN: 09:30-12:30) and afternoon (AN: 14:00-17:00) slots.

References: FR-02, BR-12, CN-06, EC-08, AS-015, AS-016.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, timedelta
from typing import Any, Protocol

# Isolated provisional policy constants (AS-015, AS-016)
FN_START_MINUTES: int = 9 * 60 + 30   # 09:30 -> 570
FN_END_MINUTES: int = 12 * 60 + 30    # 12:30 -> 750
AN_START_MINUTES: int = 14 * 60       # 14:00 -> 840
AN_END_MINUTES: int = 17 * 60         # 17:00 -> 1020

SLOT_ORDER: tuple[str, ...] = ("FN", "AN")
SLOT_TIME_BOUNDS: dict[str, tuple[int, int]] = {
    "FN": (FN_START_MINUTES, FN_END_MINUTES),
    "AN": (AN_START_MINUTES, AN_END_MINUTES),
}
SUPPLEMENTARY_ACTIVE_DATE_COUNT: int = 3


class EmptyExamWindowError(ValueError):
    """Raised when an ExamWindow yields zero active examination sessions (CN-06)."""

    error_code: str = "ERR_EMPTY_EXAM_WINDOW"

    def __init__(self, message: str = "ERR_EMPTY_EXAM_WINDOW: No active sessions remain.") -> None:
        super().__init__(message)


class ExamWindowProtocol(Protocol):
    """Structural contract for M1 ExamWindow."""

    start_date: date
    end_date: date
    holidays: Iterable[date]
    closed_slots: Iterable[tuple[date, Any]]


def _resolve_domain_types(
    session_factory: Callable[..., Any] | None,
    time_interval_factory: Callable[[int, int], Any] | None,
    slot_enum: Any | None,
) -> tuple[Callable[..., Any], Callable[[int, int], Any], Any]:
    """Resolve M1 domain constructors or raise a clear dependency error."""
    if session_factory is not None and time_interval_factory is not None and slot_enum is not None:
        return session_factory, time_interval_factory, slot_enum

    try:
        from exam_engine.domain.entities import ExamSession, TimeInterval  # type: ignore[import-not-found]
        from exam_engine.domain.enums import SessionSlot  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "M1 shared domain kernel ('exam_engine.domain') is not available. "
            "Wait for M1 or supply explicit test-only domain factories."
        ) from exc

    return (
        session_factory or ExamSession,
        time_interval_factory or TimeInterval,
        slot_enum or SessionSlot,
    )


def _iter_window_dates(start_date: date, end_date: date) -> list[date]:
    """Return inclusive chronological calendar dates from start_date to end_date."""
    if start_date > end_date:
        return []
    total_days = (end_date - start_date).days + 1
    return [start_date + timedelta(days=offset) for offset in range(total_days)]


def _normalize_closed_slots(closed_slots: Iterable[tuple[date, Any]]) -> frozenset[tuple[date, str]]:
    """Normalize (date, slot) closures to canonical (date, slot_name) pairs."""
    return frozenset(
        (slot_date, str(getattr(slot_val, "value", slot_val)))
        for slot_date, slot_val in closed_slots
    )


def generate_sessions(
    window: ExamWindowProtocol,
    *,
    session_factory: Callable[..., Any] | None = None,
    time_interval_factory: Callable[[int, int], Any] | None = None,
    slot_enum: Any | None = None,
) -> tuple[Any, ...]:
    """Generate chronological ExamSession objects for an ExamWindow (ALG-02)."""
    make_session, make_interval, slots = _resolve_domain_types(
        session_factory, time_interval_factory, slot_enum
    )

    holidays = frozenset(window.holidays)
    closed = _normalize_closed_slots(window.closed_slots)

    pairs: list[tuple[date, Any, str]] = []
    for exam_date in _iter_window_dates(window.start_date, window.end_date):
        if exam_date in holidays:
            continue
        for slot_name in SLOT_ORDER:
            if (exam_date, slot_name) in closed:
                continue
            slot_obj = getattr(slots, slot_name)
            pairs.append((exam_date, slot_obj, slot_name))

    if not pairs:
        raise EmptyExamWindowError(
            "ERR_EMPTY_EXAM_WINDOW: ExamWindow produced zero active sessions."
        )

    active_dates = list(dict.fromkeys(exam_date for exam_date, _, _ in pairs))
    supp_start_idx = max(0, len(active_dates) - SUPPLEMENTARY_ACTIVE_DATE_COUNT)
    supp_dates = frozenset(active_dates[supp_start_idx:])

    sessions: list[Any] = []
    for index, (exam_date, slot_obj, slot_name) in enumerate(pairs):
        start_min, end_min = SLOT_TIME_BOUNDS[slot_name]
        iso_cal = exam_date.isocalendar()
        sessions.append(
            make_session(
                session_id=f"{exam_date.isoformat()}_{slot_name}",
                session_index=index,
                exam_date=exam_date,
                slot=slot_obj,
                base_window=make_interval(start_min, end_min),
                is_supplementary_window_date=(exam_date in supp_dates),
                iso_week_key=(iso_cal.year, iso_cal.week),
            )
        )
    return tuple(sessions)
