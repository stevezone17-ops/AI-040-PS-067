# 20 — Viva Preparation & Technical Defence Guide

**Document Status:** Week 1 Design Baseline — Conceptual Mastery Guide for Team `AI-040`  
**Audience:** Steven Mathew Binu (`2462157`), Tanisha Chhetri (`2462160`), Mishael Julian (`2462184`)  
**Related Documents:** [`04_BUSINESS_RULE_REGISTER.md`](04_BUSINESS_RULE_REGISTER.md), [`07_SYSTEM_ARCHITECTURE.md`](07_SYSTEM_ARCHITECTURE.md), [`09_ALGORITHM_DESIGN.md`](09_ALGORITHM_DESIGN.md), [`12_MODULE_OWNERSHIP.md`](12_MODULE_OWNERSHIP.md)

> [!TIP]
> **How to Use This Guide:** Examiners award **10 marks** for Viva & Presentation and treat **inability to explain or modify your own code** as a potential fail condition. Do **not** memorise scripts word-for-word. Instead, understand *why* each data structure, sort key, and boundary condition works so you can trace any example on paper or modify any rule live in your editor.

---

## 1. Project Pitch Explanations

### 1.1 Thirty-Second Elevator Pitch
> "We designed a deterministic Python backend engine for a university examination office that schedules end-semester exams across morning and afternoon sessions with zero student clashes, packs students into halls using largest-hall-first and alternate-column anti-cheating geometry, accommodates special-needs students in ground-floor Row 1 seats with 20 extra minutes, assigns department-independent invigilators and building chiefs within daily and weekly caps, and handles post-publication disruptions—course postponements, hall closures, and late registrations—transactionally by recomputing only the affected sessions."

### 1.2 Two-Minute Technical Walkthrough
> "Our engine is a command-file-driven CLI application built purely on the Python 3.10+ standard library across five strict layers.
> First, the **I/O layer** validates master CSVs and JSONs into immutable frozen dataclasses where `Enrolment` is the single source of truth.
> Second, the **Scheduling layer** builds an $\mathcal{O}(C^2)$ student conflict graph separating absolute same-session clashes from `BACKLOG_CONSENT`-eligible pairs, sorts courses deterministically by descending enrolment, descending credits, and course code (`BR-03`), and scans chronological sessions in two passes: Pass 1 enforces all hard rules plus the `BR-02` core-course calendar-day gap and invokes exact hall packability; Pass 2 relaxes *only* the core-course gap if unavoidable, logging a `CORE_GAP_SOFT_VIOLATION`.
> Third, the **Spatial Allocation layer** enforces the 90% aggregate session cap (`floor`), separates 2-hour and 3-hour papers, reserves ground-floor Row 1 seats for special-needs students (+20 minutes), fills largest halls first in odd/even non-adjacent columns, and merges small courses under 10 students with a different-department partner.
> Fourth, the **Invigilation layer** assigns `ceil(n/30)` non-same-department hall invigilators plus 1 building chief per active building, sorted by fewest assigned duties, respecting unavailable dates, extended-time overlaps (`17:20`), 2/day, and 4–8/week ISO limits—marking shortfalls `UNSTAFFED`.
> Finally, **Incremental Change Management** executes postponements, hall closures, and late registrations on copy-on-write state snapshots, verifying global rules via a zero-shared-code **Independent Schedule Validator** and asserting SHA-256 hash equality on all unaffected sessions before committing."

---

## 2. Plain-English Walkthrough of Every Business Rule (`BR-01` – `BR-12`)

| Rule | What It Enforces & *Why* It Exists in Real Universities | Key Code Boundary to Remember |
| :--- | :--- | :--- |
| **BR-01** | Prevents a student from having 2 exams at once, or 2 in one day (mental fatigue)—except arrear students who signed `BACKLOG_CONSENT`, who can take 1 `FN` + 1 `AN` exam on the same day (`>=1` must be backlog). | Same session is *never* allowed, even with consent (`TC-013`). |
| **BR-02** | Gives cohorts at least 1 full study day (`\|d2 - d1\| >= 2` days) between heavy Core exams (`credits >= 4`). Electives (`< 4` credits) need no gap. Holidays count as study days! | `credits >= 4` (not `> 4`); consecutive dates give `\|d2 - d1\| = 1 < 2`. |
| **BR-03** | Schedules largest, highest-credit courses first (hardest to fit!) into the earliest legal slot. If no slot satisfies `BR-02`, falls back to earliest hard-legal slot and logs `SOFT_VIOLATION`. | Sort key: `(-enrolment, -credits, course_code)`. Never replace with random/MIP solver. |
| **BR-04** | Keeps 10% buffer seats across the session (`(90 * sum_cap) // 100`) for emergencies, and separates `2h` and `3h` exams into different rooms so `2h` students leaving at `11:30`/`16:00` don't disturb `3h` examinees. | Integer floor `(90 * cap) // 100`: `105` -> `94` (`EC-03`). |
| **BR-05** | Minimises active rooms by filling largest halls first (`(-cap, hall_id)`), caps halls at 2 courses, seats same-course students in non-adjacent odd/even columns to prevent copying, and forces `< 10` student courses to share a hall with another department. | `< 10` means `1..9` must merge; `10` can sit alone (`EC-02`)! |
| **BR-06** | Numbers seats row-major (`R01C01..`), seats courses alphabetically in their odd/even columns, puts `special_needs` students on `floor == 0, row == 1` for wheelchair/mobility access, and adds `+20` minutes to that hall's clock. | 3h `AN` + SN ends at `17:20` (`EC-05`). |
| **BR-07** | Assigns `max(1, ceil(n/30))` hall invigilators + `1` chief per active building; bans faculty from invigilating their own department's courses (`EC-04`); caps load at `2`/day and `4..8`/ISO-week. | `30` students = `1` invig; `31` students = `(31+29)//30 = 2` invigs! |
| **BR-08** | Balances invigilator fairness by picking `(assigned_so_far, department, invigilator_id)`, respects unavailable dates/overlaps, and reports `UNSTAFFED` if the eligible pool runs dry. | Never assign an ineligible invigilator to avoid `UNSTAFFED`! |
| **BR-09** | Postpones a course to the earliest later valid session, updating **only** `{S_orig, S_dest}` while keeping the other ~18 sessions untouched. | Checks fixed exams on target date for `BR-01` daily caps (`EC-06`). |
| **BR-10** | If a hall closes, moves its students to the next largest free hall in the same session; if the session overflows, moves the session's **smallest** course `(enrolment, credits, code)` to the next free later session. | Emits `COURSE_DISPLACED_BY_HALL_CLOSURE`. |
| **BR-11** | Seats a late-registering student into the eligible hall with the **most free seats** per course, or rejects the whole command with `REJECTED_CLASH` + 2 course codes if a clash occurs. | Atomic across all courses in the command (`AS-030`). |
| **BR-12** | Schedules supplementary backlog papers into `AN` sessions of the final 3 active exam days, unlocking `FN` sessions on those 3 days only when `enrolment > 50` (`>= 51`). | `50` -> `AN` only; `51` -> `FN` or `AN` (`EC-08`). |

---

## 3. Core Architectural & Theoretical Defence Points

### 3.1 Hard vs. Soft Constraints vs. Resource Shortages
- **Hard Constraints (`BR-01`, `BR-04`, `BR-05`, `BR-06`, `BR-07` eligibility, `BR-12`):** Protect academic fairness and physical reality. Breaking them invalidates an exam. If unsatisfiable, the course becomes `UNSCHEDULED` or the change command is `REJECTED_*`.
- **Soft Constraint (`BR-02` Core Gap):** Study comfort preference. Under `BR-03`, if a tight calendar leaves only consecutive days (`EC-01`), holding the exam on consecutive days with a logged `SOFT_VIOLATION` is preferable to cancelling the exam—while **still enforcing every hard constraint**.
- **Resource Shortage (`BR-08` `UNSTAFFED`):** Staffing shortfall reported to administration so guest/external invigilators can be arranged manually, rather than illegally placing a `CSE` professor inside a `CSE` exam hall.

### 3.2 Why Deterministic Greedy Scheduling (`BR-03`) — And Why Global Optimality Is Not Guaranteed
1. **Why Used:** Prescribed by `BR-03` ("largest degree/size first" heuristic), runs in `< 50 ms` ($\mathcal{O}(C \cdot M \cdot H \log H)$), is 100% explainable step-by-step, and produces reproducible reference outputs for grading.
2. **Why Not Globally Optimal:** Exam timetabling contains **Graph $K$-Colouring** as a special case (courses = vertices, shared students = edges, sessions = $M$ colours), which is **NP-Complete** for $M \ge 3$. A greedy choice for an early large course $C_1$ into `Day 1 FN` is never backtracked; on an adversarial bipartite/crown graph, an ILP/SAT solver might swap $C_1$ to `Day 2` to avoid a downstream `CORE_GAP_SOFT_VIOLATION` or `UNSCHEDULED` course that greedy placement cannot avoid without backtracking.

### 3.3 Why Incremental Recomputation Is Essential
If an AC fails in `BLK1-101` on Day 5 morning (`BR-10`), regenerating the whole 12-day timetable would change exam dates for 2,500 students and scramble invigilation rosters for 90 faculty! Local recomputation bounds the blast radius to `{S_orig}` (or `{S_orig, S_dest}`), verified via SHA-256 session digests (`ALG-19`).

### 3.4 Complexity Summary (Keep Handy for Whiteboard)
- **Conflict Graph (`ALG-03`):** $\mathcal{O}(S \cdot k^2 + C^2)$ — $2{,}500 \times 25 + 14{,}400 \approx 7.7 \times 10^4$ ops.
- **Initial Timetable (`ALG-06`):** $\mathcal{O}(C \cdot M \cdot (C_{\text{sess}} + H \log H))$ — $\approx 6 \times 10^4$ ops (`< 50 ms`).
- **Seating (`ALG-11`):** $\mathcal{O}(E \log E + M \cdot H \cdot R \cdot \text{Cols})$ — sorting students + grid walk.
- **Invigilation (`ALG-13`/`14`):** $\mathcal{O}(M \cdot (H + B) \cdot V \log V)$ — $\approx 3.5 \times 10^5$ ops (`< 40 ms`).
- **Incremental Command (`ALG-15`–`17`):** Touches at most `2` sessions (or `k` halls) instead of `M` sessions!

---

## 4. Thirty-Six Likely Viva Questions & Concise Answers

### Category 1: Domain Model & Architecture (`Q01`–`Q07`)
1. **Q01: Why didn't you use SQLite or PostgreSQL?**  
   *A:* With 2,500 students and 12,500 enrolments, the entire dataset occupies `< 15 MB` in RAM. Frozen Python dataclasses give sub-millisecond $\mathcal{O}(M)$ copy-on-write snapshots for rollback (`ALG-19`) with zero SQL boilerplate or external dependencies.
2. **Q02: How do you prevent `Student.backlog_courses` and `Course` enrolment lists from getting out of sync?**  
   *A:* `Enrolment(register_number, course_code, is_backlog)` is the **single source of truth**. Neither `Student` nor `Course` mutates private lists; `ProblemRegistry` derives immutable sorted tuple views from `enrolments`.
3. **Q03: Why is `Building` modelled separately from `Hall`?**  
   *A:* `BR-07` assigns one Chief Invigilator per *active building* per session, and that chief's duty window spans the latest hall end time inside that building (`ALG-14`).
4. **Q04: Why must `IndependentScheduleValidator` (`validation/`) not import helpers from `scheduling/` or `allocation/`?**  
   *A:* To eliminate common-mode failures! If `allocation/` had an off-by-one bug in column adjacency, calling the same helper in `validation/` would rubber-stamp the bug. Independent validation re-audits raw coordinates from scratch.
5. **Q05: How do you guarantee identical output across Windows and Linux or across multiple Python runs?**  
   *A:* Python randomises `set` hashes per run (`PYTHONHASHSEED`). We forbid iterating over raw `set`s, end every `sort` key with a unique string ID, use integer arithmetic `(90 * cap) // 100`, and write `\n` LF line endings.
6. **Q06: What happens if the official sample CSVs use different column headers than your Week 1 docs?**  
   *A:* Only `src/exam_engine/io/parsers.py` and `reporting/` know file headers (`ADR-012`). All 12 core engines consume `ProblemRegistry` and `ScheduleState`, requiring zero business-logic edits.
7. **Q07: Why use `TimeInterval(start_minutes, end_minutes)` integers instead of `datetime.datetime`?**  
   *A:* Intra-day session math (`09:30` = `570`, `+180 + 20 = 770`) has no timezones or daylight-saving edge cases; overlap between `[a, b)` and `[c, d)` is simply `max(a, c) < min(b, d)`.

### Category 2: Scheduling, Clashes, Gaps & Supplementary (`Q08`–`Q16`)
8. **Q08: How does your `ConflictGraph` distinguish normal clashes from `BACKLOG_CONSENT` pairs in $\mathcal{O}(1)$?**  
   *A:* It maintains two edge maps: `same_session_forbidden` (any shared student) and `same_day_forbidden` (any shared student who either lacks `BACKLOG_CONSENT` or takes both courses as regular non-backlog courses).
9. **Q09: Could a consenting backlog student ever end up with 3 exams on the same single day?**  
   *A:* Impossible! Each day has only 2 sessions (`FN` and `AN`), and `same_session_forbidden` blocks placing 2 of the student's exams in `FN` or 2 in `AN`.
10. **Q10: Explain `EC-06`: What if postponement gives a consenting backlog student 3 exams across 2 consecutive days?**  
    *A:* `BR-01` limits exams *per calendar day* (`<= 2`/day in `{FN, AN}` with consent and backlog). Having 2 exams on Day 4 (`FN`+`AN`) and 1 exam on Day 5 (`FN`) satisfies `BR-01` on both days! We still check `BR-02` if two of them are cohort core courses.
11. **Q11: How is "at least one full calendar day between consecutive core examinations" (`BR-02`) expressed mathematically?**  
    *A:* `abs((date_2 - date_1).days) >= 2`. Monday (`Day 1`) and Tuesday (`Day 2`) have diff `1` (0 full days between -> violation); Monday (`Day 1`) and Wednesday (`Day 3`) have diff `2` (Tuesday is 1 full day between -> valid, even if Tuesday is a holiday).
12. **Q12: In `EC-01`, when Pass 1 fails the core-gap rule, can Pass 2 place the course in a session that exceeds 90% capacity?**  
    *A:* Never. Pass 2 relaxes **only** `BR-02` (`check_core_gap`), while still calling `is_hard_feasible()` which enforces `BR-01`, `BR-04`, `BR-05`, `BR-06`, and `BR-12`.
13. **Q13: Why does `ALG-06` call `ALG-08` hall packing during scheduling instead of only checking `total_students <= 90%`?**  
    *A:* Because 70 students (`35` in a `2h` course + `35` in a `3h` course) pass a `72`-seat 90% cap across two `40`-seat halls, yet **cannot** physically pack because `2h` and `3h` cannot share a hall and alternate columns cap a single course at 20 seats per `5x8` hall!
14. **Q14: Explain the `50` vs `51` boundary in `BR-12`.**  
    *A:* `BR-12` says *"greater than fifty"* (`enrolment > 50`). So a supplementary course with `50` students may only use `AN` in the final 3 active days; `51` students may use `FN` or `AN`.
15. **Q15: How do you handle `EC-08` when the final day has only an `FN` session?**  
    *A:* `ALG-02` omits `Day_N_AN` via `closed_slots`. Supplementary courses with `<= 50` students cannot use `Day_N_FN` and must use earlier final-3 `AN` slots (or become `UNSCHEDULED` if full); supplementary courses with `>= 51` students *can* use `Day_N_FN`.
16. **Q16: What happens if a dataset has 5 mutually clashing regular courses in a 2-day window?**  
    *A:* First 2 courses take `Day 1 FN` and `Day 2 FN`; the remaining 3 have zero hard-valid slots and are cleanly reported as `UNSCHEDULED_COURSE` in `violations.json`.

### Category 3: Hall Packing, Seating & Accessibility (`Q17`–`Q24`)
17. **Q17: Explain `EC-03`: How do you round 90% of `105` total seats (`94.5`)?**  
    *A:* Integer floor `(90 * 105) // 100 = 94`. Using `95` would be `90.48%`, violating *"must not exceed 90%"*.
18. **Q18: Explain `EC-02`: Difference between a 9-student course and a 10-student course?**  
    *A:* `BR-05` specifies *"fewer than ten"* (`< 10`). `9` students **must** merge into a hall with a different-department equal-duration partner; `10` students may occupy a hall alone.
19. **Q19: What if a single 40-student course occupies an `8x10` hall (`80` seats) alone—do students sit in adjacent columns?**  
    *A:* No (`AS-004`). `BR-05` forbids same-course students in adjacent columns unconditionally. It uses odd columns `{1, 3, 5, 7, 9}` (`8 * 5 = 40` seats), leaving even columns empty (or open for a second course).
20. **Q20: How does alternate-column seating work in a hall with `7` columns (odd column count)?**  
    *A:* Set A = odd columns `{1, 3, 5, 7}` (`ceil(7/2) = 4` cols); Set B = even columns `{2, 4, 6}` (`floor(7/2) = 3` cols). No two columns in Set A or Set B differ by `1`.
21. **Q21: Why do courses with special-needs students reserve ground-floor halls before general largest-first packing?**  
    *A:* If upper-floor halls happened to be larger (`cap=100`) or if large non-SN courses grabbed all `floor == 0` halls first, a later course with a wheelchair user would be stranded with zero ground-floor Row 1 seats (`AS-010`).
22. **Q22: How do you reconcile alphabetical register-number seating with placing special-needs students in Row 1 (`BR-06`)?**  
    *A:* Within the course's column set, special-needs students are sorted alphabetically into `floor == 0, row == 1` first; remaining regular students are sorted alphabetically across the remaining column-set seats in row-major order (`AS-009`).
23. **Q23: Can two small courses (`6` `CSE` students and `7` `ECE` students, both `3h`) merge with each other?**  
    *A:* Yes (`AS-007`). Both sit in a hall containing another course from a different department, max 2 courses/hall is respected, and durations match (`3h`).
24. **Q24: If only 1 special-needs student sits in a hall with 39 regular students, who gets the +20 minute hall extension?**  
    *A:* Under `BR-06`, the *hall's* session end extends by 20 minutes (`effective_window`), so invigilators and building chiefs stay until `12:50`/`17:20` (`ALG-12`).

### Category 4: Invigilation & Workload (`Q25`–`Q30`)
25. **Q25: Why use `(n_students + 29) // 30` instead of `math.ceil(n_students / 30)`?**  
    *A:* Pure integer arithmetic avoids float conversion (`max(1, (n + 29) // 30)` gives `1` for `1..30`, `2` for `31..60`, `3` for `61..90`).
26. **Q26: Explain `EC-04`: A hall merges `CSE` and `ECE`. Which invigilators are excluded?**  
    *A:* Both `CSE` and `ECE` invigilators are excluded (`v.department not in {"CSE", "ECE"}`), because the hall contains courses from both departments (`BR-07`).
27. **Q27: Explain `EC-05`: A 3h `AN` hall has a special-needs student (`17:20` end) and an invigilator has another duty at `17:30`.**  
    *A:* The hall window extends from `14:00–17:00` to `14:00–17:20`. Under strict interval non-overlap (`MIN_TRANSITION_BUFFER_MINUTES = 0`, `AS-018`), `17:20 <= 17:30` does not overlap so `17:30` is eligible (whereas `17:15` is excluded!). If a mentor specifies a `15`-min script-collection buffer, changing `MIN_TRANSITION_BUFFER_MINUTES = 15` in `eligibility.py` flips `17:30` to excluded cleanly.
28. **Q28: Does a Building Chief duty count toward the 2-per-day and `max_weekly_sessions` limits?**  
    *A:* Yes (`AS-020`), and an invigilator cannot simultaneously be a Building Chief and a Hall Invigilator in the same session.
29. **Q29: How are weekly limits (`4..8`) bounded across a 12-day window?**  
    *A:* By ISO Monday–Sunday calendar weeks (`date.isocalendar()[:2]`, `AS-021`). When Monday of Week 2 starts, the weekly counter resets for the new ISO week.
30. **Q30: What happens when all non-`CSE` invigilators are unavailable or at their weekly cap for a `CSE` hall?**  
    *A:* The slot is marked `UNSTAFFED` in `invigilation_roster.csv` and logged as `HALL_UNSTAFFED` in `violations.json` (`BR-08`). A `CSE` invigilator is **never** assigned.

### Category 5: Incremental Recomputation & Rollback (`Q31`–`Q36`)
31. **Q31: During `POSTPONE_COURSE` from Day 2 to Day 4, how do you ensure Day 4's invigilator selection doesn't break Day 6's already-scheduled weekly cap?**  
    *A:* `WorkloadTracker.from_fixed_sessions()` pre-loads all duties from unaffected sessions (Days 1, 3, 5, 6..12) *before* staffing `{Day 2, Day 4}` (`TC-097`).
32. **Q32: How do you prove mathematically that unaffected sessions did not change during `BR-09`–`BR-11`?**  
    *A:* `ALG-19` hashes the canonical JSON serialisation of `(courses, halls, seats, invigilators)` for every session before and after the command and asserts `digest_before[s] == digest_after[s]` for all `s not in affected_sessions`.
33. **Q33: In `BR-10` (`MARK_HALL_UNAVAILABLE`), when does a course move to another session vs stay in the same session?**  
    *A:* First, `ALG-16` tries repacking the session's courses into the remaining halls of the **same session** (next largest free hall first). Only if 90% session cap or physical hall packing fails does it displace the session's smallest course `(enrolment, credits, course_code)` to the next free later session.
34. **Q34: Why might `POSTPONE_COURSE` fail because of `S_orig` rather than `S_dest`?**  
    *A:* If `S_orig` had only two courses—say `CS301(40 stu, CSE)` and `EC309(7 stu, ECE)`—postponing `CS301` would leave the 7-student `EC309` course alone in `S_orig`, violating `BR-05`! `ALG-15` checks `S_orig` packability after removal and rejects/rolls back if `S_orig` breaks.
35. **Q35: In `BR-11` (`ADD_LATE_REGISTRANT`), why do we pick the hall with the *most free seats* instead of the *largest total capacity* hall?**  
    *A:* Because `BR-11` explicitly mandates *"allocate the student to the eligible hall with the most free seats"* (`(-free_legal_seats, hall_id)`): an `80`-seat hall with `78` seats full has only `2` free seats, whereas a `60`-seat hall with `20` seats used has `40` free seats!
36. **Q36: What happens if a late registrant submits 5 courses and the 5th clashes (`REJECTED_CLASH`)?**  
    *A:* Because commands run on a candidate snapshot (`ALG-19`), `candidate_state` is discarded, all 4 tentative seats are rolled back atomically (`AS-030`), and `REJECTED_CLASH` is logged with the 2 clashing course codes.

---

## 5. Eight Live-Code-Modification Scenarios (Viva Practical Prep)

Examiners frequently ask: *"Change rule X right now and run pytest."* Know the exact 1-file location for each:

| Live Viva Prompt | Exact Target File & Function | Exact Code Change Needed |
| :--- | :--- | :--- |
| **1. "Change the session capacity limit from 90% to 85%."** | `allocation/policies.py` -> `compute_session_cap()` | Change `(90 * total_cap) // 100` to `(85 * total_cap) // 100` (and update matching constant in `validation/validator.py`). |
| **2. "Change small-course merging from `< 10` to `< 15` students."** | `allocation/policies.py` -> `SMALL_COURSE_THRESHOLD` | Change `10` to `15`. |
| **3. "Require `2` full calendar days between core exams (`BR-02`)."** | `scheduling/gap_validator.py` -> `check_core_gap()` | Change `abs((d1 - d2).days) >= 2` to `>= 3` (`2` intervening days = difference `3`). |
| **4. "Change invigilator ratio from 1 per 30 to 1 per 25 students."** | `invigilation/invigilator_engine.py` | Change `(n_students + 29) // 30` to `(n_students + 24) // 25`. |
| **5. "Add a 15-minute post-exam buffer for invigilator duties (`EC-05`)."** | `invigilation/eligibility.py` | Change `MIN_TRANSITION_BUFFER_MINUTES = 0` to `15`. |
| **6. "Give special-needs students 30 extra minutes instead of 20."** | `allocation/accessibility.py` -> `SPECIAL_NEEDS_EXTRA_MINUTES` | Change `20` to `30`. |
| **7. "Also forbid Building Chiefs from belonging to any department active in that building."** | `invigilation/eligibility.py` | Flip `CHIEF_EXCLUDES_BUILDING_DEPARTMENTS = False` to `True`. |
| **8. "Break course-ordering ties by *descending* course code instead of ascending."** | `scheduling/ordering.py` | Wrap `course_code` in a reverse-lexicographical comparator key inside `order_courses()`. |

---

## 6. Individual Ownership-Specific Viva Questions

### For Mishael Julian (`2462184` — Architecture, Invigilation, Validator & Orchestrator)
- Walk through how `ALG-13` and `ALG-14` interact within a single session: why staff halls before building chiefs, and how does `WorkloadTracker` reset across ISO week boundaries?
- Show how `IndependentScheduleValidator` verifies non-adjacent columns (`|col_a - col_b| != 1`) without calling `allocation/seat_assigner.py`.
- Explain how `cli.py` and `orchestrator.py` distinguish exit code `0` (including valid `UNSTAFFED` / `SOFT_VIOLATION` schedules) from exit code `2` (invalid input) and exit code `3` (internal integrity bug).

### For Steven Mathew Binu (`2462157` — Week 2 Lead; Scheduling, Conflicts, Gaps & Supplementary)
- Trace `ALG-03` (`ConflictGraph`) on a student enrolled in 2 regular courses and 1 backlog course with `backlog_consent = True`. Which edges go into `same_session_forbidden` vs `same_day_forbidden`?
- Trace `ALG-06` two-pass scheduling on `EC-01` and explain why Pass 2 can never introduce a student clash.
- Trace `ALG-02` and `ALG-07` on `EC-08` when a holiday falls on Day 11 and Day 12 has only `FN` open.

### For Tanisha Chhetri (`2462160` — Week 3 Lead; Hall/Seat/Accessibility & Incremental Changes)
- Trace `ALG-09`, `ALG-10`, and `ALG-11` when packing a `35`-student course (`1` special-needs), a `9`-student course (`EC-02`), and a `10`-student course across ground-floor and first-floor halls with `7` columns.
- Trace `ALG-16` (`MARK_HALL_UNAVAILABLE`) step-by-step when same-session capacity fails and two smallest courses tie on enrolment count.
- Explain how `ALG-17` (`ADD_LATE_REGISTRANT`) handles multi-course atomicity and why SHA-256 session digests prove unaffected-session preservation (`ALG-19`).
