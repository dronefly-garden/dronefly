#!/usr/bin/env python3
"""Update monorepo pyproject.toml dependencies for the active dronefly dev branch."""

from __future__ import annotations

import argparse
import shutil
import subprocess  # nosec B404
from pathlib import Path
import tomlkit

# .../dronefly/scripts/update_dev_deps.py
SCRIPT_DIR = Path(__file__).resolve().parent
DRONEFLY_DIR = SCRIPT_DIR.parent
MONOREPO_ROOT = (DRONEFLY_DIR / "../dronefly-monorepo").resolve()

CONVERT_REPO_URL = "https://github.com/pyinat/pyinaturalist-convert.git"
PYINAT_UPSTREAM_URL = "https://github.com/pyinat/pyinaturalist.git"

INTERNAL_PACKAGES = (
    "dronefly",
    "dronefly-cli",
    "dronefly-core",
    "dronefly-discord",
    "dronefly-doc",
    "dronefly-miner",
)

PACKAGE_FILES: dict[str, Path] = {
    "dronefly": DRONEFLY_DIR / "pyproject.toml",
    "dronefly-discord": MONOREPO_ROOT / "dronefly-discord/pyproject.toml",
    "dronefly-core": MONOREPO_ROOT / "dronefly-core/pyproject.toml",
    "dronefly-miner": MONOREPO_ROOT / "dronefly-miner/pyproject.toml",
}

BASE_DEPS: dict[str, list[str]] = {
    "dronefly": [
        "Red-DiscordBot>=3.5.24,<4",
        "dronefly-discord>=0.2.3,<0.3",
        "dronefly-miner>=0.2.0",
        "ebird-api>=3.0.6,<4",
        "filelock>=3.13.3,<4",
        "timeago>=1.0.15,<2",
        "aiolimiter>=1.0.0,<2",
        "aiohttp-retry>=2.4.5,<3",
    ],
    "dronefly-discord": [
        "inflect>=5.3.0,<6",
        "discord-py>=2.3.1",
        "dronefly-core==0.5.3",
    ],
    "dronefly-core": [
        "pyinaturalist",
        "dateparser>=1.1.1,<2",
        "filelock>=3.13.3,<4",
        "inflect>=5.3.0,<6",
        "html2markdown>=0.1.7,<0.2",
        "rich>=13.4",
    ],
    "dronefly-miner": [
        "alembic>=1.13",
        "fastparquet>=2026.5.0",
        "numpy>=2.4.6",
        "pandas>=3.0.5",
        "parquet>=1.3.1",
        "polars>=1.44.2",
        "pyarrow>=25.0.1",
        "pyinaturalist-convert",
        "sqlalchemy>=2.0.52",
        "xmltodict>=1.0.4",
    ],
}

EXTERNAL_SNAPSHOT_MEMBERS = ("pyinaturalist", "pyinaturalist-convert")


def resolve_executable(name: str) -> str:
    """Return the full executable path when available, falling back to name."""
    return shutil.which(name) or name


def find_git_dir(start: Path) -> Path | None:
    """Return the nearest directory containing a .git folder, or None if not in Git."""
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def get_git_state(search_root: Path, explicit_branch: str | None) -> tuple[str, str]:
    """Return (branch, head_sha) safely even if search_root is not a Git repository."""
    branch = explicit_branch or "dev"
    head_sha = "nogit"

    git_root = find_git_dir(search_root)
    if git_root is None:
        return branch, head_sha

    git_exe = resolve_executable("git")

    try:
        if explicit_branch is None:
            branch_out = subprocess.run(  # nosec: B603
                [git_exe, "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=git_root,
                check=True,
                text=True,
                capture_output=True,
            ).stdout.strip()
            if branch_out and branch_out != "HEAD":
                branch = branch_out

        sha_out = subprocess.run(  # nosec: B603
            [git_exe, "rev-parse", "HEAD"],
            cwd=git_root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        if sha_out:
            head_sha = sha_out
    except subprocess.CalledProcessError:
        pass

    return branch, head_sha


def latest_remote_sha(repo_url: str, ref: str = "refs/heads/main") -> str:
    git_exe = resolve_executable("git")
    out = subprocess.check_output(  # nosec: B603
        [git_exe, "ls-remote", repo_url, ref],
        text=True,
    ).strip()
    if not out:
        raise RuntimeError(f"Could not resolve {ref} for {repo_url}")
    return out.split()[0]


def set_multiline_deps(project_tbl: tomlkit.items.Table, deps: list[str]) -> None:
    dep_array = tomlkit.array()
    dep_array.multiline(True)
    for item in deps:
        dep_array.append(item)
    project_tbl["dependencies"] = dep_array


def update_root_workspace_sources(
    root_pyproject: Path,
    use_workspace_sources: bool,
) -> None:
    """Update monorepo root workspace members and [tool.uv.sources] for upstream snapshots."""
    if not root_pyproject.exists():
        print(f"[skip] {root_pyproject} does not exist")
        return

    doc = tomlkit.parse(root_pyproject.read_text(encoding="utf-8"))

    tool_tbl = doc.get("tool")
    uv_tbl = tool_tbl.get("uv") if isinstance(tool_tbl, dict) else None
    if isinstance(uv_tbl, dict):
        workspace_tbl = uv_tbl.get("workspace")
        if isinstance(workspace_tbl, dict) and "members" in workspace_tbl:
            filtered_members = [
                m
                for m in workspace_tbl["members"]
                if m not in EXTERNAL_SNAPSHOT_MEMBERS
            ]
            members_array = tomlkit.array()
            members_array.multiline(True)
            for member in filtered_members:
                members_array.append(member)
            workspace_tbl["members"] = members_array

        sources_tbl = uv_tbl.get("sources")
        if isinstance(sources_tbl, dict):
            for ext_pkg in EXTERNAL_SNAPSHOT_MEMBERS:
                if ext_pkg in sources_tbl:
                    del sources_tbl[ext_pkg]

            for pkg in INTERNAL_PACKAGES:
                if pkg in sources_tbl and not use_workspace_sources:
                    del sources_tbl[pkg]
                elif use_workspace_sources and pkg in sources_tbl:
                    sources_tbl[pkg] = {"workspace": True}

    root_pyproject.write_text(tomlkit.dumps(doc), encoding="utf-8")
    print(f"[updated] {root_pyproject} (root workspace & sources)")


def update_member_pyproject(
    pkg_name: str,
    pyproject_path: Path,
    branch: str,
    head_sha: str,
    convert_sha: str,
    use_workspace_sources: bool,
) -> None:
    if not pyproject_path.exists():
        print(f"[skip] {pyproject_path} does not exist")
        return

    doc = tomlkit.parse(pyproject_path.read_text(encoding="utf-8"))
    project = doc.setdefault("project", tomlkit.table())

    deps = list(BASE_DEPS[pkg_name])
    if pkg_name == "dronefly-core":
        deps = [
            (
                f"pyinaturalist @ git+{PYINAT_UPSTREAM_URL}@main"
                if d == "pyinaturalist"
                else d
            )
            for d in deps
        ]
    elif pkg_name == "dronefly-miner":
        deps = [
            (
                f"pyinaturalist-convert @ git+{CONVERT_REPO_URL}@{convert_sha}"
                if d == "pyinaturalist-convert"
                else d
            )
            for d in deps
        ]

    set_multiline_deps(project, deps)

    if "tool" in doc and "uv" in doc["tool"] and "sources" in doc["tool"]["uv"]:
        sources_tbl = doc["tool"]["uv"]["sources"]
        for stale in ("pyinaturalist", "pyinaturalist-convert"):
            if stale in sources_tbl:
                del sources_tbl[stale]
        if not use_workspace_sources:
            for internal_pkg in INTERNAL_PACKAGES:
                if internal_pkg != pkg_name and internal_pkg in sources_tbl:
                    del sources_tbl[internal_pkg]

    pyproject_path.write_text(tomlkit.dumps(doc), encoding="utf-8")
    print(f"[updated] {pyproject_path} (branch={branch}, rev={head_sha[:8]})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--branch",
        default=None,
        help="Dev branch name when no Git repo is detected (default: 'dev').",
    )
    parser.add_argument(
        "--pin-snapshots",
        action="store_true",
        help="Remove internal workspace=true source overrides for snapshot lock/build mode.",
    )
    parser.add_argument(
        "--no-lock",
        action="store_true",
        help="Skip running `uv lock` after updating pyproject.toml files.",
    )
    args = parser.parse_args()

    branch, head_sha = get_git_state(DRONEFLY_DIR, args.branch)
    convert_sha = latest_remote_sha(CONVERT_REPO_URL, "refs/heads/main")

    print(f"Dronefly dir:  {DRONEFLY_DIR}")
    print(f"Monorepo root: {MONOREPO_ROOT}")
    print(f"Branch:        {branch} (rev={head_sha[:8]})")
    print(f"Latest upstream pyinaturalist-convert main SHA: {convert_sha}")

    update_root_workspace_sources(
        root_pyproject=MONOREPO_ROOT / "pyproject.toml",
        use_workspace_sources=not args.pin_snapshots,
    )

    for pkg_name, path in PACKAGE_FILES.items():
        update_member_pyproject(
            pkg_name=pkg_name,
            pyproject_path=path,
            branch=branch,
            head_sha=head_sha,
            convert_sha=convert_sha,
            use_workspace_sources=not args.pin_snapshots,
        )

    if not args.no_lock and MONOREPO_ROOT.exists():
        uv_exe = resolve_executable("uv")
        subprocess.run([uv_exe, "lock"], cwd=MONOREPO_ROOT, check=True)  # nosec: B603


if __name__ == "__main__":
    main()
