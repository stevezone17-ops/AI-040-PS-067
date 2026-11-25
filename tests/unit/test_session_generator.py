"""Unit tests for ALG-02 examination session generation.

Covers FR-02, CN-06, EC-08, AS-015, AS-016, TC-006, and TC-101 using
isolated test-only domain stubs until M1 (exam_engine.domain) is published.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from exam_engine.scheduling.session_generator import (  # noqa: E402
    AN_END_MINUTES,
    AN_START_MINUTES,
    FN_END_MINUTES,
    FN_START_MINUTES,
    EmptyExamWindowError,
    generate_sessions,
)


class StubSessionSlot(Enum):
    """Test-only stub for M1 SessionSlot enum."""

    FN = "FN"
    AN = "AN"


@dataclass(frozen=True, slots=True)
class StubTimeInterval:
    """Test-only stub for M1 TimeInterval value object."""

    start_minutes: int
    end_minutes: int


@dataclass(frozen=True, slots=True)
class StubExamWindow:
    """Test-only stub for M1 ExamWindow entity."""

    start_date: date
    end_date: date
    holidays: frozenset[date] = field(default_factory=frozenset)
    closed_slots: frozenset[tuple[date, StubSessionSlot]] = field(default_factory=frozenset)
    window_id: str = "MAIN_WINDOW"


@dataclass(frozen=True, slots=True)
class StubExamSession:
    """Test-only stub for M1 ExamSession entity."""

    session_id: str
    session_index: int
    exam_date: date
    slot: StubSessionSlot
    base_window: StubTimeInterval
    is_supplementary_window_date: bool
    iso_week_key: tuple[int, int]


def _run_generate(window: StubExamWindow) -> tuple[StubExamSession, ...]:
    """Invoke generate_sessions with test-only M1 stubs."""
    return generate_sessions(
        window,
        session_factory=StubExamSession,
        time_interval_factory=StubTimeInterval,
        slot_enum=StubSessionSlot,
    )


def test_normal_multi_day_window_ordering_indices_and_intervals() -> None:
    """Normal multi-day window produces chronological FN/AN sessions and 0-based indices."""
    window = StubExamWindow(start_date=date(2026, 12, 1), end_date=date(2026, 12, 4))
    sessions = _run_generate(window)

    assert len(sessions) == 8
    assert [s.session_index for s in sessions] == list(range(8))
    assert [s.session_id for s in sessions] == [
        "2026-12-01_FN",
        "2026-12-01_AN",
        "2026-12-02_FN",
        "2026-12-02_AN",
        "2026-12-03_FN",
        "2026-12-03_AN",
        "2026-12-04_FN",
        "2026-12-04_AN",
    ]
    for sess in sessions:
        if sess.slot is StubSessionSlot.FN:
            assert sess.base_window == StubTimeInterval(FN_START_MINUTES, FN_END_MINUTES)
            assert sess.base_window == StubTimeInterval(570, 750)
        else:
            assert sess.base_window == StubTimeInterval(AN_START_MINUTES, AN_END_MINUTES)
            assert sess.base_window == StubTimeInterval(840, 1020)
        assert sess.iso_week_key == (2026, 49)


def test_single_day_window_has_both_slots_and_supplementary_flag() -> None:
    """Single-day window (< 3 active dates) tags both FN and AN as supplementary."""
    window = StubExamWindow(start_date=date(2026, 12, 1), end_date=date(2026, 12, 1))
    sessions = _run_generate(window)

    assert len(sessions) == 2
    assert sessions[0].slot is StubSessionSlot.FN
    assert sessions[1].slot is StubSessionSlot.AN
    assert [s.session_index for s in sessions] == [0, 1]
    assert all(s.is_supplementary_window_date for s in sessions)


def test_two_active_dates_all_tagged_supplementary() -> None:
    """Window with fewer than 3 active dates tags all active dates as supplementary."""
    window = StubExamWindow(
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 3),
        holidays=frozenset({date(2026, 12, 2)}),
    )
    sessions = _run_generate(window)

    assert len(sessions) == 4
    assert all(s.is_supplementary_window_date for s in sessions)


def test_tc_006_holiday_and_final_day_fn_only_ec_08() -> None:
    """TC-006 / EC-08: Dec 01-04, Dec 02 holiday, Dec 04 AN closed -> 5 sessions."""
    window = StubExamWindow(
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 4),
        holidays=frozenset({date(2026, 12, 2)}),
        closed_slots=frozenset({(date(2026, 12, 4), StubSessionSlot.AN)}),
    )
    sessions = _run_generate(window)

    assert [s.session_id for s in sessions] == [
        "2026-12-01_FN",
        "2026-12-01_AN",
        "2026-12-03_FN",
        "2026-12-03_AN",
        "2026-12-04_FN",
    ]
    assert [s.session_index for s in sessions] == [0, 1, 2, 3, 4]
    assert all(s.is_supplementary_window_date for s in sessions)


def test_closed_fn_and_closed_an_slots_excluded() -> None:
    """Closed FN and AN slots on separate days are skipped while keeping indices contiguous."""
    window = StubExamWindow(
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 2),
        closed_slots=frozenset(
            {
                (date(2026, 12, 1), StubSessionSlot.FN),
                (date(2026, 12, 2), StubSessionSlot.AN),
            }
        ),
    )
    sessions = _run_generate(window)

    assert [s.session_id for s in sessions] == ["2026-12-01_AN", "2026-12-02_FN"]
    assert [s.session_index for s in sessions] == [0, 1]


def test_fully_closed_date_excluded_from_active_supplementary_dates() -> None:
    """Date with both FN and AN closed does not count as an active supplementary date."""
    window = StubExamWindow(
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 5),
        closed_slots=frozenset(
            {
                (date(2026, 12, 4), StubSessionSlot.FN),
                (date(2026, 12, 4), StubSessionSlot.AN),
            }
        ),
    )
    sessions = _run_generate(window)

    # Active dates are Dec 01, Dec 02, Dec 03, Dec 05 -> final 3 are Dec 02, Dec 03, Dec 05
    supp_by_date = {s.exam_date: s.is_supplementary_window_date for s in sessions}
    assert supp_by_date == {
        date(2026, 12, 1): False,
        date(2026, 12, 2): True,
        date(2026, 12, 3): True,
        date(2026, 12, 5): True,
    }


def test_final_three_active_dates_with_holiday_in_tail() -> None:
    """AS-015: Holiday inside final calendar days shifts final 3 active dates earlier."""
    window = StubExamWindow(
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 6),
        holidays=frozenset({date(2026, 12, 5)}),
    )
    sessions = _run_generate(window)

    supp_dates = sorted({s.exam_date for s in sessions if s.is_supplementary_window_date})
    non_supp_dates = sorted({s.exam_date for s in sessions if not s.is_supplementary_window_date})
    assert non_supp_dates == [date(2026, 12, 1), date(2026, 12, 2)]
    assert supp_dates == [date(2026, 12, 3), date(2026, 12, 4), date(2026, 12, 6)]


def test_tc_101_empty_window_all_holidays_raises() -> None:
    """TC-101 / CN-06: Window where all dates are holidays raises ERR_EMPTY_EXAM_WINDOW."""
    window = StubExamWindow(
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 2),
        holidays=frozenset({date(2026, 12, 1), date(2026, 12, 2)}),
    )
    with pytest.raises(EmptyExamWindowError) as exc_info:
        _run_generate(window)
    assert exc_info.value.error_code == "ERR_EMPTY_EXAM_WINDOW"


def test_empty_window_all_slots_closed_raises() -> None:
    """CN-06: Window where all slots are closed raises ERR_EMPTY_EXAM_WINDOW."""
    window = StubExamWindow(
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 1),
        closed_slots=frozenset(
            {
                (date(2026, 12, 1), StubSessionSlot.FN),
                (date(2026, 12, 1), StubSessionSlot.AN),
            }
        ),
    )
    with pytest.raises(EmptyExamWindowError) as exc_info:
        _run_generate(window)
    assert exc_info.value.error_code == "ERR_EMPTY_EXAM_WINDOW"


def test_inverted_window_dates_raises_empty_window() -> None:
    """TC-102 / CN-06: start_date > end_date yields zero sessions and raises ERR_EMPTY_EXAM_WINDOW."""
    window = StubExamWindow(start_date=date(2026, 12, 10), end_date=date(2026, 12, 5))
    with pytest.raises(EmptyExamWindowError) as exc_info:
        _run_generate(window)
    assert exc_info.value.error_code == "ERR_EMPTY_EXAM_WINDOW"


def test_deterministic_reproducibility() -> None:
    """Repeated calls with identical ExamWindow produce identical session tuples."""
    window = StubExamWindow(
        start_date=date(2026, 12, 1),
        end_date=date(2026, 12, 5),
        holidays=frozenset({date(2026, 12, 3)}),
        closed_slots=frozenset({(date(2026, 12, 5), StubSessionSlot.AN)}),
    )
    first = _run_generate(window)
    second = _run_generate(window)
    assert first == second


def test_missing_m1_domain_raises_clear_dependency_error() -> None:
    """Calling generate_sessions without M1 domain or stubs raises ModuleNotFoundError."""
    window = StubExamWindow(start_date=date(2026, 12, 1), end_date=date(2026, 12, 1))
    with pytest.raises(ModuleNotFoundError, match="exam_engine.domain"):
        generate_sessions(window)
