"""Unit tests for ALG-05: Deterministic Course Ordering.

Covers BR-03 and CN-10:
  - Priority 1: Descending student enrolment count
  - Priority 2: Descending course credits
  - Priority 3: Ascending course code (deterministic tie-breaker)
  - Zero-enrolment courses (TC-040)
  - Both regular and backlog enrolment counting
  - Permutation invariance across input record orders (TC-109)
  - Immutability of registry and course objects
  - Single course, empty registry, duplicate enrolment handling

Test case traceability
----------------------
TC-020  Primary sort key: Enrolment DESC
        C_small(20 stu, 4 cr), C_mid(50 stu, 3 cr), C_big(80 stu, 2 cr)
        -> [C_big, C_mid, C_small]
TC-021  Secondary & tertiary tie-breakers:
        CS102(50 stu, 4 cr), CS101(50 stu, 4 cr), AA101(50 stu, 3 cr)
        -> [CS101, CS102, AA101]
TC-040  0-enrolment course:
        Registered course CS000 with 0 enrolled students
TC-109  Permutation invariance:
        Permuting input registry course ordering produces identical outputs

M1 dependency status
--------------------
exam_engine.domain is NOT yet published as of Week 2.
All tests use isolated structural stubs consistent with docs/08_DOMAIN_MODEL.md.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from exam_engine.scheduling.ordering import order_courses

# ---------------------------------------------------------------------------
# Test-only stubs (structural protocol implementations)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StubCourse:
    """Minimal stub for domain.Course."""

    course_code: str
    credits: int
    department: str = "CSE"
    semester: int = 1
    duration_hours: int = 3
    is_supplementary: bool = False


@dataclass(frozen=True)
class StubEnrolment:
    """Minimal stub for domain.Enrolment."""

    register_number: str
    course_code: str
    is_backlog: bool = False


@dataclass
class StubRegistry:
    """Minimal stub for domain.ProblemRegistry.

    Provides courses mapping and enrolments_by_course mapping.
    """

    courses: dict[str, StubCourse]
    enrolments_by_course: dict[str, list[StubEnrolment]] = field(
        default_factory=dict
    )
    enrolments_by_student: dict[str, list[StubEnrolment]] = field(
        default_factory=dict
    )


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------


def test_empty_course_registry() -> None:
    """Empty registry returns an empty tuple."""
    registry = StubRegistry(courses={}, enrolments_by_course={})
    assert order_courses(registry) == ()


def test_single_course() -> None:
    """Single course registry returns a 1-tuple containing that course."""
    course = StubCourse("CS101", credits=4)
    registry = StubRegistry(
        courses={"CS101": course},
        enrolments_by_course={"CS101": [StubEnrolment("R01", "CS101")]},
    )
    result = order_courses(registry)
    assert result == (course,)


def test_tc_020_primary_sort_key_enrolment_descending() -> None:
    """TC-020: Priority 1 — Courses ordered by descending enrolment count.

    C_small(20 stu, 4 cr), C_mid(50 stu, 3 cr), C_big(80 stu, 2 cr)
    Expected order: [C_big, C_mid, C_small]
    """
    c_small = StubCourse("C_small", credits=4)
    c_mid = StubCourse("C_mid", credits=3)
    c_big = StubCourse("C_big", credits=2)

    enrols_small = [StubEnrolment(f"R_s{i}", "C_small") for i in range(20)]
    enrols_mid = [StubEnrolment(f"R_m{i}", "C_mid") for i in range(50)]
    enrols_big = [StubEnrolment(f"R_b{i}", "C_big") for i in range(80)]

    registry = StubRegistry(
        courses={
            "C_small": c_small,
            "C_mid": c_mid,
            "C_big": c_big,
        },
        enrolments_by_course={
            "C_small": enrols_small,
            "C_mid": enrols_mid,
            "C_big": enrols_big,
        },
    )

    result = order_courses(registry)
    expected_codes = ("C_big", "C_mid", "C_small")
    assert tuple(c.course_code for c in result) == expected_codes


def test_priority_2_credits_descending_when_enrolment_equal() -> None:
    """Equal enrolment counts broken by descending credits."""
    c1 = StubCourse("C_3CR", credits=3)
    c2 = StubCourse("C_4CR", credits=4)
    c3 = StubCourse("C_2CR", credits=2)

    # All have 50 enrolments
    enrols_1 = [StubEnrolment(f"R1_{i}", "C_3CR") for i in range(50)]
    enrols_2 = [StubEnrolment(f"R2_{i}", "C_4CR") for i in range(50)]
    enrols_3 = [StubEnrolment(f"R3_{i}", "C_2CR") for i in range(50)]

    registry = StubRegistry(
        courses={
            "C_3CR": c1,
            "C_4CR": c2,
            "C_2CR": c3,
        },
        enrolments_by_course={
            "C_3CR": enrols_1,
            "C_4CR": enrols_2,
            "C_2CR": enrols_3,
        },
    )

    result = order_courses(registry)
    expected_codes = ("C_4CR", "C_3CR", "C_2CR")
    assert tuple(c.course_code for c in result) == expected_codes


def test_priority_3_course_code_ascending_when_enrolment_and_credits_equal() -> None:
    """Equal enrolment and credits broken by ascending course code."""
    c1 = StubCourse("CS103", credits=4)
    c2 = StubCourse("CS101", credits=4)
    c3 = StubCourse("CS102", credits=4)

    # All have 30 enrolments
    enrols = [StubEnrolment(f"R_{i}", "any") for i in range(30)]

    registry = StubRegistry(
        courses={
            "CS103": c1,
            "CS101": c2,
            "CS102": c3,
        },
        enrolments_by_course={
            "CS103": enrols,
            "CS101": enrols,
            "CS102": enrols,
        },
    )

    result = order_courses(registry)
    expected_codes = ("CS101", "CS102", "CS103")
    assert tuple(c.course_code for c in result) == expected_codes


def test_tc_021_secondary_and_tertiary_tie_breakers() -> None:
    """TC-021: Complete tie-breaking test from catalogue.

    CS102(50 stu, 4 cr), CS101(50 stu, 4 cr), AA101(50 stu, 3 cr)
    Sort keys:
      CS101: (-50, -4, 'CS101')
      CS102: (-50, -4, 'CS102')
      AA101: (-50, -3, 'AA101')
    Expected order: [CS101, CS102, AA101]
    """
    cs102 = StubCourse("CS102", credits=4)
    cs101 = StubCourse("CS101", credits=4)
    aa101 = StubCourse("AA101", credits=3)

    enrols_50 = [StubEnrolment(f"R_{i}", "any") for i in range(50)]

    registry = StubRegistry(
        courses={
            "CS102": cs102,
            "CS101": cs101,
            "AA101": aa101,
        },
        enrolments_by_course={
            "CS102": enrols_50,
            "CS101": enrols_50,
            "AA101": enrols_50,
        },
    )

    result = order_courses(registry)
    expected_codes = ("CS101", "CS102", "AA101")
    assert tuple(c.course_code for c in result) == expected_codes


def test_complete_three_level_sorting_priority() -> None:
    """Courses combining differences across all three dimensions."""
    c_a = StubCourse("MAT101", credits=4)  # 100 stu, 4 cr
    c_b = StubCourse("PHY101", credits=3)  # 100 stu, 3 cr
    c_c = StubCourse("CH101", credits=4)   # 80 stu, 4 cr
    c_d = StubCourse("CS201", credits=4)   # 100 stu, 4 cr

    enrols_100 = [StubEnrolment(f"R100_{i}", "any") for i in range(100)]
    enrols_80 = [StubEnrolment(f"R80_{i}", "any") for i in range(80)]

    registry = StubRegistry(
        courses={
            "MAT101": c_a,
            "PHY101": c_b,
            "CH101": c_c,
            "CS201": c_d,
        },
        enrolments_by_course={
            "MAT101": enrols_100,
            "PHY101": enrols_100,
            "CH101": enrols_80,
            "CS201": enrols_100,
        },
    )

    result = order_courses(registry)
    # Among 100 stu: CS201 (4cr) < MAT101 (4cr) by code; PHY101 (3cr) comes after
    # Then 80 stu: CH101
    expected_codes = ("CS201", "MAT101", "PHY101", "CH101")
    assert tuple(c.course_code for c in result) == expected_codes


def test_enrolment_precedence_over_credits() -> None:
    """1 additional student outranks higher credit weight."""
    c_low_cred_high_enrol = StubCourse("C_MANY", credits=2)
    c_high_cred_low_enrol = StubCourse("C_FEW", credits=5)

    registry = StubRegistry(
        courses={
            "C_MANY": c_low_cred_high_enrol,
            "C_FEW": c_high_cred_low_enrol,
        },
        enrolments_by_course={
            "C_MANY": [StubEnrolment(f"R_{i}", "C_MANY") for i in range(51)],
            "C_FEW": [StubEnrolment(f"R_{i}", "C_FEW") for i in range(50)],
        },
    )

    result = order_courses(registry)
    assert tuple(c.course_code for c in result) == ("C_MANY", "C_FEW")


def test_credits_precedence_over_course_code() -> None:
    """Higher credits outranks alphabetical course code when enrolment is equal."""
    c_z = StubCourse("ZZ999", credits=4)
    c_a = StubCourse("AA001", credits=2)

    enrols_20 = [StubEnrolment(f"R_{i}", "any") for i in range(20)]

    registry = StubRegistry(
        courses={
            "ZZ999": c_z,
            "AA001": c_a,
        },
        enrolments_by_course={
            "ZZ999": enrols_20,
            "AA001": enrols_20,
        },
    )

    result = order_courses(registry)
    assert tuple(c.course_code for c in result) == ("ZZ999", "AA001")


def test_tc_040_zero_enrolment_courses() -> None:
    """TC-040: Courses with 0 enrolments sort by credits then course code."""
    c_zero_4cr = StubCourse("CS004", credits=4)
    c_zero_2cr = StubCourse("CS002", credits=2)
    c_zero_4cr_b = StubCourse("CS001", credits=4)
    c_active = StubCourse("CS100", credits=1)

    registry = StubRegistry(
        courses={
            "CS004": c_zero_4cr,
            "CS002": c_zero_2cr,
            "CS001": c_zero_4cr_b,
            "CS100": c_active,
        },
        enrolments_by_course={
            "CS100": [StubEnrolment("R1", "CS100")],
            # CS004, CS002, CS001 have 0 enrolments (missing from dict or empty list)
            "CS004": [],
        },
    )

    result = order_courses(registry)
    # CS100 has 1 student -> 1st
    # CS001 and CS004 have 0 students, 4 credits -> "CS001" < "CS004"
    # CS002 has 0 students, 2 credits -> last
    expected_codes = ("CS100", "CS001", "CS004", "CS002")
    assert tuple(c.course_code for c in result) == expected_codes


def test_regular_and_backlog_enrolments_both_count() -> None:
    """Both regular and backlog enrolments contribute to the enrolment count."""
    c1 = StubCourse("C1", credits=4)
    c2 = StubCourse("C2", credits=4)

    # C1: 10 regular + 10 backlog = 20 total
    enrols_c1 = [
        StubEnrolment(f"R_{i}", "C1", is_backlog=False) for i in range(10)
    ] + [
        StubEnrolment(f"B_{i}", "C1", is_backlog=True) for i in range(10)
    ]
    # C2: 15 regular + 0 backlog = 15 total
    enrols_c2 = [
        StubEnrolment(f"R2_{i}", "C2", is_backlog=False) for i in range(15)
    ]

    registry = StubRegistry(
        courses={"C1": c1, "C2": c2},
        enrolments_by_course={"C1": enrols_c1, "C2": enrols_c2},
    )

    result = order_courses(registry)
    assert tuple(c.course_code for c in result) == ("C1", "C2")


def test_supplementary_course_standard_ordering() -> None:
    """Supplementary courses adhere to the standard (-enrolment, -credits, code) key."""
    c_reg = StubCourse("MAT101", credits=4, is_supplementary=False)
    c_supp = StubCourse("MAT101S", credits=4, is_supplementary=True)

    # MAT101 has 30 students; MAT101S has 5 students
    registry = StubRegistry(
        courses={"MAT101": c_reg, "MAT101S": c_supp},
        enrolments_by_course={
            "MAT101": [StubEnrolment(f"R_{i}", "MAT101") for i in range(30)],
            "MAT101S": [StubEnrolment(f"S_{i}", "MAT101S") for i in range(5)],
        },
    )

    result = order_courses(registry)
    assert tuple(c.course_code for c in result) == ("MAT101", "MAT101S")


def test_deterministic_across_repeated_calls() -> None:
    """Repeated calls with identical registry yield identical output tuple."""
    c1 = StubCourse("CS101", credits=4)
    c2 = StubCourse("CS102", credits=3)
    c3 = StubCourse("CS103", credits=4)

    registry = StubRegistry(
        courses={"CS101": c1, "CS102": c2, "CS103": c3},
        enrolments_by_course={
            "CS101": [StubEnrolment("R1", "CS101")],
            "CS102": [StubEnrolment("R2", "CS102")],
            "CS103": [StubEnrolment("R3", "CS103")],
        },
    )

    r1 = order_courses(registry)
    r2 = order_courses(registry)
    assert r1 == r2


def test_tc_109_deterministic_across_reordered_registry() -> None:
    """TC-109: Reversing the insertion order of courses in registry produces identical results."""
    c1 = StubCourse("CS101", credits=4)
    c2 = StubCourse("CS102", credits=4)
    c3 = StubCourse("CS103", credits=4)
    c4 = StubCourse("MA201", credits=3)

    enrols_40 = [StubEnrolment(f"R_{i}", "any") for i in range(40)]
    enrols_20 = [StubEnrolment(f"R_{i}", "any") for i in range(20)]

    reg_forward = StubRegistry(
        courses={"CS101": c1, "CS102": c2, "CS103": c3, "MA201": c4},
        enrolments_by_course={
            "CS101": enrols_40,
            "CS102": enrols_40,
            "CS103": enrols_20,
            "MA201": enrols_40,
        },
    )

    reg_reversed = StubRegistry(
        courses={"MA201": c4, "CS103": c3, "CS102": c2, "CS101": c1},
        enrolments_by_course={
            "MA201": enrols_40,
            "CS103": enrols_20,
            "CS102": enrols_40,
            "CS101": enrols_40,
        },
    )

    out_forward = order_courses(reg_forward)
    out_reversed = order_courses(reg_reversed)

    assert out_forward == out_reversed
    # Expected: 40 stu 4cr (CS101, CS102), 40 stu 3cr (MA201), 20 stu 4cr (CS103)
    expected_codes = ("CS101", "CS102", "MA201", "CS103")
    assert tuple(c.course_code for c in out_forward) == expected_codes


def test_registry_not_mutated() -> None:
    """The input registry's courses dict and enrolments are not modified."""
    c1 = StubCourse("CS101", credits=4)
    c2 = StubCourse("CS102", credits=3)
    courses_dict = {"CS101": c1, "CS102": c2}
    enrols_dict = {"CS101": [StubEnrolment("R1", "CS101")], "CS102": []}

    registry = StubRegistry(courses=courses_dict, enrolments_by_course=enrols_dict)

    original_keys = list(courses_dict.keys())
    original_enrol_keys = list(enrols_dict.keys())

    _ = order_courses(registry)

    assert list(registry.courses.keys()) == original_keys
    assert list(registry.enrolments_by_course.keys()) == original_enrol_keys


def test_course_objects_not_mutated() -> None:
    """The attributes of Course objects remain completely unchanged."""
    c1 = StubCourse("CS101", credits=4, department="CSE", semester=2)
    registry = StubRegistry(courses={"CS101": c1}, enrolments_by_course={"CS101": []})

    out = order_courses(registry)
    assert out[0] is c1
    assert out[0].course_code == "CS101"
    assert out[0].credits == 4
    assert out[0].department == "CSE"
    assert out[0].semester == 2


def test_fallback_enrolments_by_student() -> None:
    """When enrolments_by_course is absent, derives count from enrolments_by_student."""
    class MinimalRegistry:
        def __init__(self) -> None:
            self.courses = {
                "C1": StubCourse("C1", credits=4),
                "C2": StubCourse("C2", credits=4),
            }
            # Only enrolments_by_student is present
            self.enrolments_by_student = {
                "S1": [StubEnrolment("S1", "C1"), StubEnrolment("S1", "C2")],
                "S2": [StubEnrolment("S2", "C1")],
            }

    registry = MinimalRegistry()
    # C1 has 2 enrolments, C2 has 1 enrolment
    result = order_courses(registry)  # type: ignore[arg-type]
    assert tuple(c.course_code for c in result) == ("C1", "C2")
