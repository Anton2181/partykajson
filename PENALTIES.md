# Solver Penalties Documentation

This document describes the penalties used by the schedule solver to optimize assignments.

## 1. Multi-Day Weekdays (Cascading)
**Rule Name:** `"Multi-Day Weekdays (e.g. Tue+Wed)"`
**Description:** Penalizes assigning a person to work on multiple weekdays within the same week.
**Logic:** Cascading (Geometric).
- Assignments on days marked with `day_num != 0` (Null) and `day_num != 7` (Sunday) are counted.
- **Formula:** `Cost = PenaltyPrice * 2^(WeekdaysWorked - 2)` (for Weekdays >= 2).
- **Example:**
    - 2 Weekdays: 1x Penalty ($2^0$)
    - 3 Weekdays: 2x Penalty ($2^1$)
    - 4 Weekdays: 4x Penalty ($2^2$)
    - 5 Weekdays: 8x Penalty ($2^3$)

## 2. Role Diversity (Cascading)
**Rule Name:** `"Role Diversity (Assignments in each capable family)"`
**Description:** Penalizes missing assignments in families (categories) where the person is capable.
**Logic:** Cascading (Geometric).
- For each family defined in the groups, checks if the person has at least one assignment.
- **Formula:** `Cost = BasePenalty * 2^(MissedFamilies - 1)` (for Missed >= 1).
- **Example:**
    - Miss 1 Family: 1x Base Penalty
    - Miss 2 Families: 2x Base Penalty
    - Miss 3 Families: 4x Base Penalty
    - Miss 4 Families: 8x Base Penalty

## 3. Underworked Team Member
**Rule Name:** `"Underworked Team Member (< 8 Effort)"`
**Description:** Huge penalty if a person's total effort is below the minimum threshold (default 8.0).
**Logic:** Binary. Active if TotalEffort < MinEffort.

## 4. Unassigned Group
**Rule Name:** `"Unassigned Group"`
**Description:** Penalty for leaving a group unassigned.
**Logic:** Binary per group.

## 5. Multi-Day General
**Rule Name:** `"Multi-Day General (Weekday+Sunday)"`
**Description:** Penalizes working on both a Weekday and Sunday in the schedule (global scope or per week depending on exact implementation, currently global tracking used implicitly via boolean checks).
**Logic:** Binary. Active if `HasWeekday` AND `HasSunday`.

## 6. Cooldown (Adjacent Weeks)
**Rule Name:** `"Cooldown (Adjacent Weeks)"`
**Description:** Penalizes working in consecutively linked groups (e.g., Week N -> Week N+1).
**Logic:**
- **Pairwise:** Penalty for working in both Group A and Group B where A->B is a cooldown link.
- **Geometric Streak:** Additional penalties for streaks of length 3, 4, 5+ (e.g., 3 consecutive weeks).
    - Length 3: +1x Penalty
    - Length 4: +2x Penalty

## 7. Intra-Week Cooldown
**Rule Name:** `"Intra-Week Cooldown (Same Week)"`
**Description:** Penalizes working in two conflicting groups within the same week.
**Logic:** Pairwise. Active if assigned to both linked groups.

## 8. Inefficient Assignment (Task Count)
**Rule Name:** `P_INEFFICIENT` (Internal)
**Description:** Penalizes coming in on a day to perform fewer than 2 tasks (if configured).
**Logic:** Active if `TasksOnDay < 2`.
