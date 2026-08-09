#!/usr/bin/env bash
set -euo pipefail

# 1. Configuration & Prereq Checks
REPO_NAME="dronefly"
ORG_NAME="dronefly-garden"
MEMBERS=("dronefly-cli" "dronefly-core" "dronefly-discord" "dronefly")
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
CURRENT_DIR="$(pwd)"
PARENT_DIR="$(dirname "$CURRENT_DIR")"
MONOREPO_DIR="$PARENT_DIR/dronefly-monorepo"

echo "Ensuring monorepo root at: $MONOREPO_DIR"
mkdir -p "$MONOREPO_DIR"

# Move/ensure all member repositories are cloned in the parent directory
cd "$PARENT_DIR"
for member in "${MEMBERS[@]}"; do
    if [ ! -d "$member" ]; then
        echo "Cloning missing repository: $member..."
        git clone "https://github.com/$ORG_NAME/$member.git"
    else
        echo "Repository already exists locally: $member"
    fi
done

# 3. Setup Symlinks inside dronefly-monorepo
cd "$MONOREPO_DIR"
echo "Configuring symlinks for monorepo workspace..."
for member in "${MEMBERS[@]}"; do
    TARGET_PATH="../$member"
    if [ -L "$member" ]; then
        rm "$member"
    elif [ -e "$member" ]; then
        echo "Warning: $member exists as a regular file/dir. Removing to replace with symlink..."
        rm -rf "$member"
    fi
    ln -s "$TARGET_PATH" "$member"
done

# 4. Write .python-version for Monorepo Root
echo "Generating monorepo root .python-version ($TARGET_PYTHON)..."
echo "$TARGET_PYTHON" > .python-version

# 5. Write Root pyproject.toml
echo "Generating root pyproject.toml..."
cat << 'EOF' > pyproject.toml
[tool.uv.workspace]
members = ["dronefly-cli", "dronefly-core", "dronefly-discord", "dronefly"]

[tool.uv.sources]
dronefly-cli = { workspace = true }
dronefly-core = { workspace = true }
dronefly-discord = { workspace = true }
dronefly = { workspace = true }
EOF

# 6. Create Virtual Environments, .python-version, & Pre-commit for Members and Root
echo "Creating monorepo root virtual environment..."
uv venv --python "$TARGET_PYTHON" --seed

echo "Syncing monorepo workspace dependencies..."
uv sync --all-packages --all-groups

echo "Configuring individual member environments, .python-version files, and pre-commit hooks..."
for member in "${MEMBERS[@]}"; do
    if [ -d "$member" ]; then
        echo "Setting up $member..."
        (
            cd "$member"
            echo "$TARGET_PYTHON" > .python-version
            uv venv --python "$TARGET_PYTHON" --seed
            uv sync --all-groups
            
            if [ -f ".pre-commit-config.yaml" ]; then
                echo "Installing pre-commit hooks for $member..."
                uv run pre-commit install
            fi
        )
    fi
done

# 7. Configure VS Code Workspace and Member Settings
echo "Configuring VS Code settings..."

# Monorepo root VS Code settings
MONOREPO_VSCODE=".vscode"
mkdir -p "$MONOREPO_VSCODE"
cat << 'EOF' > "$MONOREPO_VSCODE/settings.json"
{
    "python.analysis.diagnosticMode": "workspace",
    "python.analysis.extraPaths": [
        "dronefly",
        "dronefly-cli",
        "dronefly-core",
        "dronefly-discord"
    ]
}
EOF

# Member repositories VS Code settings
for member in "${MEMBERS[@]}"; do
    if [ -d "$member" ]; then
        MEMBER_VSCODE="../$member/.vscode"
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
