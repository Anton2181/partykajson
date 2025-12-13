#!/bin/bash
set -e

# Define paths
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_INTEL="$PROJECT_ROOT/.venv_intel"
BUILD_SCRIPT="$PROJECT_ROOT/src/build.py"

echo "=========================================="
echo "   Building Partyka Assigner Script for Intel    "
echo "   (Compatible with ALL Macs via Rosetta) "
echo "=========================================="

# 1. Create dedicated Intel venv if it doesn't exist
if [ ! -d "$VENV_INTEL" ]; then
    echo "[1/3] Creating isolated Intel virtual environment (.venv_intel)..."
    # Create venv using standard python, but the *architecture* will be decided when we run binaries inside it?
    # Actually, best to run the creation under arch x86_64 to be sure, though venv structure is mostly text.
    arch -x86_64 python3 -m venv "$VENV_INTEL"
else
    echo "[1/3] Using existing .venv_intel..."
fi

# 2. Install/Update Requirements under Intel Architecture
echo "[2/3] Installing dependencies for x86_64..."
# Using the pip inside the new venv, forcing x86_64 execution
arch -x86_64 "$VENV_INTEL/bin/pip" install --upgrade pip
arch -x86_64 "$VENV_INTEL/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"

# 3. Run Build Script
echo "[3/3] Running Build..."
arch -x86_64 "$VENV_INTEL/bin/python" "$BUILD_SCRIPT"

echo "=========================================="
echo "   BUILD SUCCESSFUL"
echo "=========================================="
echo "Artifacts are in: $PROJECT_ROOT/dist"
echo "You can now zip the app and 'data' folder for distribution."
