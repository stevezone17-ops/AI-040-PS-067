# 13 — Testing & Quality Assurance Strategy

**Document Status:** Week 1 Design Baseline — Zero Executable Code in Week 1  
**Related Documents:** [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md), [`14_TEST_CASE_CATALOGUE.md`](14_TEST_CASE_CATALOGUE.md), [`15_REQUIREMENTS_TRACEABILITY_MATRIX.md`](15_REQUIREMENTS_TRACEABILITY_MATRIX.md)

---

## 1. Testing Philosophy & Rubric Alignment

Testing directly accounts for **10 marks**, Validation & Edge Cases for **15 marks**, and Business-Rule Correctness for **40 marks** (65/100 marks combined). Because our architecture avoids external databases, web servers, and non-deterministic heuristics, **100% of business logic can be tested deterministically in memory in milliseconds** using `pytest`.

### Core Testing Principles
1. **Dual-Oracle Verification:** Every integration and change-command test asserts **both**:
   - Specific expected domain outcomes (exact `session_id`, `hall_id`, `seat_label`, `invigilator_id`, or `Violation.code`), AND
   - Zero hard-constraint errors from `IndependentScheduleValidator.validate(state)` (`ALG-18`).
2. **Boundary-Value Precision:** Every numeric threshold in `PS-067` is tested on **both sides of the exact boundary**:
   - Small course merge (`BR-05`, `EC-02`): `0`, `1`, `9` (must merge) vs `10` (may sit alone).
   - Core vs Elective (`BR-02`): `3` credits (no gap) vs `4` credits (requires `>= 1` full calendar day gap, i.e., `|d2 - d1| >= 2`).
   - Session 90% capacity (`BR-04`, `EC-03`): `capacity = 105` -> `94` students (pass) vs `95` students (fail).
   - Hall invigilators (`BR-07`): `1` student (`1` invig), `30` students (`1` invig) vs `31` students (`2` invigs), `60` (`2`) vs `61` (`3`).
   - Invigilator weekly cap (`BR-07`): `3` and `9` (rejected input) vs `4` and `8` (enforced exact ceiling).
   - Supplementary `FN` threshold (`BR-12`): `50` students (`AN` only) vs `51` students (`FN` or `AN`).
   - Special-needs duty overlap (`EC-05`): `17:20` hall end vs `17:15` external duty (overlap -> excluded) vs `17:30` external duty (non-overlap -> eligible under `AS-018`).
3. **Zero Shared Mutable Fixtures:** Pytest factory helpers (`make_course()`, `make_hall()`, `make_student()`) construct fresh frozen dataclasses per test function.

---

## 2. Five-Tier Verification Pyramid (Weeks 2–3)

| Tier | Planned Directory | Scope & Technique | Execution Target |
| :--- | :--- | :--- | :--- |
| **1. Unit Tests** | `tests/unit/` | Isolated module tests for `io/`, `conflict_graph`, `gap_validator`, `ordering`, `supplementary`, `hall_allocator`, `merge_policy`, `seat_assigner`, `accessibility`, `invigilator_engine`, and `validator`. | `< 0.5 s` total (~75 tests) |
| **2. Integration Tests** | `tests/integration/` | Multi-engine flows: Initial synthesis (`ALG-01`–`ALG-14` + `ALG-18` + `ALG-20`) and transactional change sequences (`POSTPONE`, `HALL_UNAVAILABLE`, `LATE_REG` with rollback & hash checks). | `< 1.5 s` total (~25 tests) |
| **3. Property / Invariant Tests** | `tests/integration/test_invariants.py` | Parametric seeded synthetic problem generators (10–150 courses, dense clashes, tight halls, random valid closures) asserting `ALG-18` hard-validity + SHA-256 blast-radius preservation on every run. *(Implemented with pure seeded `random.Random(seed)` in test code only—no external dependency required, or optional `hypothesis` dev-only).* | `< 2.0 s` total (~6 tests) |
| **4. Determinism & Regression Tests** | `tests/regression/` | Subprocess execution under `PYTHONHASHSEED=1` vs `PYTHONHASHSEED=424242` + shuffled input CSV row orderings (verifying `ALG-01` normalisation & `BR-03` sorting produce byte-for-byte identical outputs), plus golden-file diff against official sample expected outputs (`M9`). | `< 2.5 s` total (~4 tests) |
| **5. Scale & Performance Benchmarks** | `tests/regression/test_performance.py` | Synthetic expected-scale benchmark (`120` courses, `2,500` students, `18` halls, `90` invigilators, `12` days, `8` change commands) asserting wall-clock runtime `< 5.0 s` and peak RAM `< 150 MB`. | `< 5.0 s` (~2 tests) |

---

## 3. Planned Fixture Strategy (`tests/fixtures/` & `data/synthetic/`)

1. **Micro-Fixtures (In-Memory Builder DSL):** Concise builder helper `ScenarioBuilder` in `tests/conftest.py` so each unit test specifies **only** the attributes relevant to its rule (e.g., `builder.add_course("CS101", dept="CSE", credits=4, students=9)`), keeping tests readable in 15–25 lines.
2. **Synthetic Edge-Case File Bundles (`data/synthetic/`):**
   - `syn_01_clean_minimal/` — 8 courses, 60 students, 3 halls, 10 invigilators, 4 days (smoke pipeline).
   - `syn_02_edge_gauntlet/` — Combines `EC-01` through `EC-08` in a single deterministic file set.
   - `syn_03_infeasible_stress/` — Exercises `UNSCHEDULED_COURSE`, `HALL_UNSTAFFED`, `BUILDING_CHIEF_UNSTAFFED`, and rejected change rollbacks.
   - `syn_04_full_scale_120c_2500s/` — Matches exact official scale (`Section 8`) prior to official sample release.
3. **Official Sample Dataset (`data/sample/`):** Reserved strictly for official capstone inputs and expected outputs when provided by mentors (never fabricated).

---

## 4. Test Coverage & Quality Standards

- **Catalogue Volume:** **112 concrete, non-redundant test cases (`TC-001`–`TC-112`)** specified in [`14_TEST_CASE_CATALOGUE.md`](14_TEST_CASE_CATALOGUE.md).
- **Rule & Edge-Case Coverage:** 100% of `FR-01`–`FR-06`, 100% of `BR-01`–`BR-12` (each with positive, negative, boundary, and interaction cases), and 100% of `EC-01`–`EC-08`.
- **Line & Branch Coverage Target (Weeks 2–3):** $\ge 92\%$ line coverage and $\ge 88\%$ branch coverage across `src/exam_engine/`, with `100%` branch coverage on `validation/validator.py` and `changes/state_manager.py`.
