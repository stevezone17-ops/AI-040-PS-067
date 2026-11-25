# 10 — Input & Output Data Contracts (Provisional)

**Document Status:** **PROVISIONAL SPECIFICATION** — Subject to Official Sample Dataset Schema Alignment  
**Related Documents:** [`02_SOFTWARE_REQUIREMENTS_SPECIFICATION.md`](02_SOFTWARE_REQUIREMENTS_SPECIFICATION.md), [`05_ASSUMPTION_REGISTER.md`](05_ASSUMPTION_REGISTER.md), [`06_CONSTRAINT_CATALOGUE.md`](06_CONSTRAINT_CATALOGUE.md), [`08_DOMAIN_MODEL.md`](08_DOMAIN_MODEL.md)

> [!IMPORTANT]
> **Explicit Provisional Disclaimer:** Official input schemas and sample expected outputs have **not** been provided in the Week 1 problem brief. All file formats, column headers, and JSON structures defined below are **provisional team contracts** engineered to represent every requirement in `FR-01`–`FR-06`, `BR-01`–`BR-12`, and `EC-01`–`EC-08`. All parsing and formatting are isolated inside `src/exam_engine/io/` and `src/exam_engine/reporting/` adapters (`NFR-06`) so official file schemas can be plugged in during Week 2/3 without altering any core domain entity or algorithm.

---

## 1. Adapter Isolation Architecture (`NFR-06`)

```text
[Provisional / Official Files] <---> [InputAdapter / OutputFormatter Protocols] <---> [Pure Domain Models]
    (CSV / JSON / TXT)                  (src/exam_engine/io/ & reporting/)            (src/exam_engine/domain/)
```

- **`InputReaderProtocol`:** Exposes `load_problem_instance(input_dir: Path) -> RawProblemPayload` and `load_commands(cmd_path: Path) -> list[RawCommandPayload]`.
- **`ReportWriterProtocol`:** Exposes `write_reports(state: ScheduleState, output_dir: Path) -> None`.
- **Encoding & Line Endings:** UTF-8 without BOM; `\n` (LF) line terminators on output; case-insensitive trimmed identifier normalisation (`" cs301 "` -> `"CS301"`); flexible boolean parsing (`true/1/yes/Y` vs `false/0/no/N`).

---

## 2. Provisional Input Schemas

### 2.1 `courses.csv`
- **Primary Identifier:** `course_code` (`CN-01`).
- **Duplicate / Missing Handling:** Duplicate `course_code` raises `ERR_DUPLICATE_KEY`; missing required field raises `ERR_MISSING_REQUIRED_FIELD`; invalid duration/credits raises `ERR_INVALID_COURSE`.

| Column | Type | Req? | Allowed Values / Constraints | Domain Mapping |
| :--- | :--- | :---: | :--- | :--- |
| `course_code` | `string` | Yes | Non-empty alphanumeric/hyphen (`[A-Z0-9_-]+`) | `Course.course_code` |
| `title` | `string` | No | Free text (default `""`) | `Course.title` |
| `department` | `string` | Yes | Non-empty department code (e.g., `CSE`, `ECE`, `AIML`, `MAT`) | `Course.department` |
| `semester` | `int` | Yes | Integer `>= 1` | `Course.semester` |
| `credits` | `int` | Yes | Integer `>= 0` (`>= 4` = Core, `< 4` = Elective per `BR-02`) | `Course.credits` |
| `duration_hours` | `int` | Yes | Strictly `2` or `3` (`FR-01`) | `Course.duration_hours` |
| `is_supplementary` | `bool` | No | `true` / `false` (default `false`; `true` triggers `BR-12`, `AS-012`) | `Course.is_supplementary` |

**Illustrative Example (`courses.csv`):**
```csv
course_code,title,department,semester,credits,duration_hours,is_supplementary
AIML601,Deep Learning Architectures,AIML,6,4,3,false
AIML602,Natural Language Processing,AIML,6,4,3,false
CSE615,Cloud Native Systems,CSE,6,3,2,false
MAT401S,Probability & Statistics (Supplementary),MAT,4,4,3,true
```

---

### 2.2 `students.csv`
- **Primary Identifier:** `register_number` (`CN-02`).
- **Referential Integrity:** Every code in pipe-delimited `backlog_courses` (if populated) must exist in `courses.csv` (`ERR_UNKNOWN_REFERENCE`) and match an enrolment in `enrolments.csv` (`ALG-01`).

| Column | Type | Req? | Allowed Values / Constraints | Domain Mapping |
| :--- | :--- | :---: | :--- | :--- |
| `register_number` | `string` | Yes | Unique student identifier (e.g., `2462157`) | `Student.register_number` |
| `programme` | `string` | Yes | Non-empty programme code (e.g., `BTech-AIML`) | `Student.programme` |
| `semester` | `int` | Yes | Integer `>= 1` | `Student.semester` |
| `special_needs` | `bool` | No | `true` / `false` (default `false`; triggers `BR-06` Row 1 + 20m) | `Student.special_needs` |
| `backlog_courses` | `string` | No | Pipe-delimited `course_code`s (e.g., `MAT401S\|CS302`) or empty | Cross-synced to `Enrolment.is_backlog` |
| `backlog_consent` | `bool` | No | `true` / `false` (`BACKLOG_CONSENT` flag per `BR-01`) | `Student.backlog_consent` |

**Illustrative Example (`students.csv`):**
```csv
register_number,programme,semester,special_needs,backlog_courses,backlog_consent
2462101,BTech-AIML,6,false,,false
2462115,BTech-AIML,6,true,,false
2462140,BTech-AIML,6,false,MAT401S,true
```

---

### 2.3 `enrolments.csv`
- **Primary Identifier:** Composite `(register_number, course_code)` (`CN-03`).
- **Referential Integrity:** `register_number` must exist in `students.csv`; `course_code` must exist in `courses.csv` (`ERR_UNKNOWN_REFERENCE`). Duplicate pairs raise `ERR_DUPLICATE_ENROLMENT`. *(Note: If the official dataset embeds enrolment lists inside `courses.csv` or `students.csv` instead of a separate `enrolments.csv`, `InputAdapter` unpacks them into canonical `Enrolment` records transparently.)*

| Column | Type | Req? | Allowed Values / Constraints | Domain Mapping |
| :--- | :--- | :---: | :--- | :--- |
| `register_number` | `string` | Yes | Foreign key -> `students.csv` | `Enrolment.register_number` |
| `course_code` | `string` | Yes | Foreign key -> `courses.csv` | `Enrolment.course_code` |
| `is_backlog` | `bool` | No | `true` / `false` (OR-merged with `students.backlog_courses` & `courses.is_supplementary`) | `Enrolment.is_backlog` |

**Illustrative Example (`enrolments.csv`):**
```csv
register_number,course_code,is_backlog
2462101,AIML601,false
2462115,AIML601,false
2462140,AIML601,false
2462140,MAT401S,true
```

---

### 2.4 `halls.csv`
- **Primary Identifier:** `hall_id` (`CN-04`).
- **Accessibility Representation:** `floor == 0` denotes ground floor (`BR-06`).
- **Validation:** `rows >= 1`, `columns >= 1`, `floor >= 0`, `1 <= capacity <= rows * columns` (`ERR_INVALID_HALL_DIMENSIONS`, `AS-003`).

| Column | Type | Req? | Allowed Values / Constraints | Domain Mapping |
| :--- | :--- | :---: | :--- | :--- |
| `hall_id` | `string` | Yes | Unique hall ID (e.g., `BLK1-G01`) | `Hall.hall_id` |
| `building_code` | `string` | Yes | Non-empty building ID (derives `Building` entity) | `Hall.building_code` |
| `floor` | `int` | Yes | Integer `>= 0` (`0` = Ground Floor; `1` = First Floor, etc.) | `Hall.floor` |
| `rows` | `int` | Yes | Integer `>= 1` | `Hall.rows` |
| `columns` | `int` | Yes | Integer `>= 1` | `Hall.columns` |
| `capacity` | `int` | Yes | `1 <= capacity <= rows * columns` | `Hall.capacity` |

**Illustrative Example (`halls.csv`):**
```csv
hall_id,building_code,floor,rows,columns,capacity
BLK1-G01,BLOCK-1,0,10,8,80
BLK1-101,BLOCK-1,1,10,6,60
BLK2-G01,BLOCK-2,0,8,7,56
```

---

### 2.5 `invigilators.csv`
- **Primary Identifier:** `invigilator_id` (`CN-05`).
- **Additional Duties Representation (`EC-05`, `AS-018`):** `external_duties` encodes pipe-delimited `YYYY-MM-DD@HH:MM-HH:MM` busy windows alongside pipe-delimited full-day `unavailable_dates` (`YYYY-MM-DD`).

| Column | Type | Req? | Allowed Values / Constraints | Domain Mapping |
| :--- | :--- | :---: | :--- | :--- |
| `invigilator_id` | `string` | Yes | Unique invigilator ID (e.g., `INV-001`) | `Invigilator.invigilator_id` |
| `name` | `string` | No | Free text | `Invigilator.name` |
| `department` | `string` | Yes | Non-empty department code | `Invigilator.department` |
| `max_weekly_sessions` | `int` | Yes | Integer `4 <= val <= 8` (`BR-07`) | `Invigilator.max_weekly_sessions` |
| `unavailable_dates` | `string` | No | Pipe-delimited `YYYY-MM-DD` ISO dates | `Invigilator.unavailable_dates` |
| `external_duties` | `string` | No | Pipe-delimited `YYYY-MM-DD@HH:MM-HH:MM` (`EC-05`) | `Invigilator.external_duties` |

**Illustrative Example (`invigilators.csv`):**
```csv
invigilator_id,name,department,max_weekly_sessions,unavailable_dates,external_duties
INV-001,Dr. Rao,PHY,6,2026-12-05,2026-12-03@17:30-19:00
INV-002,Prof. Nair,CSE,5,,2026-12-03@17:15-18:30
INV-003,Dr. Thomas,MAT,8,,
```

---

### 2.6 `exam_window.json`
- **Purpose:** Defines calendar window, full-day holidays, and partial-day session closures (`EC-08`, `AS-016`).
- **Validation:** `start_date <= end_date`; `sessions` definitions match `09:30-12:30` (`FN`) and `14:00-17:00` (`AN`); yields `>= 1` active session (`CN-06`).

```json
{
  "window_id": "END_SEM_DEC_2026",
  "start_date": "2026-12-01",
  "end_date": "2026-12-12",
  "sessions": {
    "FN": { "start_time": "09:30", "end_time": "12:30" },
    "AN": { "start_time": "14:00", "end_time": "17:00" }
  },
  "holidays": ["2026-12-06", "2026-12-10"],
  "closed_slots": [
    { "date": "2026-12-12", "slot": "AN", "reason": "Final day afternoon convocation setup (EC-08)" }
  ]
}
```

---

### 2.7 `commands.json`
- **Purpose:** Ordered array of incremental change commands (`FR-05`, `BR-09`, `BR-10`, `BR-11`).
- **Validation:** Unique `command_id`s; `type` in `{"POSTPONE_COURSE", "MARK_HALL_UNAVAILABLE", "ADD_LATE_REGISTRANT"}`.

```json
{
  "commands": [
    {
      "command_id": "CMD-001",
      "type": "POSTPONE_COURSE",
      "course_code": "AIML601",
      "min_target_date": null,
      "reason": "Paper setter transit delay"
    },
    {
      "command_id": "CMD-002",
      "type": "MARK_HALL_UNAVAILABLE",
      "hall_id": "BLK1-101",
      "target_sessions": ["2026-12-03_FN"],
      "reason": "AC electrical maintenance"
    },
    {
      "command_id": "CMD-003",
      "type": "ADD_LATE_REGISTRANT",
      "student": {
        "register_number": "2462199",
        "programme": "BTech-AIML",
        "semester": 6,
        "special_needs": false,
        "backlog_consent": false
      },
      "enrolments": [
        { "course_code": "AIML601", "is_backlog": false },
        { "course_code": "CSE615", "is_backlog": false }
      ]
    }
  ]
}
```

---

## 3. Provisional Output Contracts & Deterministic Formatting (`FR-06`, `AS-033`)

### 3.1 `timetable.csv`
- **Sort Order:** `(exam_date ASC, slot_order [FN=0, AN=1] ASC, course_code ASC)`.
- **Columns:** `session_id,exam_date,slot,start_time,base_end_time,course_code,department,semester,credits,is_core,duration_hours,is_supplementary,enrolment_count,used_gap_soft_fallback`

```csv
session_id,exam_date,slot,start_time,base_end_time,course_code,department,semester,credits,is_core,duration_hours,is_supplementary,enrolment_count,used_gap_soft_fallback
2026-12-01_FN,2026-12-01,FN,09:30,12:30,AIML601,AIML,6,4,true,3,false,65,false
2026-12-11_AN,2026-12-11,AN,14:00,17:00,MAT401S,MAT,4,4,true,3,true,14,false
```

### 3.2 `hall_plan.csv`
- **Sort Order:** `(exam_date ASC, slot_order ASC, hall_id ASC, column_slot [ODD=0, EVEN=1] ASC)`.
- **Columns:** `session_id,exam_date,slot,building_code,hall_id,floor,hall_capacity,duration_hours,effective_start_time,effective_end_time,has_special_needs,column_slot,course_code,department,allocated_students,required_hall_invigilators`

```csv
session_id,exam_date,slot,building_code,hall_id,floor,hall_capacity,duration_hours,effective_start_time,effective_end_time,has_special_needs,column_slot,course_code,department,allocated_students,required_hall_invigilators
2026-12-01_FN,2026-12-01,FN,BLOCK-1,BLK1-G01,0,80,3,09:30,12:50,true,ODD,AIML601,AIML,40,2
2026-12-01_FN,2026-12-01,FN,BLOCK-1,BLK1-G01,0,80,3,09:30,12:50,true,EVEN,ECE609,ECE,8,2
```

### 3.3 `seat_assignments.csv`
- **Sort Order:** `(exam_date ASC, slot_order ASC, hall_id ASC, row ASC, column ASC)`.
- **Columns:** `session_id,exam_date,slot,building_code,hall_id,floor,seat_number,seat_label,row,column,course_code,register_number,is_special_needs`

```csv
session_id,exam_date,slot,building_code,hall_id,floor,seat_number,seat_label,row,column,course_code,register_number,is_special_needs
2026-12-01_FN,2026-12-01,FN,BLOCK-1,BLK1-G01,0,1,R01C01,1,1,AIML601,2462115,true
2026-12-01_FN,2026-12-01,FN,BLOCK-1,BLK1-G01,0,2,R01C02,1,2,ECE609,2461004,false
2026-12-01_FN,2026-12-01,FN,BLOCK-1,BLK1-G01,0,3,R01C03,1,3,AIML601,2462101,false
```

### 3.4 `seat_maps.txt`
- **Sort Order:** `(exam_date ASC, slot_order ASC, hall_id ASC)`; rows `1..R`, columns `1..C`.
- **Format:** Fixed-width deterministic ASCII table per occupied `(session_id, hall_id)` (`*` marks `special_needs == True`):
```text
================================================================================
SESSION: 2026-12-01_FN | HALL: BLK1-G01 (BLOCK-1, Floor 0) | TIME: 09:30-12:50
COURSES: ODD=AIML601 (40) | EVEN=ECE609 (8) | OCCUPIED: 48/80 | STAFF REQ: 2
--------------------------------------------------------------------------------
Row 01: [R01C01 AIML601:2462115*] [R01C02 ECE609 :2461004 ] [R01C03 AIML601:2462101 ] ...
Row 02: [R02C01 AIML601:2462109 ] [R02C02 ECE609 :2461019 ] [R02C03 AIML601:2462112 ] ...
================================================================================
```

### 3.5 `invigilation_roster.csv`
- **Sort Order:** `(exam_date ASC, slot_order ASC, building_code ASC, role_order [BUILDING_CHIEF=0, HALL_INVIGILATOR=1] ASC, hall_id_or_empty ASC, slot_index ASC)`.
- **Columns:** `assignment_id,session_id,exam_date,slot,building_code,hall_id,role,slot_index,status,invigilator_id,invigilator_department,duty_start_time,duty_end_time`

```csv
assignment_id,session_id,exam_date,slot,building_code,hall_id,role,slot_index,status,invigilator_id,invigilator_department,duty_start_time,duty_end_time
2026-12-01_FN:CHIEF:BLOCK-1:1,2026-12-01_FN,2026-12-01,FN,BLOCK-1,,BUILDING_CHIEF,1,ASSIGNED,INV-003,MAT,09:30,12:50
2026-12-01_FN:HALL:BLK1-G01:1,2026-12-01_FN,2026-12-01,FN,BLOCK-1,BLK1-G01,HALL_INVIGILATOR,1,ASSIGNED,INV-001,PHY,09:30,12:50
2026-12-01_FN:HALL:BLK1-G01:2,2026-12-01_FN,2026-12-01,FN,BLOCK-1,BLK1-G01,HALL_INVIGILATOR,2,UNSTAFFED,,,09:30,12:50
```

### 3.6 `violations.json`
- **Sort Order:** Grouped/sorted by `(category_order, session_id_or_empty, entity_ids, code)`.
```json
{
  "state_version": 2,
  "summary": {
    "soft_violations": 1,
    "resource_shortages": 1,
    "unscheduled_courses": 0,
    "displacement_notices": 1,
    "rejected_changes": 1
  },
  "active_violations": [
    {
      "violation_id": "VIOL-0001",
      "category": "SOFT_VIOLATION",
      "code": "CORE_GAP_SOFT_VIOLATION",
      "rule_id": "BR-02",
      "session_id": "2026-12-02_FN",
      "entity_ids": ["AIML602", "AIML601"],
      "message": "No gap-compliant slot available; scheduled on consecutive day 2026-12-02.",
      "source_command_id": null
    },
    {
      "violation_id": "VIOL-0002",
      "category": "RESOURCE_SHORTAGE",
      "code": "HALL_UNSTAFFED",
      "rule_id": "BR-08",
      "session_id": "2026-12-01_FN",
      "entity_ids": ["BLK1-G01"],
      "message": "Eligible invigilator pool exhausted for slot 2 of hall BLK1-G01.",
      "source_command_id": null
    }
  ],
  "rejected_changes": [
    {
      "command_id": "CMD-003",
      "code": "REJECTED_CLASH",
      "rule_id": "BR-11",
      "conflicting_courses": ["AIML601", "AIML603"],
      "message": "Late registration for 2462199 causes same-day clash between AIML601 and AIML603."
    }
  ]
}
```

### 3.7 `change_results.json` & `schedule_state.json`
- **`change_results.json`:** Ordered list matching `commands.json` execution order (`1..K`), recording `command_id`, `change_type`, `status`, `affected_sessions`, `conflicting_courses`, `displaced_courses`, `unaffected_sessions_verified`, and `reason`.
- **`schedule_state.json`:** Canonical JSON serialisation (`sort_keys=True`) of `ScheduleState` allowing standalone resumption of incremental commands (`--resume-state schedule_state.json`) without re-running initial synthesis!
