# 04 — Business Rule Register

**Document Status:** Authoritative Baseline — Week 1 Mandatory Deliverable  
**Source Authority:** Master Prompt Sections 5 & 6 (`PS-067`)  
**Related Documents:** [`05_ASSUMPTION_REGISTER.md`](05_ASSUMPTION_REGISTER.md), [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md), [`09_ALGORITHM_DESIGN.md`](09_ALGORITHM_DESIGN.md), [`14_TEST_CASE_CATALOGUE.md`](14_TEST_CASE_CATALOGUE.md)

> [!IMPORTANT]
> Rules `BR-01` through `BR-12` and Edge Cases `EC-01` through `EC-08` are **authoritative project requirements**. No module may silently modify, reorder, or replace them with alternative optimisation objectives. Where operational details are underspecified in the prompt, exact provisional resolutions are cross-referenced to [`05_ASSUMPTION_REGISTER.md`](05_ASSUMPTION_REGISTER.md).

---

## 1. Authoritative Business Rules (`BR-01` – `BR-12`)

### BR-01 — Student Examination Clashes
- **Official Statement:** No student may have two examinations in the same session. A student may not have more than one examination per day. A backlog student may have two examinations on the same day only when: (1) the examinations occur in different sessions, and (2) the student is flagged `BACKLOG_CONSENT`.
- **Classification:** Hard Constraint (`CN-07`, `CN-08`).
- **Formal Invariant:**
  - $\forall s \in \text{Students}, \forall \text{session } \tau$: $|\{c \in E(s) : \text{slot}(c) = \tau\}| \le 1$.
  - $\forall s \in \text{Students}, \forall \text{date } d$:
    - $|\{c \in E(s) : \text{date}(c) = d\}| \le 1$, **UNLESS** $s.\text{backlog\_consent} = \text{True}$ AND $|\{c \in E(s) : \text{date}(c) = d\}| = 2$ AND the two courses occupy `{FN, AN}` AND at least one of the two courses is a backlog enrolment for $s$ (`AS-013`).
- **Owning Modules:** `scheduling/conflict_graph.py`, `scheduling/scheduler.py` (Steven); audited by `validation/validator.py` (Mishael); enforced in changes by `changes/` (Tanisha).
- **Linked Assumptions & Edge Cases:** `AS-012`, `AS-013`, `AS-014`; `EC-06`, `EC-07`.

---

### BR-02 — Core Examination Gap
- **Official Statement:** Students in the same programme-semester must have at least one full calendar day between consecutive core examinations. Core courses have credits $\ge 4$. Elective courses have credits $< 4$ and require no gap. Holidays count towards the calendar-day gap.
- **Classification:** Soft-Fallback Constraint (`CN-09`) — enforced first as a scheduling requirement; degrades only to `SOFT_VIOLATION` under `BR-03` when no hard-valid session satisfies the gap.
- **Formal Invariant:**
  - Core predicate: $\text{is\_core}(c) \iff c.\text{credits} \ge 4$.
  - For any two distinct core courses $c_1, c_2$ sharing a `(programme, semester)` cohort (`AS-011`), $|\text{date}(c_1) - \text{date}(c_2)| \ge 2$ calendar days (e.g., `2026-12-01` and `2026-12-03` have `2026-12-02` as 1 full intervening calendar day, even if `2026-12-02` is a holiday).
  - Note: Two core courses of the same cohort on the same day (`|d1 - d2| = 0`) are already blocked by `BR-01` if they share students, and also violate `BR-02` (`0 < 2`); consecutive calendar days (`|d1 - d2| = 1`) violate `BR-02` (`EC-01`).
- **Owning Modules:** `scheduling/gap_validator.py` (Steven); audited by `validation/validator.py` (Mishael).
- **Linked Assumptions & Edge Cases:** `AS-011`, `AS-016`, `AS-027`; `EC-01`, `EC-06`.

---

### BR-03 — Deterministic Scheduling Heuristic
- **Official Statement:** Sort courses by: (1) Descending enrolment, (2) Descending credits, (3) Ascending course code. For each course, select the earliest session satisfying all hard rules and the gap rule. If no session satisfies the gap rule, select the earliest session satisfying all hard rules and record a `SOFT_VIOLATION`. Do not silently replace this heuristic with an optimisation algorithm that produces different expected outputs.
- **Classification:** Deterministic Algorithmic Policy (`CN-10`).
- **Sort Key:** `key(c) = (-len(c.enrolments), -c.credits, c.course_code)`.
- **Two-Pass Candidate Scan per Course:**
  - **Pass 1 (Strict):** Iterate chronological sessions $\tau_0, \tau_1, \dots, \tau_{m-1}$; pick smallest index $i$ satisfying all hard rules (`BR-01`, `BR-04`, `BR-05` feasibility, `BR-06` accessibility feasibility, `BR-12`) **AND** `BR-02`.
  - **Pass 2 (Gap Fallback):** Only if Pass 1 finds no session, iterate $\tau_0, \dots, \tau_{m-1}$; pick smallest index $i$ satisfying **all hard rules**, and append `Violation(type="SOFT_VIOLATION", code="CORE_GAP_SOFT_VIOLATION", ...)` to state.
  - **Infeasibility:** If Pass 2 also finds no session, mark course `UNSCHEDULED` (`CN-10`, `AS-032`).
- **Owning Modules:** `scheduling/ordering.py`, `scheduling/scheduler.py` (Steven).
- **Linked Assumptions & Edge Cases:** `AS-006`, `AS-032`; `EC-01`, `EC-07`.

---

### BR-04 — Session Capacity and Duration Compatibility
- **Official Statement:** Total seats used in a session must not exceed 90% of total available hall capacity. Three-hour examinations cannot share a hall with two-hour examinations.
- **Classification:** Hard Constraints (`CN-11` Session Aggregate Cap; `CN-12` Hall Duration Compatibility).
- **Formal Invariant:**
  - Let $H_{\text{avail}}(\tau)$ be the set of available halls in session $\tau$. Total students scheduled in $\tau$:
    $$\sum_{c \text{ in } \tau} |E(c)| \le \left\lfloor 0.90 \times \sum_{h \in H_{\text{avail}}(\tau)} h.\text{capacity} \right\rfloor$$
  - For every occupied hall $h$ in session $\tau$: $|\{c.\text{duration\_hours} : c \text{ allocated to } h\}| = 1$.
- **Owning Modules:** Session cap in `scheduling/scheduler.py` (Steven); hall duration compatibility in `allocation/hall_allocator.py` (Tanisha); audited by `validation/validator.py` (Mishael).
- **Linked Assumptions & Edge Cases:** `AS-001`, `AS-002`, `AS-003`; `EC-03`.

---

### BR-05 — Hall Filling
- **Official Statement:** Fill the largest hall first. A hall may contain at most two different courses. Students from the same course may not occupy adjacent columns. A course with fewer than ten students must be merged into a hall containing another course from a different department.
- **Classification:** Hard Constraints & Deterministic Packing Policy (`CN-13`, `CN-14`, `CN-15`, `CN-16`).
- **Formal Rules:**
  1. **Hall Order:** Available halls sorted by `(-h.capacity, h.hall_id)` (`AS-023`), subject to ground-floor accessibility reservation when special-needs students require `floor == 0` (`AS-010`).
  2. **Max Courses per Hall:** `1 <= len(h.courses) <= 2`.
  3. **Non-Adjacent Columns:** Course in Slot A uses odd columns `{1, 3, 5, ...}` ($\lceil C/2 \rceil$ cols); Course in Slot B uses even columns `{2, 4, 6, ...}` ($\lfloor C/2 \rfloor$ cols). Even in a 1-course hall, a single course uses only Slot A odd columns (`AS-004`, `AS-005`).
  4. **Mandatory Small-Course Merge:** If $1 \le |E(c)| < 10$, hall $h$ hosting $c$ **must** contain a second course $c'$ with $c'.\text{department} \ne c.\text{department}$ and $c'.\text{duration\_hours} = c.\text{duration\_hours}$. (Courses with $|E(c)| \ge 10$ may occupy a hall alone or share with a compatible second course; `EC-02`, `AS-006`, `AS-007`, `AS-008`).
- **Owning Modules:** `allocation/hall_allocator.py`, `allocation/merge_policy.py` (Tanisha).
- **Linked Assumptions & Edge Cases:** `AS-004`, `AS-005`, `AS-006`, `AS-007`, `AS-008`, `AS-023`, `AS-024`; `EC-02`, `EC-04`.

---

### BR-06 — Seating and Accessibility
- **Official Statement:** Seats are numbered in row-major order. Students of a course are seated alphabetically by register number in alternate columns. Special-needs students must occupy row one of a ground-floor hall. Special-needs students receive twenty extra minutes, extending the session end for that hall.
- **Classification:** Hard Constraints & Deterministic Seating Policy (`CN-17`, `CN-18`, `CN-19`).
- **Formal Rules:**
  1. **Seat Coordinates:** Row $r \in [1, \text{rows}]$, Column $k \in [1, \text{columns}]$, sequential number $(r-1)\times\text{columns} + k$, formatted `R{r:02d}C{k:02d}`.
  2. **Special-Needs Placement (`AS-009`):** Students with `special_needs == True` are sorted ascending by `register_number` and assigned first into `(row = 1, col in course_column_set)` of a hall with `floor == 0`.
  3. **Standard Placement:** Remaining students of the course are sorted ascending by `register_number` and fill remaining positions in `course_column_set` in row-major order (`row = 1` remaining cols, then `row = 2`, ..., `row = rows`), never exceeding `h.capacity`.
  4. **Extended Hall Duration (`AS-017`):** If hall $h$ in session $\tau$ contains $\ge 1$ special-needs student, `effective_end_time = base_end_time + 20 minutes` (`FN` 2h -> `11:50`, `FN` 3h -> `12:50`, `AN` 2h -> `16:20`, `AN` 3h -> `17:20`).
- **Owning Modules:** `allocation/seat_assigner.py`, `allocation/accessibility.py` (Tanisha).
- **Linked Assumptions & Edge Cases:** `AS-003`, `AS-009`, `AS-010`, `AS-017`, `AS-024`; `EC-05`.

---

### BR-07 — Invigilation Requirements
- **Official Statement:** Each occupied hall requires one invigilator per thirty students, rounded upwards, with a minimum of one invigilator. Each active building requires one additional chief invigilator per session. An invigilator may not invigilate a hall containing a course from their own department. An invigilator may work a maximum of two sessions per day. The supplied individual weekly limit, ranging from four to eight sessions, must be respected.
- **Classification:** Hard Eligibility & Headcount Rules (`CN-20`, `CN-21`, `CN-22`, `CN-23`).
- **Formal Rules:**
  - Hall invigilator count for occupied hall $h$ with $n_h > 0$ students: $\max(1, \lceil n_h / 30 \rceil)$.
  - Active building $b$ (with $\ge 1$ occupied hall in $\tau$): $+1$ Chief Invigilator.
  - Department conflict (`EC-04`): Invigilator $v$ ineligible for hall $h$ if $v.\text{department} \in \{c.\text{department} : c \text{ seated in } h\}$. (Chief invigilators operate at building level per `AS-019`).
  - Daily cap: $\text{sessions\_on\_date}(v, d) \le 2$ (counting both hall and chief duties, `AS-020`).
  - Weekly cap: $\text{sessions\_in\_iso\_week}(v, w) \le v.\text{max\_weekly\_sessions} \in [4, 8]$ (`AS-021`).
  - Intra-session uniqueness: An invigilator may hold at most 1 role (either 1 hall OR 1 building chief) per session.
- **Owning Modules:** `invigilation/invigilator_engine.py` (Mishael).
- **Linked Assumptions & Edge Cases:** `AS-018`, `AS-019`, `AS-020`, `AS-021`; `EC-04`, `EC-05`.

---

### BR-08 — Deterministic Invigilator Assignment
- **Official Statement:** Eligible invigilators must be sorted by: (1) Fewest sessions assigned so far, (2) Department in alphabetical order, (3) Invigilator identifier. Unavailable dates must be respected. If the eligible pool is exhausted, mark the hall `UNSTAFFED` and include it in the violations report.
- **Classification:** Deterministic Staffing Policy & Resource Shortage Reporting (`CN-24`).
- **Sort Key:** `key(v) = (assigned_count(v), v.department, v.invigilator_id)`.
- **Availability Check:** Date $d \notin v.\text{unavailable\_dates}$ AND hall/building duty interval `[session_start, effective_end_time)` does not overlap any external duty window of $v$ on date $d$ (`EC-05`, `AS-018`).
- **Shortage Behaviour:** Assign as many eligible invigilators as exist; for each unfilled required slot (hall or building chief), emit `UNSTAFFED` slot marker in roster and `Violation(type="RESOURCE_SHORTAGE", code="HALL_UNSTAFFED" | "BUILDING_CHIEF_UNSTAFFED")` in `violations.json`.
- **Owning Modules:** `invigilation/invigilator_engine.py` (Mishael).
- **Linked Assumptions & Edge Cases:** `AS-018`, `AS-022`, `AS-029`; `EC-04`, `EC-05`.

---

### BR-09 — Course Postponement
- **Official Statement:** Move the postponed course to the earliest later session satisfying all hard rules. The daily examination limits must be validated against already fixed examinations. Regenerate affected hall plans and invigilation rosters only for the original and destination sessions. All other assignments must remain unchanged.
- **Classification:** Incremental Change Rule (`CN-25`).
- **Blast Radius:** Strictly `{S_orig, S_dest}` (note: if moving the course out of `S_orig` would leave a `< 10` small partner unmerged in `S_orig`, `S_orig` hard-validity check catches or re-packs `S_orig` halls cleanly; if `S_orig` cannot remain hard-valid or no `S_dest` exists, command rejects atomically per `AS-031`).
- **Owning Modules:** `changes/postponement.py` (Tanisha).
- **Linked Assumptions & Edge Cases:** `AS-026`, `AS-027`, `AS-031`; `EC-06`.

---

### BR-10 — Hall Unavailability
- **Official Statement:** When a hall becomes unavailable, move its students to the next largest hall with free capacity in the same session. If sufficient capacity is unavailable, move the session's smallest course to the next free session and flag the change. All resulting allocations must continue satisfying applicable hard rules.
- **Classification:** Incremental Change Rule (`CN-26`).
- **Blast Radius:** `{S_orig}` when absorbed within the same session; `{S_orig, S_dest_1, ...}` when smallest-course displacement is triggered (`AS-025`, `AS-031`).
- **Owning Modules:** `changes/hall_unavailability.py` (Tanisha).
- **Linked Assumptions & Edge Cases:** `AS-025`, `AS-027`, `AS-031`.

---

### BR-11 — Late Registration
- **Official Statement:** For each examination belonging to a late registrant, allocate the student to the eligible hall with the most free seats. If adding the student causes an examination clash, reject the registration with `REJECTED_CLASH` and include the two conflicting course codes.
- **Classification:** Incremental Change Rule (`CN-27`).
- **Blast Radius:** Only the specific `(session, hall)` slots receiving the late registrant across their enrolled courses (atomic across all courses in the command per `AS-030`; existing student seats in those halls are preserved or course-column-appended cleanly — see `ALG-17` / `AS-028`!).
  - *Important detail on seat preservation during late registration:* Within the target hall, do existing students of that course keep their seats or re-sort alphabetically? Wait: `BR-06` requires students of a course to be seated alphabetically by register number in alternate columns, while `BR-11` says "allocate the student to the eligible hall with the most free seats". We explicitly document and handle this in `ALG-17` & `11_INCREMENTAL_RECOMPUTATION.md`: re-seating only that course's column set in that single chosen hall maintains `BR-06` alphabetical invariants for `IndependentScheduleValidator` while leaving every other hall and every other course untouched!
- **Owning Modules:** `changes/late_registration.py` (Tanisha).
- **Linked Assumptions & Edge Cases:** `AS-028`, `AS-029`, `AS-030`.

---

### BR-12 — Supplementary Examinations
- **Official Statement:** Supplementary backlog courses must be scheduled in `AN` sessions during the final three days of the examination window. A backlog course with enrolment greater than fifty may use an `FN` session during those days.
- **Classification:** Hard Temporal Eligibility Constraint (`CN-28`).
- **Formal Invariant:**
  - Let $D_{\text{final3}}$ be the final 3 active examination dates of `ExamWindow` (`AS-015`).
  - If `c.is_supplementary == True`:
    - $\text{date}(c) \in D_{\text{final3}}$.
    - If $|E(c)| \le 50$: $\text{slot}(c) = \text{AN}$ (strictly: $50 \le 50 \implies \text{AN}$ only; $51 > 50 \implies \text{FN or AN}$).
- **Owning Modules:** `scheduling/supplementary.py` (Steven); audited by `validation/validator.py` (Mishael).
- **Linked Assumptions & Edge Cases:** `AS-012`, `AS-015`, `AS-016`; `EC-08`.

---

## 2. Mandatory Edge Cases Register (`EC-01` – `EC-08`)

| ID | Mandatory Scenario | Governing Rules | Deterministic Engine Handling | Verification Test IDs |
| :--- | :--- | :--- | :--- | :--- |
| **EC-01** | Two core courses (`credits >= 4`) of the same programme-semester where only consecutive exam dates remain (`\|d2 - d1\| = 1`). | `BR-02`, `BR-03` | Pass 1 (strict gap `>= 2` calendar days) finds no slot for the 2nd core course. Pass 2 (fallback) selects the earliest consecutive-day session satisfying all hard rules (`BR-01`, `BR-04`, `BR-05`, `BR-06`, `BR-12`) and logs `SOFT_VIOLATION` (`CORE_GAP_SOFT_VIOLATION`). | `TC-016`, `TC-017` |
| **EC-02** | Course with **10 students** vs. course with **9 students**. | `BR-05` | Boundary is `< 10`. The 10-student course (`10 >= 10`) can legally occupy a hall **alone** (in odd columns). The 9-student course (`9 < 10`) **must** be merged into a hall with another equal-duration course from a **different department** (`AS-006`). | `TC-034`, `TC-035`, `TC-036` |
| **EC-03** | Hall or aggregate session capacity where 90% produces a fractional value (e.g., total capacity `105` -> `0.90 * 105 = 94.5`). | `BR-04` | Apply `math.floor` (`AS-002`): `floor(94.5) = 94` seats max. `94` students is valid (`94 <= 94.5`); `95` students (`90.48% > 90%`) is rejected as exceeding 90%. | `TC-026`, `TC-027` |
| **EC-04** | Invigilator belonging to **either** department represented in a merged 2-course hall (e.g., `CSE` + `ECE` hall). | `BR-05`, `BR-07`, `BR-08` | Both `CSE` and `ECE` invigilators are excluded from invigilating that hall (`v.department not in {"CSE", "ECE"}`). Only invigilators from third departments (e.g., `MAT`, `PHY`) are eligible. | `TC-056`, `TC-057` |
| **EC-05** | Special-needs student in a 3-hour `AN` exam extending hall duty from `17:00` to `17:20` when invigilator has another duty at `17:30` (vs `17:15`). | `BR-06`, `BR-08` | Hall effective window becomes `14:00–17:20`. Under `AS-018` (`0`-min strict interval non-overlap `[14:00, 17:20)` vs `[17:30, ...)`), `17:20 <= 17:30` so the `17:30` invigilator remains **eligible**, whereas an invigilator with a `17:15` (or `17:00`) duty is **excluded** due to the `+20m` extension. (Configurable handover buffer policy documented in `AS-018`). | `TC-062`, `TC-063`, `TC-064` |
| **EC-06** | Course postponement resulting in a consenting backlog student having **3 examinations across 2 consecutive days** (e.g., Day 1 `FN`+`AN`, Day 2 `FN`). | `BR-01`, `BR-02`, `BR-09` | Validated per-day under `BR-01` (`AS-014`): Day 1 has 2 exams (`FN` & `AN`, `BACKLOG_CONSENT=True`, `>=1` backlog paper -> valid); Day 2 has 1 exam (`FN` -> valid). No hard clash! If two of those are regular cohort core courses on consecutive days, `BR-02` gap check applies (`AS-027`). If the student lacked `BACKLOG_CONSENT` or hit 2 regular exams on Day 1, postponement skips that day. | `TC-075`, `TC-076` |
| **EC-07** | Student enrolled in two courses that would otherwise land in the same earliest session (`FN` Day 1) by size/credit order. | `BR-01`, `BR-03` | Conflict graph (`ALG-03`) records an edge `(C1, C2)`. `C1` (higher sort priority) takes `Day 1 FN`. When `C2` is evaluated, `Day 1 FN` fails `BR-01` (same session), `Day 1 AN` also fails `BR-01` (same day, unless `BACKLOG_CONSENT` + backlog enrolment for **every** shared student!), so `C2` deterministically advances to `Day 2 FN` (or `Day 3 FN` if core gap applies). | `TC-009`, `TC-010`, `TC-022` |
| **EC-08** | Final day of the examination window having **only an `FN` session** available (`AN` closed/unavailable). | `FR-02`, `BR-12` | Session generator (`ALG-02`) creates `Day_N_FN` only (`AS-016`). Under `BR-12`, supplementary courses with `enrolment <= 50` **cannot** use `Day_N_FN` (must use `AN` on `Day_{N-2}` or `Day_{N-1}`); supplementary courses with `enrolment > 50` (`>= 51`) **can** legally be scheduled into `Day_N_FN`. | `TC-088`, `TC-089`, `TC-090` |
