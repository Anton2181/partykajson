# Design Philosophy

This document outlines the core principles behind the solver's design, focusing on flexibility, scalability, and "Soft" regulation.

## 1. The Penalty Ladder: Relative Priority
The core concept of our optimization strategy is the **Penalty Ladder** (defined in `penalty_config.json`).
- **Hierarchy**: Rules are ordered from **Most Important** (Top) to **Least Important** (Bottom).
- **Geometric Scaling**: We use a `penalty_ratio` (default 10) to strictly enforce this hierarchy.
    - Rule 1 Cost: $10^9$
    - Rule 2 Cost: $10^8$
    - ...
    - Rule 10 Cost: $10^0$
- **Why?**: This ensures that **1 violation of a higher rule is ALWAYS worse than ANY number of violations of lower rules**. The solver will never "trade" a critical failure (like leaving a group empty) just to fix a minor inconvenience (like a slight effort imbalance).

## 2. Geometric Penalties ($3^N$)
Within a specific rule (e.g., "Don't work too many days in a row"), we often use a **Geometric Progression** (Base 3) for costs: $Cost = P \cdot 3^{N-2}$.
- **1 Excess**: Small cost. (Acceptable if necessary).
- **2 Excess**: 3x Cost. (Painful).
- **3 Excess**: 9x Cost. (Very bad).
- **Philosophy**: "Rare exceptions are okay, but don't abuse them." This allows the solver to find solutions in tight constraints by making *one* person suffer a bit, rather than failing completely.

## 3. "Pay for What You Use" (Modularity)
The codebase is designed to support a dynamic list of rules without performance penalties.
- **Configurable**: You can add or remove strings from the `ladder` list in `penalty_config.json`.
- **Zero Overhead**: In `solver.py`, every complex logic block is guarded by `if PENALTY_VALUE > 0:`.
    - If you remove "Role Diversity" from the config, `PENALTY_VALUE` becomes 0.
    - The solver **skips** the entire block of code that calculates diversity constraints.
    - This means you can have 50 available rules but only run 3, and it will be as fast as a solver designed for only those 3.

## 4. Soft vs Hard Constraints
We prefer **Soft Constraints** (Penalties) over **Hard Constraints** (Forbidden states).
- **Hard**: "Person CANNOT work 3 days." -> Result: Solver returns `INFEASIBLE` (Crash/No Schedule).
- **Soft**: "Person PAYS 1,000,000 to work 3 days." -> Result: Solver avoids it if possible, but if it's the *only* way to cover the shift, it does it and reports the cost.
- **Benefit**: The user always gets a schedule, even if it's imperfect. They can then see *where* the friction is (via the Penalties report) and adjust manually.
