#!/usr/bin/env bash
set -euo pipefail

# NOTE: Maintained on the `feat-taxon-autocomplete` branch while `pyinaturalist` and
# `pyinaturalist-convert` use temporary git sources. Before merging back into `main`,
# replace git dependencies/sources with published versioned releases.

# 1. Configuration & Prereq Checks
ORG_NAME="dronefly-garden"
BOT_MEMBERS=("dronefly-cli" "dronefly-core" "dronefly-discord" "dronefly-miner" "dronefly")
ALL_REPOS=("dronefly-cli" "dronefly-core" "dronefly-discord" "dronefly-doc" "dronefly-miner" "dronefly")
TARGET_PYTHON="3.11"

echo "=== Setting up Dronefly Monorepo Workspace ==="

for cmd in git python3 uv pre-commit; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "Error: Required tool '$cmd' is not installed." >&2
        exit 1
    fi
done

# Ensure Python 3.11 is available via uv
if ! uv python find "$TARGET_PYTHON" &> /dev/null; then
    echo "Python $TARGET_PYTHON not found. Installing via uv..."
    uv python install "$TARGET_PYTHON"
fi

# 2. Establish Monorepo Directory Structure and Clones
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRONEFLY_DIR="$(dirname "$SCRIPT_DIR")"
PARENT_DIR="$(dirname "$DRONEFLY_DIR")"
MONOREPO_DIR="$PARENT_DIR/dronefly-monorepo"

echo "Dronefly repo dir: $DRONEFLY_DIR"
echo "Ensuring monorepo root at: $MONOREPO_DIR"
mkdir -p "$MONOREPO_DIR"

# Ensure all member repositories exist in the parent directory
cd "$PARENT_DIR"
for repo in "${ALL_REPOS[@]}"; do
    if [ ! -d "$repo" ]; then
        echo "Cloning missing repository: $repo..."
        git clone "https://github.com/$ORG_NAME/$repo.git"
    else
        echo "Repository already exists locally: $repo"
    fi
done

# 3. Prepare Monorepo Directory (exclude dronefly-doc from uv lock; keep optional symlink)
cd "$MONOREPO_DIR"
if [ -L "dronefly-doc" ]; then
    rm "dronefly-doc"
elif [ -e "dronefly-doc" ]; then
    echo "Warning: dronefly-doc exists as a file/dir in monorepo; removing before creating symlink..."
    rm -rf "dronefly-doc"
fi
ln -s "../dronefly-doc" "dronefly-doc"

cat << 'EOF' > .gitignore
.venv/
__pycache__/
*.pyc
*.egg-info/
dist/
build/
dronefly-doc
tmp/
EOF

# 4. Write .python-version for Monorepo Root
echo "Generating monorepo root .python-version ($TARGET_PYTHON)..."
echo "$TARGET_PYTHON" > .python-version

# 5. Write Root pyproject.toml
echo "Generating root pyproject.toml..."
cat << 'EOF' > pyproject.toml
[project]
name = "dronefly-monorepo"
version = "0.1.0"
requires-python = ">=3.11,<3.12"
dependencies = []

[tool.uv.workspace]
members = []

[tool.uv.sources]
dronefly = { path = "../dronefly", editable = true }
dronefly-cli = { path = "../dronefly-cli", editable = true }
dronefly-core = { path = "../dronefly-core", editable = true }
dronefly-discord = { path = "../dronefly-discord", editable = true }
dronefly-miner = { path = "../dronefly-miner", editable = true }
pyinaturalist = { git = "https://github.com/pyinat/pyinaturalist.git", rev = "main" }
pyinaturalist-convert = { git = "https://github.com/pyinat/pyinaturalist-convert.git", rev = "main" }

[tool.uv]
default-groups = ["members", "dev"]
override-dependencies = [
    "starlette>=0.35",
]

[dependency-groups]
members = [
    "dronefly",
    "dronefly-cli",
    "dronefly-core",
    "dronefly-discord",
    "dronefly-miner",
]
dev = [
    "pip",
    "pyinaturalist",
    "tomlkit",
]
EOF

# 6. Create Virtual Environment, Lock & Sync Monorepo Dependencies, & Pre-commit
echo "Creating monorepo root virtual environment..."
uv venv --python "$TARGET_PYTHON" --seed

echo "Locking and syncing monorepo dependencies..."
uv lock
uv sync

echo "Configuring .python-version and pre-commit hooks for repositories..."
for repo in "${ALL_REPOS[@]}"; do
    REPO_PATH="$PARENT_DIR/$repo"
    if [ -d "$REPO_PATH" ]; then
        echo "Configuring $repo..."
        (
            cd "$REPO_PATH"
            echo "$TARGET_PYTHON" > .python-version
            if [ -f ".pre-commit-config.yaml" ]; then
                echo "Installing pre-commit hooks for $repo..."
                pre-commit install
            fi
        )
    fi
done

# 7. Configure VS Code Workspace and Member Settings
echo "Configuring VS Code settings..."

MONOREPO_VSCODE="$MONOREPO_DIR/.vscode"
mkdir -p "$MONOREPO_VSCODE"
cat << 'EOF' > "$MONOREPO_VSCODE/settings.json"
{
    "python.analysis.diagnosticMode": "workspace",
    "python.analysis.extraPaths": [
        "dronefly",
        "dronefly-cli",
        "dronefly-core",
        "dronefly-discord",
        "dronefly-doc",
        "dronefly-miner"
    ]
}
EOF

for repo in "${ALL_REPOS[@]}"; do
    REPO_PATH="$PARENT_DIR/$repo"
    if [ -d "$REPO_PATH" ]; then
        MEMBER_VSCODE="$REPO_PATH/.vscode"
        mkdir -p "$MEMBER_VSCODE"
        cat << 'EOF' > "$MEMBER_VSCODE/settings.json"
{
    "python-envs.pythonProjects": [
        {
            "path": ".",
            "envManager": "ms-python.python:venv",
            "packageManager": "ms-python.python:pip"
        }
    ]
}
EOF
    fi
done

echo "=== Monorepo setup successfully completed at: $MONOREPO_DIR ==="
