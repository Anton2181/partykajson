# Solver Penalties Documentation

This document describes the penalties used by the schedule solver to optimize assignments.

## 1. Multi-Day Weekdays (Cascading)
**Rule Name:** `"Multi-Day Weekdays (e.g. Tue+Wed)"`
**Description:** Penalizes assigning a person to work on multiple weekdays within the same week.
**Logic:** Cascading (Geometric).
- Assignments on days marked with `day_num != 0` (Null) and `day_num != 7` (Sunday) are counted.
- **Formula:** `Cost = PenaltyPrice * 3^(WeekdaysWorked - 2)` (for Weekdays >= 2).
- **Example:**
    - 2 Weekdays: 1x Penalty ($3^0$)
    - 3 Weekdays: 3x Penalty ($3^1$)
    - 4 Weekdays: 9x Penalty ($3^2$)
    - 5 Weekdays: 27x Penalty ($3^3$)

## 2. Teaching/Assisting Preference
**Rule Name:** `"Teaching/Assisting Preference"`
**Description:** Ensures teachers are assigned to Teaching (primary) or Assisting families, and assistants are assigned to Assisting.
**Logic:**
- **Teachers (Candidates for 'Teaching'):**
    - If assigned to 'Teaching': No Penalty.
    - If assigned to only 'Assisting': Half Penalty (0.5x).
    - If assigned neither: Full Penalty (1.0x).
- **Assistants (Candidates only for 'Assisting'):**
    - If assigned to 'Assisting': No Penalty.
    - If not assigned: Full Penalty (1.0x).

## 3. Teaching/Assisting Equality
**Rule Name:** `"Teaching/Assisting Equality"`
**Description:** Penalizes taking more than 1 assignment within the "Teaching" or "Assisting" families to promote sharing.
**Refinement:** Purely pre-assigned schedules are exempt. The penalty only activates if the solver adds at least one new "Auto" assignment to the family.
> **Note:** "Unavoidable" assignments (where the person is the only valid candidate) are treated as **Manual** and do not trigger the penalty, even if not explicitly pre-assigned.
**Logic:** Geometric penalty for excess assignments ($N > 1$) per family.
- **Formula:** $Cost = P \cdot 3^{N-2}$ (for $N \ge 2$).
- **Example:**
    - 2 Assignments: 1x Penalty ($3^0$)
    - 3 Assignments: 3x Penalty ($3^1$)
    - 4 Assignments: 9x Penalty ($3^2$)

## 4. Role Diversity (Cascading)
**Rule Name:** `"Role Diversity (Assignments in each capable family)"`
**Description:** Penalizes missing assignments in families (categories) where the person is capable.
**Logic:** Cascading (Geometric).
- For each family defined in the groups, checks if the person has at least one assignment.
- **Formula:** `Cost = BasePenalty * 3^(MissedFamilies - 1)` (for Missed >= 1).
- **Example:**
    - Miss 1 Family: 1x Base Penalty
    - Miss 2 Families: 3x Base Penalty
    - Miss 3 Families: 9x Base Penalty
    - Miss 4 Families: 27x Base Penalty

## 5. Underworked Team Member
**Rule Name:** `"Underworked Team Member (< Threshold)"`
**Description:** Huge penalty if a person's total effort is below the minimum threshold (Configured in `penalty_config.json`, default 8.0).
**Logic:** Binary. Active if TotalEffort < ConfiguredThreshold.

## 6. Unassigned Group
**Rule Name:** `"Unassigned Group"`
**Description:** Penalty for leaving a group unassigned.
**Logic:** Binary per group.

## 7. Multi-Day General
**Rule Name:** `"Multi-Day General (Weekday+Sunday)"`
**Description:** Penalizes working on both a Weekday and Sunday in the schedule (global scope or per week depending on exact implementation, currently global tracking used implicitly via boolean checks).
**Logic:** Binary. Active if `HasWeekday` AND `HasSunday`.

## 8. Cooldown (Adjacent Weeks)
**Rule Name:** `"Cooldown (Adjacent Weeks)"`
**Description:** Penalizes working in consecutively linked groups (e.g., Week N -> Week N+1).
**Logic:**
- **Pairwise:** Penalty for working in both Group A and Group B where A->B is a cooldown link.
- **Geometric Streak:** Additional penalties for streaks of length 3, 4, 5+ (e.g., 3 consecutive weeks).
    - Length 3: +1x Penalty
    - Length 4: +3x Penalty
    - Length 5: +9x Penalty

## 9. Intra-Week Cooldown
**Rule Name:** `"Intra-Week Cooldown (Same Week)"`
**Description:** Penalizes working in two conflicting groups within the same week.
**Logic:** Pairwise. Active if assigned to both linked groups.

## 10. Inefficient Assignment (Task Count)
**Rule Name:** `P_INEFFICIENT` (Internal)
**Description:** Penalizes coming in on a day to perform fewer than 2 tasks (if configured).
**Logic:** Active if `TasksOnDay < 2`.

## 11. Effort Equalization (Squared Deviation)
**Rule Name:** `"Effort Equalization (Squared Deviation)"`
**Description:** Soft penalty to encourage all team members to be close to the target effort (Configured Threshold, default 8.0).
**Logic:** Quadratic.
- **Formula:** $Cost = P \cdot \lfloor(Effort - Threshold)^2\rfloor$.
- Note: Effort is scaled by 10 internally, so we calculate $SqDiff = (ScaledEffort - ScaledThreshold)^2$ and then normalize by dividing by 100 to get the deviation squared in range.


## 11. Code Dependencies (Performance Optimization)
Some penalties share computationally expensive logic. To optimize performance, the solver groups these rules into shared blocks. If **all** rules in a block are disabled (Penalty 0), the overhead for that logic is skipped entirely.

### A. Teaching Logic Block
**Shared Computation:** `Rule 2: Preference` and `Rule 3: Equality`.
- **Logic:** Sorting groups into "Teaching" vs "Assisting" families and identifying capable candidates.
- **Dependency:** If **both** rules are 0, this classification is skipped. If **either** is active, both have access to the pre-computed group lists.

### B. Daily Logic Block
**Shared Computation:** `Rule 1: Multi-Day Weekdays`, `Rule 7: Multi-Day General`, and `Rule 10: Inefficient Day`.
- **Logic:** Mapping every group to a specific `DayKey` (e.g. `Week1_Tue`) and generating `worked_var` booleans for every person/day.
- **Dependency:** If **all three** are 0, the solver never calculates daily schedules. If **any** is active, the daily map is built once and shared.
