"""
Repository tools for MCP server.

All functions perform deterministic, local filesystem analysis.
No AI reasoning is involved — every result is derived from pure static
inspection of files and directories on disk.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

#: Directories that are never meaningful for source analysis and are always
#: excluded from traversal unless the caller explicitly requests them.
_SKIP_DIRS: frozenset[str] = frozenset({
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".hg",
    ".svn",
    "dist",
    "build",
    "out",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "target",       # Rust / Maven build artefacts
    ".gradle",
    ".idea",
    ".vscode",
})

#: Mapping from file extension (lower-cased) to canonical language name.
_EXT_TO_LANG: dict[str, str] = {
    # Python
    ".py": "Python", ".pyw": "Python", ".pyi": "Python",
    # JavaScript
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    # TypeScript
    ".ts": "TypeScript", ".tsx": "TypeScript",
    # Web
    ".html": "HTML", ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS", ".sass": "SCSS",
    ".less": "Less",
    ".vue": "Vue",
    ".svelte": "Svelte",
    # Systems
    ".go": "Go",
    ".rs": "Rust",
    ".c": "C", ".h": "C",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++", ".hxx": "C++",
    ".cs": "C#",
    ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin",
    ".swift": "Swift",
    ".scala": "Scala",
    # Scripting
    ".rb": "Ruby",
    ".php": "PHP",
    ".lua": "Lua",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".r": "R",
    ".dart": "Dart",
    ".ex": "Elixir", ".exs": "Elixir",
    ".hs": "Haskell",
    ".ml": "OCaml", ".mli": "OCaml",
    # Data / Config
    ".sql": "SQL",
    ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML",
    ".json": "JSON",
    ".xml": "XML",
    # Docs
    ".md": "Markdown", ".mdx": "Markdown", ".rst": "reStructuredText",
    # IaC
    ".tf": "Terraform", ".tfvars": "Terraform",
}


def _is_skip_path(rel_parts: tuple[str, ...]) -> bool:
    """Returns True if any path component is hidden or in the skip set."""
    for part in rel_parts:
        if part in _SKIP_DIRS or part.startswith("."):
            return True
    return False


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


def clone_repository(repo_url: str, local_path: str) -> bool:
    """
    Clones a public Git repository to a local directory using a shallow clone
    (``--depth 1``) for efficiency.

    If cloning fails for any reason — including an invalid URL, network error,
    or timeout — any partially created directory at ``local_path`` that did not
    exist before the call is deleted before returning ``False``.

    Args:
        repo_url (str): The URL of the public GitHub repository.
        local_path (str): The target local directory path.

    Returns:
        bool: True if cloning succeeded, False otherwise.
    """
    local_path = os.path.abspath(local_path)
    dir_existed_before = os.path.exists(local_path)

    print(f"[MCP TOOL] Cloning {repo_url} → {local_path} ...", file=sys.stderr)

    def _cleanup() -> None:
        """Remove a partially created directory if we created it."""
        if not dir_existed_before and os.path.exists(local_path):
            shutil.rmtree(local_path, ignore_errors=True)
            print(f"[MCP TOOL] Cleaned up partial directory: {local_path}", file=sys.stderr)

    try:
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, local_path],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            print(f"[MCP TOOL] Clone succeeded: {local_path}", file=sys.stderr)
            return True

        print(
            f"[MCP TOOL] Clone failed (exit {result.returncode}): "
            f"{result.stderr.strip()}",
            file=sys.stderr,
        )
        _cleanup()
        return False

    except subprocess.TimeoutExpired:
        print(f"[MCP TOOL] Clone timed out for {repo_url}", file=sys.stderr)
        _cleanup()
        return False

    except FileNotFoundError:
        print(
            "[MCP TOOL] 'git' not found. Ensure Git is installed and in PATH.",
            file=sys.stderr,
        )
        _cleanup()
        return False

    except Exception as exc:  # noqa: BLE001
        print(f"[MCP TOOL] Clone error for {repo_url}: {exc}", file=sys.stderr)
        _cleanup()
        return False


def list_directory(
    dir_path: str,
    max_depth: int | None = None,
    include_hidden: bool = False,
) -> list[str]:
    """
    Recursively lists all files and directories under ``dir_path``, returning
    paths relative to the root using forward-slash separators. Directory paths
    are suffixed with ``'/'``.

    Hidden entries (names starting with ``'.'``) and common non-source
    directories (e.g. ``.git``, ``node_modules``, ``__pycache__``) are
    excluded by default.

    Args:
        dir_path (str): Root directory path to traverse.
        max_depth (int | None): Maximum traversal depth (``None`` = unlimited).
            Depth 0 lists only the contents of ``dir_path`` itself.
        include_hidden (bool): If ``True``, include hidden files and directories.

    Returns:
        list[str]: Sorted list of relative paths. Directory entries end with ``'/'``.
    """
    base = os.path.abspath(dir_path)
    if not os.path.isdir(base):
        print(f"[MCP TOOL] Not a directory: {base}", file=sys.stderr)
        return []

    results: list[str] = []

    for root, dirs, files in os.walk(base, topdown=True):
        rel_root = os.path.relpath(root, base)
        depth = 0 if rel_root == "." else rel_root.count(os.sep) + 1

        # Enforce depth cap — prune children so os.walk won't descend.
        if max_depth is not None and depth >= max_depth:
            dirs.clear()
            continue

        # Filter and sort child directories in-place to control traversal.
        if include_hidden:
            dirs[:] = sorted(dirs)
        else:
            dirs[:] = sorted(
                d for d in dirs
                if not d.startswith(".") and d not in _SKIP_DIRS
            )

        # Emit directory entries.
        for d in dirs:
            rel = os.path.relpath(os.path.join(root, d), base).replace(os.sep, "/")
            results.append(rel + "/")

        # Emit file entries.
        for f in sorted(files):
            if not include_hidden and f.startswith("."):
                continue
            rel = os.path.relpath(os.path.join(root, f), base).replace(os.sep, "/")
            results.append(rel)

    return results


def read_file(file_path: str, max_bytes: int = 512_000) -> str:
    """
    Reads the text content of a file.

    Decoding is attempted with UTF-8 first, falling back to ``latin-1`` on
    ``UnicodeDecodeError``. If the file exceeds ``max_bytes``, the returned
    string is truncated and a ``[...TRUNCATED...]`` marker is appended.

    Args:
        file_path (str): Absolute or relative path to the file.
        max_bytes (int): Maximum bytes to read (default 512 KB).

    Returns:
        str: Text content of the file, or an empty string if the file is
             missing, unreadable, or binary.
    """
    if not os.path.isfile(file_path):
        print(f"[MCP TOOL] File not found: {file_path}", file=sys.stderr)
        return ""

    file_size = os.path.getsize(file_path)

    for encoding in ("utf-8", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding, errors="strict") as fh:
                content = fh.read(max_bytes)
            if file_size > max_bytes:
                content += (
                    f"\n\n[...TRUNCATED — file is {file_size:,} bytes; "
                    f"showing first {max_bytes:,} bytes...]"
                )
            return content
        except UnicodeDecodeError:
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"[MCP TOOL] Error reading {file_path}: {exc}", file=sys.stderr)
            return ""

    # Both encodings failed — almost certainly a binary file.
    print(f"[MCP TOOL] Skipping binary file: {file_path}", file=sys.stderr)
    return ""


def detect_languages(repo_path: str) -> dict[str, dict]:
    """
    Scans repository source files to identify the distribution of programming
    languages by file count and line count.

    Only files with recognised extensions (or special filenames such as
    ``Dockerfile`` or ``Makefile``) are counted. Common non-source directories
    are excluded from traversal.

    Args:
        repo_path (str): Root directory of the repository to scan.

    Returns:
        dict[str, dict]: Mapping of language name to a metrics dictionary::

            {
                "file_count": int,
                "line_count": int,
                "percentage": float,   # share of total lines, 0–100
            }

        Ordered by descending line count.
    """
    base = os.path.abspath(repo_path)
    if not os.path.isdir(base):
        print(f"[MCP TOOL] Not a directory: {base}", file=sys.stderr)
        return {}

    #: {language: {file_count, line_count}}
    counts: dict[str, dict[str, int]] = {}

    for root, dirs, files in os.walk(base, topdown=True):
        dirs[:] = [
            d for d in dirs
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            lang: str | None = _EXT_TO_LANG.get(ext)

            # Filename-only matches for extension-less files.
            if lang is None:
                fname_lower = fname.lower()
                if fname_lower == "dockerfile":
                    lang = "Dockerfile"
                elif fname_lower in ("makefile", "gnumakefile"):
                    lang = "Makefile"
                elif fname_lower == "gemfile":
                    lang = "Ruby"
            if lang is None:
                continue

            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                    line_count = sum(1 for _ in fh)
            except Exception:  # noqa: BLE001
                line_count = 0

            if lang not in counts:
                counts[lang] = {"file_count": 0, "line_count": 0}
            counts[lang]["file_count"] += 1
            counts[lang]["line_count"] += line_count

    total_lines = sum(v["line_count"] for v in counts.values()) or 1

    # Build result ordered by line count descending.
    result: dict[str, dict] = {}
    for lang, data in sorted(
        counts.items(), key=lambda kv: kv[1]["line_count"], reverse=True
    ):
        result[lang] = {
            "file_count": data["file_count"],
            "line_count": data["line_count"],
            "percentage": round(data["line_count"] / total_lines * 100, 2),
        }

    return result


def search_files(
    repo_path: str,
    pattern: str,
    file_glob: str = "*",
    max_results: int = 200,
) -> list[dict]:
    """
    Searches file contents within the repository for lines matching a regex
    pattern, optionally filtering by filename glob.

    Returns structured match records so downstream consumers (e.g.
    ContributionAgent) can process results without string parsing.

    Args:
        repo_path (str): Root directory path for the search.
        pattern (str): Regular expression pattern (case-insensitive).
        file_glob (str): Glob pattern for filename filtering (default ``'*'``).
        max_results (int): Maximum number of match records to return (default 200).

    Returns:
        list[dict]: Match records, each with keys:

            - ``file`` (str): Relative path using forward slashes.
            - ``line`` (int): 1-based line number of the match.
            - ``match`` (str): Full text of the matching line (trailing whitespace stripped).
    """
    base = Path(repo_path).resolve()
    if not base.is_dir():
        print(f"[MCP TOOL] Not a directory: {base}", file=sys.stderr)
        return []

    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        print(f"[MCP TOOL] Invalid regex pattern '{pattern}': {exc}", file=sys.stderr)
        return []

    results: list[dict] = []

    for fpath in sorted(base.rglob(file_glob)):
        if len(results) >= max_results:
            break
        if not fpath.is_file():
            continue

        # Skip hidden directories and known non-source directories.
        try:
            rel_parts = fpath.relative_to(base).parts
        except ValueError:
            continue
        if _is_skip_path(rel_parts):
            continue

        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                for lineno, raw_line in enumerate(fh, 1):
                    if compiled.search(raw_line):
                        results.append(
                            {
                                "file": str(fpath.relative_to(base)).replace("\\", "/"),
                                "line": lineno,
                                "match": raw_line.rstrip(),
                            }
                        )
                        if len(results) >= max_results:
                            break
        except Exception:  # noqa: BLE001
            continue

    return results
