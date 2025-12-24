# Exceptions and Overrides

This document details how the solver handles "Exceptional" cases where standard optimization rules are bypassed or modified.

## 1. Manual Assignments
The strongest override in the system is a **Manual Assignment**.
- **Input**: If a group has `"assignee": "Name"` in the input JSON (from `groups.json`).
- **Effect**:
    1.  **Hard Constraint**: The solver is forced to assign this person (`x_group_person == 1`).
    2.  **Zero Cost**: The creation of variables ensures no alternate candidates are even considered.
    3.  **Exemption**: Manual assignments are typically exempt from penalties like "Equalization" (see below).

## 2. "Unavoidable" Candidates
Sometimes, a person is not manually assigned, but they are the **only** valid option due to candidate filtering.
- **Logic**: If `len(candidate_list) == 1`.
- **Effect**: The solver treats this identically to a Manual Assignment for the purpose of penalty exemptions.
- **Rationale**: You shouldn't be penalized for "hoarding" tasks if there was literally no one else who could do it.

## 3. Penalty Exemptions
Several rules have logic to "Ignore" manual or unavoidable assignments.

### A. Teaching/Assisting Equality
**Rule**: Penalize taking > 1 assignment in a family.
**Exception**:
- Assignments that are **Manual** or **Unavoidable** do NOT count towards the "Hoarding" penalty *if* they are the only ones.
- The penalty only triggers if the solver *chooses* to add **Auto-Assignments** on top of existing ones.
- **Logic**: `Cost > 0` IF `Count > 1` AND `HasAutoAssignment == True`.

### B. Cooldowns
**Rule**: Penalize working adjacent weeks.
**Exception**:
- If the assignment in Week N **AND** the assignment in Week N+1 are **both** Manual/Unavoidable, the penalty is skipped.
- **Rationale**: If the schedule dictates that a person *must* work these weeks (e.g., fixed rotation), the solver shouldn't fight it or report it as a "Bad" decision.

## 4. Priority Lists
The input data can specify strict subsets of candidates via `filtered_priority_candidates_list`.
- **Logic**: If a `priority_list` exists and is not empty, the solver **ONLY** considers candidates in this list. All other "techincally capable" candidates in the broader list are ignored.
- **Use Case**: This allows the UI/User to narrow down the search space ("Only consider these 3 people for this specific Shift").

## 5. Split Roles & Dual Capability ("Both")
Some team members are marked as **"Both"** (Leader + Follower).
- **Standard Logic**: Users marked as "Both" appear in candidate lists for *Role: Leader* AND *Role: Follower* tasks.
- **Priority Handling**:
    - If a task requires a "Leader" and has a Starred Priority list, a "Both" user is **only** considered a priority candidate if they are manually starred *for that specific task*.
    - **Exception**: If a "Both" user is the **ONLY** starred candidate available for a Split Group (one Leader slot, one Follower slot), the system may infer priority contextually, but generally, explicit starring is preferred to avoid ambiguity.

