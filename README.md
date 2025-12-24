# Partyka Assigner Script

**Automated Scheduling & Assignment Solver**

The Partyka Assigner Script is a Python-based tool designed to automate the complex task of assigning roles and shifts to team members. It uses the **Google OR-Tools CP-SAT** solver to find optimized schedules that respect hard constraints (availability, exclusions) while minimizing soft penalties (fairness, preferences, burnout prevention).

## Quick Start

### 1. Prerequisites
- Python 3.10+
- Virtual Environment (Recommended)

### 2. Setup
```bash
# Create virtual env
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Running the Solver
To run the full pipeline (Data Download -> Processing -> Solving):
```bash
python src/step_04_run_solver.py
```
*Note: Ensure you have the necessary credentials in `.env` if verifying Google Sheets integration, though local mock data is often used for dev.*

## Documentation Map

Detailed documentation is located in the `docs/` folder:

- **[SOLVER_ARCHITECTURE.md](docs/SOLVER_ARCHITECTURE.md)**: High-level overview of how the solver interprets data, builds the model, and finds solutions.
- **[PENALTIES.md](docs/PENALTIES.md)**: The "Rulebook". Detailed geometric formulas and logic for every penalty (Role Diversity, Cooldowns, etc.).
- **[EXCEPTIONS_AND_OVERRIDES.md](docs/EXCEPTIONS_AND_OVERRIDES.md)**: Explains when rules are broken. Covers Manual Assignments, Unavoidable Candidates, and Priority Lists.
- **[DATA_PIPELINE.md](docs/DATA_PIPELINE.md)**: How raw CSVs are transformed into the `groups.json` format.
- **[DESIGN_PHILOSOPHY.md](docs/DESIGN_PHILOSOPHY.md)**: The "Why". Explains the Penalty Ladder and the preference for Soft Constraints.
- **[DISTRIBUTION.md](docs/DISTRIBUTION.md)**: How to build (`src/build.py`) and share the standalone application for Mac/Windows.

## Project Structure

- `src/`: Source code.
  - `solver/`: Core logic (`solver.py`, `penalties.py`).
  - `...`: Pipeline scripts.
- `data/`: Input/Output data.
  - `raw/`: CSVs from Google Sheets.
  - `processed/`: JSONs used by the solver.
- `tests/`: Pytest suite.
- `docs/`: Markdown documentation.
