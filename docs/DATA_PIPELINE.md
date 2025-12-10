# Data Pipeline: From Raw to Solver

This document explains the "Preprocessing" phase—how raw CSV data is transformed into the structured `groups.json` that the solver consumes.

## Step 1: Download (`src/step_01_download_data.py`)
*Currently skipped in local dev mode.*
- **Purpose**: Fetches the latest schedule and availability data from Google Sheets.
- **Output**: Raw CSV files in `data/raw/` (e.g., `january_2026.csv`).

## Step 2: Conversion (`src/step_02_convert_data.py`)
- **Purpose**: Standardization.
- **Process**:
    1.  **Task Availability**: Parses `task_availability.csv`.
        -   Extracts who *can* do what.
        -   Output: `data/processed/tasks.json`.
    2.  **Calendar Availability**: Parses `calendar_availability.csv`.
        -   Extracts who is *free* when.
        -   Handles "All Evening" -> "20-21, 21-22, 22-00" propagation.
        -   Output: `data/processed/calendar.json`.
    3.  **Schedule Parsing**: Parses `january_2026.csv`.
        -   Generates unique **Task IDs** (`T15_2_1_1`) for every row.
        -   Calculates the initial **Candidate List** for each task by intersecting *Capability* (Step 2.1) and *Availability* (Step 2.2).
        -   Output: `data/processed/january_2026_tasks.json`.

## Step 3: Group Aggregation (`src/step_03_aggregate_groups.py`)
This is the most critical preprocessing step. The solver does not assign "Tasks"; it assigns "Groups".

### Why Groups?
A "Shift" often consists of multiple related tasks (e.g., "Teaching" + "Preparation" + "Mentoring"). We don't want to assign Person A to "Teaching" and Person B to "Preparation" for the *same class*.
> **A Group is an atomic unit of assignment.** One Person is assigned to One Group.

### The Aggregation Process
1.  **Task Families**: The script reads `data/task_families.json`. This defines patterns like:
    -   *Family*: "Teaching"
    -   *Group Definition*: "Teacher" requires [Preparation, Conducting, Feedback].
2.  **Pattern Matching**: The script scans the list of Tasks (from Step 2).
    -   If it finds a set of tasks that matches a Group Definition (same Week, same Day), it bundles them into a **Group**.
    -   **Strict Consumption**: Once tasks are bundled into a Group, they are removed from the pool.
3.  **Candidate Intersection**:
    -   The Group's candidate list is the **INTERSECTION** of candidates for all its component tasks.
    -   *Example*: To be assigned to the "Teacher Group", you must be available for *both* "Preparation" (20:00) *and* "Teaching" (21:00).
4.  **Standalone Groups**:
    -   Any tasks left over (not part of a Family pattern) become "Standalone Groups" of 1 task.

### Outputs
-   `data/processed/january_2026_groups.json`: The final input for the Solver.
-   Contains Group IDs (`G15_2_1_1`), Candidate Lists, and Conflict relationships (Exclusive/Cooldowns).

## Step 4: Solver
(See [SOLVER_ARCHITECTURE.md](SOLVER_ARCHITECTURE.md))
