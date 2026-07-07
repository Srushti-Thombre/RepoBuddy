"""
RepositoryAgent — deterministic local codebase analysis.

Orchestrates the five MCP repository tools into a fully-populated
``RepositoryContext`` without any AI reasoning. All detection is heuristic
and rule-based, making the analysis fast, reproducible, and offline-capable.

Downstream agents (ArchitectureAgent, ContributionAgent, ReportAgent) receive
the ``RepositoryContext`` directly. Callers that need a plain dict for
compatibility with the scaffold-level stub signatures can call
``context.model_dump()``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.adk import Agent

from models.repository_context import (
    BuildSystemInfo,
    ComplexityLevel,
    ComplexityMetrics,
    DocumentationInfo,
    EntryPoint,
    LanguageStat,
    PackageManagerInfo,
    RepositoryContext,
    TreeNode,
)
from mcp_server.tools_repository import (
    clone_repository,
    detect_languages,
    list_directory,
    read_file,
    search_files,
)


# ---------------------------------------------------------------------------
# Module-level knowledge bases
# ---------------------------------------------------------------------------

#: Directories that the agent skips when building the repo tree and computing
#: metrics. Mirrors the skip list used inside the MCP tools.
_SKIP_DIRS: frozenset[str] = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "out", ".next", ".nuxt", ".svelte-kit",
    "target", ".gradle", ".idea", ".vscode",
})

# ---------------------------------------------------------------------------
# Package-manager detection tables
# ---------------------------------------------------------------------------

#: (pm_display_name, primary_config_filename)
_PYTHON_PM_CHECKS: list[tuple[str, str]] = [
    ("pip",         "requirements.txt"),
    ("pipenv",      "Pipfile"),
    ("conda",       "environment.yml"),
    ("conda",       "environment.yaml"),
    ("setuptools",  "setup.py"),
]

_OTHER_PM_CHECKS: list[tuple[str, str]] = [
    ("cargo",       "Cargo.toml"),
    ("go modules",  "go.mod"),
    ("maven",       "pom.xml"),
    ("gradle",      "build.gradle"),
    ("gradle",      "build.gradle.kts"),
    ("bundler",     "Gemfile"),
    ("composer",    "composer.json"),
    ("pub",         "pubspec.yaml"),
    ("mix",         "mix.exs"),
]

# ---------------------------------------------------------------------------
# Build-system detection table
# ---------------------------------------------------------------------------

#: (tool_display_name, list_of_config_filenames_to_check)
_BUILD_SYSTEM_CHECKS: list[tuple[str, list[str]]] = [
    ("make",            ["Makefile", "makefile", "GNUmakefile"]),
    ("cmake",           ["CMakeLists.txt"]),
    ("meson",           ["meson.build"]),
    ("bazel",           ["BUILD", "BUILD.bazel", "WORKSPACE", "WORKSPACE.bazel"]),
    ("tox",             ["tox.ini"]),
    ("nox",             ["noxfile.py"]),
    ("Docker",          ["Dockerfile"]),
    ("docker-compose",  ["docker-compose.yml", "docker-compose.yaml"]),
    ("webpack",         ["webpack.config.js", "webpack.config.ts", "webpack.config.cjs"]),
    ("vite",            ["vite.config.js", "vite.config.ts", "vite.config.mjs"]),
    ("rollup",          ["rollup.config.js", "rollup.config.ts", "rollup.config.mjs"]),
    ("parcel",          [".parcelrc"]),
    ("esbuild",         ["esbuild.config.js", "esbuild.config.mjs"]),
    ("turbo",           ["turbo.json"]),
    ("nx",              ["nx.json"]),
    ("lerna",           ["lerna.json"]),
    ("Jenkins",         ["Jenkinsfile"]),
]

# ---------------------------------------------------------------------------
# Framework detection tables
# ---------------------------------------------------------------------------

#: Known Python framework / library package names → display name.
_PYTHON_FRAMEWORKS: dict[str, str] = {
    "django":           "Django",
    "flask":            "Flask",
    "fastapi":          "FastAPI",
    "starlette":        "Starlette",
    "tornado":          "Tornado",
    "aiohttp":          "aiohttp",
    "bottle":           "Bottle",
    "pyramid":          "Pyramid",
    "sanic":            "Sanic",
    "litestar":         "Litestar",
    "falcon":           "Falcon",
    "cherrypy":         "CherryPy",
    "pydantic":         "Pydantic",
    "sqlalchemy":       "SQLAlchemy",
    "celery":           "Celery",
    "dramatiq":         "Dramatiq",
    "google-adk":       "Google ADK",
    "google_adk":       "Google ADK",
    "google-genai":     "Google GenAI",
    "openai":           "OpenAI",
    "anthropic":        "Anthropic",
    "langchain":        "LangChain",
    "llama-index":      "LlamaIndex",
    "llamaindex":       "LlamaIndex",
    "tensorflow":       "TensorFlow",
    "torch":            "PyTorch",
    "keras":            "Keras",
    "scikit-learn":     "scikit-learn",
    "streamlit":        "Streamlit",
    "gradio":           "Gradio",
    "dash":             "Dash",
    "typer":            "Typer",
    "click":            "Click",
    "rich":             "Rich",
    "httpx":            "HTTPX",
    "requests":         "Requests",
    "mcp":              "MCP",
}

#: Known JavaScript/TypeScript package names (in ``package.json``) → display name.
_JS_FRAMEWORKS: dict[str, str] = {
    "react":                "React",
    "react-dom":            "React",
    "vue":                  "Vue",
    "@angular/core":        "Angular",
    "svelte":               "Svelte",
    "next":                 "Next.js",
    "nuxt":                 "Nuxt.js",
    "gatsby":               "Gatsby",
    "astro":                "Astro",
    "express":              "Express",
    "fastify":              "Fastify",
    "koa":                  "Koa",
    "@nestjs/core":         "NestJS",
    "hapi":                 "Hapi",
    "@hapi/hapi":           "Hapi",
    "socket.io":            "Socket.IO",
    "electron":             "Electron",
    "vite":                 "Vite",
    "webpack":              "webpack",
    "rollup":               "Rollup",
    "jest":                 "Jest",
    "vitest":               "Vitest",
    "mocha":                "Mocha",
    "graphql":              "GraphQL",
    "@apollo/client":       "Apollo",
    "prisma":               "Prisma",
    "@prisma/client":       "Prisma",
    "typeorm":              "TypeORM",
    "sequelize":            "Sequelize",
    "mongoose":             "Mongoose",
    "redux":                "Redux",
    "@reduxjs/toolkit":     "Redux",
    "zustand":              "Zustand",
    "tailwindcss":          "Tailwind CSS",
    "styled-components":    "styled-components",
    "axios":                "Axios",
    "trpc":                 "@trpc",
    "@trpc/server":         "tRPC",
}

#: Regex patterns to search in ``go.mod`` → display name.
_GO_FRAMEWORKS: dict[str, str] = {
    "gin-gonic/gin":    "Gin",
    "labstack/echo":    "Echo",
    "gofiber/fiber":    "Fiber",
    "gorilla/mux":      "Gorilla Mux",
    "go-chi/chi":       "Chi",
    "beego/beego":      "Beego",
    "urfave/cli":       "urfave/cli",
    "spf13/cobra":      "Cobra",
}

#: Crate names to search in ``Cargo.toml`` → display name.
_RUST_FRAMEWORKS: dict[str, str] = {
    "actix-web":    "Actix Web",
    "axum":         "Axum",
    "rocket":       "Rocket",
    "warp":         "Warp",
    "tokio":        "Tokio",
    "serde":        "Serde",
    "sqlx":         "SQLx",
    "sea-orm":      "SeaORM",
    "clap":         "Clap",
}

# ---------------------------------------------------------------------------
# Entry-point detection table
# ---------------------------------------------------------------------------

#: (relative_path_candidate, entry_type_label) in priority order.
_ENTRY_POINT_CANDIDATES: list[tuple[str, str]] = [
    # Python
    ("main.py",          "main"),
    ("app.py",           "main"),
    ("run.py",           "main"),
    ("server.py",        "main"),
    ("manage.py",        "main"),     # Django
    ("asgi.py",          "asgi"),
    ("wsgi.py",          "wsgi"),
    ("cli.py",           "cli"),
    ("__main__.py",      "main"),
    # Go
    ("main.go",          "main"),
    ("cmd/main.go",      "main"),
    # JavaScript / TypeScript
    ("index.js",         "index"),
    ("index.ts",         "index"),
    ("server.js",        "main"),
    ("server.ts",        "main"),
    ("app.js",           "main"),
    ("app.ts",           "main"),
    ("main.js",          "main"),
    ("main.ts",          "main"),
    ("src/index.js",     "index"),
    ("src/index.ts",     "index"),
    ("src/main.js",      "main"),
    ("src/main.ts",      "main"),
    # Rust
    ("src/main.rs",      "main"),
    # Java / Kotlin
    ("src/main/java/Main.java",   "main"),
    ("src/Main.java",             "main"),
    ("src/main/kotlin/Main.kt",   "main"),
    # C#
    ("Program.cs",       "main"),
    ("src/Program.cs",   "main"),
    # Ruby
    ("app.rb",           "main"),
    ("config.ru",        "main"),    # Rack
    # PHP
    ("index.php",        "index"),
    ("public/index.php", "index"),
]

# ---------------------------------------------------------------------------
# Test detection tables
# ---------------------------------------------------------------------------

#: Known test directories (exact names, case-sensitive).
_TEST_DIRS: tuple[str, ...] = (
    "tests", "test", "spec", "__tests__", "test_suite",
    "e2e", "integration", "unit",
)

#: File-name patterns that imply a test file.
_TEST_FILE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"^test_.*\.py$"),
    re.compile(r".*_test\.py$"),
    re.compile(r".*\.spec\.(js|ts|jsx|tsx)$"),
    re.compile(r".*\.test\.(js|ts|jsx|tsx)$"),
    re.compile(r"^.*_spec\.rb$"),
)

#: Mapping of config-file indicator → test framework name.
_TEST_FRAMEWORK_INDICATORS: list[tuple[str, str]] = [
    ("pytest.ini",           "pytest"),
    ("conftest.py",          "pytest"),
    ("setup.cfg",            "pytest"),       # refined later by content
    ("pyproject.toml",       "pytest"),       # refined later by content
    ("jest.config.js",       "Jest"),
    ("jest.config.ts",       "Jest"),
    ("jest.config.mjs",      "Jest"),
    ("vitest.config.js",     "Vitest"),
    ("vitest.config.ts",     "Vitest"),
    ("mocha",                "Mocha"),        # matched by dep name
    (".mocharc.js",          "Mocha"),
    (".mocharc.yml",         "Mocha"),
    ("karma.conf.js",        "Karma"),
    ("cypress.config.js",    "Cypress"),
    ("cypress.config.ts",    "Cypress"),
    ("playwright.config.ts", "Playwright"),
    ("playwright.config.js", "Playwright"),
]

# ---------------------------------------------------------------------------
# Documentation detection helpers
# ---------------------------------------------------------------------------

_README_CANDIDATES: tuple[str, ...] = (
    "README.md", "README.rst", "README.txt", "README",
    "Readme.md", "readme.md",
)

_CONTRIBUTING_CANDIDATES: tuple[str, ...] = (
    "CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING.txt", "CONTRIBUTING",
)

_CHANGELOG_CANDIDATES: tuple[str, ...] = (
    "CHANGELOG.md", "CHANGELOG.rst", "CHANGELOG", "CHANGES.md",
    "HISTORY.md", "HISTORY.rst", "HISTORY",
    "RELEASES.md", "NEWS.md",
)

_DOCS_DIRS: tuple[str, ...] = ("docs", "doc", "documentation", "wiki")


# ---------------------------------------------------------------------------
# Complexity scoring constants
# ---------------------------------------------------------------------------

#: Maximum contribution of each signal to the 0–100 composite score.
_COMPLEXITY_WEIGHTS = {
    "files":     25,   # up to 25 pts — 1 pt per 10 files, cap at 250 files
    "lines":     35,   # up to 35 pts — 1 pt per 500 lines, cap at 17 500 lines
    "max_depth": 20,   # up to 20 pts — 2 pts per depth level, cap at depth 10
    "languages": 20,   # up to 20 pts — 5 pts per extra language beyond 1, cap at 4 extras
}

_COMPLEXITY_THRESHOLDS: list[tuple[int, ComplexityLevel]] = [
    (76, "Very High"),
    (51, "High"),
    (26, "Medium"),
    (0,  "Low"),
]


# ===========================================================================
# RepositoryAgent
# ===========================================================================


class RepositoryAgent:
    """
    RepositoryAgent handles deep local codebase and repository inspection.

    Responsibilities:
    - Interface with local filesystem tools to parse file and directory structures.
    - Locate codebase entry points (e.g. main.py, index.js, app.go).
    - Detect package managers (e.g. pip, npm, cargo) and build systems (e.g. webpack, cmake).
    - Detect test suites (e.g. pytest, jest) and documentation structures.
    - Estimate codebase complexity based on file layouts, lines of code, and structure.
    - Interface with the repository MCP tools (clone, list, read, search, detect_languages).
    """

    def __init__(self) -> None:
        """
        Initializes the RepositoryAgent and configures its underlying ADK Agent
        structure with the five repository MCP tools registered.
        """
        self.adk_agent = Agent(
            name="RepositoryAgent",
            instruction=(
                "You are an expert static analysis agent. Your goal is to inspect files locally, "
                "detect entry points, package managers, build systems, test files, and docs, "
                "and calculate repository complexity scores."
            ),
            tools=[
                clone_repository,
                list_directory,
                read_file,
                detect_languages,
                search_files,
            ],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clone_and_analyze(
        self, repo_url: str, workspace_dir: str
    ) -> RepositoryContext | None:
        """
        Convenience method: clones the repository to ``workspace_dir`` and
        immediately runs a full analysis on the cloned checkout.

        Args:
            repo_url (str): Public Git repository URL.
            workspace_dir (str): Local directory path for the clone.

        Returns:
            RepositoryContext: Populated analysis context, or ``None`` if
            cloning failed.
        """
        success = clone_repository(repo_url, workspace_dir)
        if not success:
            print(
                f"[RepositoryAgent] Clone failed for {repo_url}; aborting analysis.",
                file=sys.stderr,
            )
            return None
        return self.analyze_repository(workspace_dir)

    def analyze_repository(self, local_path: str) -> RepositoryContext:
        """
        Runs a full deterministic analysis on the repository at ``local_path``.

        The method orchestrates nine private detection passes in dependency
        order, assembling their outputs into a single ``RepositoryContext``.

        Args:
            local_path (str): Absolute path to the local repository directory.

        Returns:
            RepositoryContext: Fully populated analysis context.

        Note:
            Downstream consumers that require a plain dict for compatibility
            with other agents can call ``context.model_dump()``.
        """
        repo_path = os.path.abspath(local_path)
        print(f"[RepositoryAgent] Starting analysis: {repo_path}", file=sys.stderr)

        if not os.path.isdir(repo_path):
            raise ValueError(f"Repository path does not exist or is not a directory: {repo_path}")

        # 1. File tree (needed for complexity metrics).
        repo_tree = self._build_repo_tree(repo_path)
        print(f"[RepositoryAgent] Tree built — {len(repo_tree)} nodes.", file=sys.stderr)

        # 2. Language distribution.
        raw_langs = detect_languages(repo_path)
        languages = {
            name: LanguageStat(**stats) for name, stats in raw_langs.items()
        }
        primary_language = next(iter(languages), None)
        print(f"[RepositoryAgent] Languages: {list(languages.keys())}", file=sys.stderr)

        # 3. Package managers.
        package_managers = self._detect_package_managers(repo_path)
        print(
            f"[RepositoryAgent] Package managers: {[pm.name for pm in package_managers]}",
            file=sys.stderr,
        )

        # 4. Build systems.
        build_systems = self._detect_build_systems(repo_path)
        print(
            f"[RepositoryAgent] Build systems: {[bs.name for bs in build_systems]}",
            file=sys.stderr,
        )

        # 5. Frameworks (depends on package manager config files).
        frameworks = self._detect_frameworks(repo_path, package_managers, primary_language)
        print(f"[RepositoryAgent] Frameworks: {frameworks}", file=sys.stderr)

        # 6. Entry points.
        entry_points = self._find_entry_points(repo_path, package_managers)
        print(
            f"[RepositoryAgent] Entry points: {[ep.path for ep in entry_points]}",
            file=sys.stderr,
        )

        # 7. Tests.
        has_tests, test_paths, test_framework = self._find_test_info(
            repo_path, package_managers
        )
        print(
            f"[RepositoryAgent] Tests: has_tests={has_tests}, "
            f"framework={test_framework}, paths={test_paths}",
            file=sys.stderr,
        )

        # 8. Documentation.
        documentation = self._find_documentation(repo_path)
        print(
            f"[RepositoryAgent] Docs: readme={documentation.readme_path}, "
            f"docs_dir={documentation.docs_dir}",
            file=sys.stderr,
        )

        # 9. Complexity.
        complexity = self._compute_complexity(repo_tree, languages)
        print(
            f"[RepositoryAgent] Complexity: score={complexity.score}, "
            f"level={complexity.level}",
            file=sys.stderr,
        )

        # 10. Recommended reading order (mentor-specific).
        reading_order = self._compute_reading_order(
            repo_path, documentation, entry_points, package_managers, primary_language
        )
        print(
            f"[RepositoryAgent] Reading order: {reading_order}",
            file=sys.stderr,
        )

        context = RepositoryContext(
            repo_path=repo_path,
            languages=languages,
            primary_language=primary_language,
            frameworks=frameworks,
            package_managers=package_managers,
            build_systems=build_systems,
            entry_points=entry_points,
            test_framework=test_framework,
            has_tests=has_tests,
            test_paths=test_paths,
            documentation=documentation,
            repo_tree=repo_tree,
            complexity=complexity,
            recommended_reading_order=reading_order,
            analysis_timestamp=datetime.now(timezone.utc),
        )

        print("[RepositoryAgent] Analysis complete.", file=sys.stderr)
        return context

    # ------------------------------------------------------------------
    # Private helpers — repo tree
    # ------------------------------------------------------------------

    def _build_repo_tree(self, repo_path: str, max_nodes: int = 1_000) -> list[TreeNode]:
        """
        Builds a flat list of ``TreeNode`` objects representing the repository
        file system, capped at ``max_nodes`` to prevent memory issues on very
        large repositories.
        """
        base = Path(repo_path).resolve()
        nodes: list[TreeNode] = []

        for root, dirs, files in os.walk(base, topdown=True):
            if len(nodes) >= max_nodes:
                dirs.clear()
                break

            dirs[:] = sorted(
                d for d in dirs
                if d not in _SKIP_DIRS and not d.startswith(".")
            )

            for d in dirs:
                if len(nodes) >= max_nodes:
                    break
                rel = Path(root, d).relative_to(base)
                nodes.append(
                    TreeNode(
                        path=str(rel).replace("\\", "/") + "/",
                        node_type="directory",
                        size_bytes=None,
                    )
                )

            for f in sorted(files):
                if len(nodes) >= max_nodes:
                    break
                if f.startswith("."):
                    continue
                fpath = Path(root, f)
                rel = fpath.relative_to(base)
                try:
                    size = fpath.stat().st_size
                except OSError:
                    size = None
                nodes.append(
                    TreeNode(
                        path=str(rel).replace("\\", "/"),
                        node_type="file",
                        size_bytes=size,
                    )
                )

        return nodes

    # ------------------------------------------------------------------
    # Private helpers — package managers
    # ------------------------------------------------------------------

    def _detect_package_managers(self, repo_path: str) -> list[PackageManagerInfo]:
        """
        Detects package managers by checking for known configuration files in
        the repository root and common monorepo subdirectories.
        """
        try:
            root_files: set[str] = set(os.listdir(repo_path))
        except OSError:
            return []

        results: list[PackageManagerInfo] = []
        seen_configs: set[str] = set()

        def _add(name: str, config_file: str) -> None:
            if config_file not in seen_configs:
                seen_configs.add(config_file)
                results.append(PackageManagerInfo(name=name, config_file=config_file))

        # Python — pip / setuptools
        for pm_name, fname in _PYTHON_PM_CHECKS:
            if fname in root_files:
                _add(pm_name, fname)

        # Python — pyproject.toml (disambiguate poetry vs setuptools)
        if "pyproject.toml" in root_files:
            content = read_file(os.path.join(repo_path, "pyproject.toml"))
            if "[tool.poetry]" in content:
                _add("poetry", "pyproject.toml")
            elif "[build-system]" in content or "[project]" in content:
                _add("setuptools", "pyproject.toml")
            else:
                _add("setuptools", "pyproject.toml")   # present but minimal

        # JavaScript — check root and common monorepo subdirs
        js_search_dirs: list[tuple[str, str]] = [("", "")]  # (subdir_rel, subdir_display)
        for subdir in ("frontend", "client", "web", "ui", "app", "packages"):
            if subdir in root_files and os.path.isdir(os.path.join(repo_path, subdir)):
                js_search_dirs.append((subdir, subdir + "/"))

        for subdir_rel, subdir_display in js_search_dirs:
            pkg_dir = os.path.join(repo_path, subdir_rel) if subdir_rel else repo_path
            pkg_json = os.path.join(pkg_dir, "package.json")
            if not os.path.isfile(pkg_json):
                continue
            # Detect npm vs yarn vs pnpm by lockfile presence.
            if os.path.isfile(os.path.join(pkg_dir, "pnpm-lock.yaml")):
                pm_name = "pnpm"
            elif os.path.isfile(os.path.join(pkg_dir, "yarn.lock")):
                pm_name = "yarn"
            else:
                pm_name = "npm"
            config_rel = f"{subdir_display}package.json" if subdir_display else "package.json"
            _add(pm_name, config_rel)

        # Other languages
        for pm_name, fname in _OTHER_PM_CHECKS:
            if fname in root_files:
                _add(pm_name, fname)

        return results

    # ------------------------------------------------------------------
    # Private helpers — build systems
    # ------------------------------------------------------------------

    def _detect_build_systems(self, repo_path: str) -> list[BuildSystemInfo]:
        """
        Detects build tools, bundlers, and CI/CD systems by checking for
        known configuration files in the repository root.
        """
        try:
            root_files: set[str] = set(os.listdir(repo_path))
            # Also include hidden entries (Dockerfile etc. are not hidden, but
            # .parcelrc, .mocharc are).
            root_all: set[str] = set(
                os.listdir(repo_path)
            )
        except OSError:
            return []

        results: list[BuildSystemInfo] = []
        seen: set[str] = set()

        def _add(name: str, config_file: str) -> None:
            if name not in seen:
                seen.add(name)
                results.append(BuildSystemInfo(name=name, config_file=config_file))

        for tool_name, config_files in _BUILD_SYSTEM_CHECKS:
            for fname in config_files:
                if fname in root_all:
                    _add(tool_name, fname)
                    break

        # GitHub Actions — check .github/workflows/
        gh_workflows = os.path.join(repo_path, ".github", "workflows")
        if os.path.isdir(gh_workflows):
            wf_files = sorted(
                f for f in os.listdir(gh_workflows)
                if f.endswith((".yml", ".yaml"))
            )
            if wf_files:
                _add("GitHub Actions", f".github/workflows/{wf_files[0]}")

        # GitLab CI
        if ".gitlab-ci.yml" in root_all:
            _add("GitLab CI", ".gitlab-ci.yml")

        # Circle CI
        circle = os.path.join(repo_path, ".circleci", "config.yml")
        if os.path.isfile(circle):
            _add("CircleCI", ".circleci/config.yml")

        return results

    # ------------------------------------------------------------------
    # Private helpers — frameworks
    # ------------------------------------------------------------------

    def _detect_frameworks(
        self,
        repo_path: str,
        package_managers: list[PackageManagerInfo],
        primary_language: str | None,
    ) -> list[str]:
        """
        Detects frameworks and major libraries by reading package dependency
        files and matching against known name tables.

        Reads only the specific config files identified by the package-manager
        detection pass, keeping I/O minimal.
        """
        detected: dict[str, str] = {}  # package_key → display_name

        pm_config_files = {pm.config_file for pm in package_managers}

        # --- Python dependency files ---
        for fname in ("requirements.txt", "requirements-dev.txt", "requirements-test.txt"):
            fpath = os.path.join(repo_path, fname)
            if os.path.isfile(fpath):
                content = read_file(fpath)
                self._scan_python_deps(content, detected)

        if "pyproject.toml" in pm_config_files or os.path.isfile(
            os.path.join(repo_path, "pyproject.toml")
        ):
            content = read_file(os.path.join(repo_path, "pyproject.toml"))
            self._scan_python_deps(content, detected)

        if "setup.py" in pm_config_files or os.path.isfile(
            os.path.join(repo_path, "setup.py")
        ):
            content = read_file(os.path.join(repo_path, "setup.py"))
            self._scan_python_deps(content, detected)

        # --- JavaScript / TypeScript package.json ---
        js_configs = [
            cf for cf in pm_config_files if cf.endswith("package.json")
        ]
        # Fallback: also try root package.json directly.
        if not js_configs and os.path.isfile(os.path.join(repo_path, "package.json")):
            js_configs = ["package.json"]

        for js_config in js_configs:
            fpath = os.path.join(repo_path, js_config)
            if os.path.isfile(fpath):
                self._scan_package_json(fpath, detected)

        # --- Go: go.mod ---
        go_mod = os.path.join(repo_path, "go.mod")
        if os.path.isfile(go_mod):
            content = read_file(go_mod)
            for pkg_fragment, display in _GO_FRAMEWORKS.items():
                if pkg_fragment in content and display not in detected.values():
                    detected[pkg_fragment] = display

        # --- Rust: Cargo.toml ---
        cargo_toml = os.path.join(repo_path, "Cargo.toml")
        if os.path.isfile(cargo_toml):
            content = read_file(cargo_toml)
            for crate, display in _RUST_FRAMEWORKS.items():
                if crate in content and display not in detected.values():
                    detected[crate] = display

        # Deduplicate, preserving insertion order.
        seen: set[str] = set()
        results: list[str] = []
        for display in detected.values():
            if display not in seen:
                seen.add(display)
                results.append(display)
        return results

    def _scan_python_deps(
        self, content: str, detected: dict[str, str]
    ) -> None:
        """Scans raw text of a Python dependency file and populates ``detected``."""
        content_lower = content.lower()
        for pkg_key, display in _PYTHON_FRAMEWORKS.items():
            # Match whole package name (with optional version spec).
            # Handles both `pkg-name` and `pkg_name` formats.
            normalised = pkg_key.replace("-", "[-_]").replace("_", "[-_]")
            if re.search(rf"(?:^|\s){normalised}(?:\s*[=><!;\[]|$)", content_lower, re.MULTILINE):
                detected[pkg_key] = display

    def _scan_package_json(
        self, fpath: str, detected: dict[str, str]
    ) -> None:
        """Parses a ``package.json`` file and populates ``detected`` from both
        ``dependencies`` and ``devDependencies``."""
        content = read_file(fpath)
        if not content:
            return
        try:
            pkg = json.loads(content)
        except json.JSONDecodeError:
            return

        all_deps: set[str] = set()
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            all_deps.update(pkg.get(section, {}).keys())

        for dep in all_deps:
            dep_lower = dep.lower()
            for pkg_key, display in _JS_FRAMEWORKS.items():
                if dep_lower == pkg_key.lower() and display not in detected.values():
                    detected[dep] = display
                    break

    # ------------------------------------------------------------------
    # Private helpers — entry points
    # ------------------------------------------------------------------

    def _find_entry_points(
        self,
        repo_path: str,
        package_managers: list[PackageManagerInfo],
    ) -> list[EntryPoint]:
        """
        Locates application entry points using a prioritised candidate list and
        additional heuristics for JavaScript (``package.json`` ``main`` / ``scripts``).
        """
        results: list[EntryPoint] = []
        seen_paths: set[str] = set()

        def _add(path: str, entry_type: str) -> None:
            norm = path.replace("\\", "/")
            if norm not in seen_paths:
                seen_paths.add(norm)
                results.append(EntryPoint(path=norm, entry_type=entry_type))

        # Check static candidates.
        for rel_path, entry_type in _ENTRY_POINT_CANDIDATES:
            full = os.path.join(repo_path, *rel_path.split("/"))
            if os.path.isfile(full):
                _add(rel_path, entry_type)

        # JavaScript: check package.json "main" and "scripts.start" fields.
        for pm in package_managers:
            if pm.config_file.endswith("package.json"):
                fpath = os.path.join(repo_path, pm.config_file)
                if os.path.isfile(fpath):
                    content = read_file(fpath)
                    try:
                        pkg = json.loads(content)
                    except json.JSONDecodeError:
                        continue
                    main_field = pkg.get("main")
                    if isinstance(main_field, str) and main_field:
                        _add(main_field.lstrip("./"), "module")
                    # "scripts": {"start": "node src/server.js"} → parse node arg
                    start_script: str = pkg.get("scripts", {}).get("start", "")
                    m = re.search(r"node\s+([\w./\\-]+\.(?:js|mjs|cjs))", start_script)
                    if m:
                        _add(m.group(1).lstrip("./"), "main")

        # Python: check pyproject.toml [project.scripts] and [tool.poetry.scripts]
        pyproject = os.path.join(repo_path, "pyproject.toml")
        if os.path.isfile(pyproject):
            content = read_file(pyproject)
            # e.g. my-cli = "mypackage.cli:main"
            for m in re.finditer(r'=\s*"([^"]+):(\w+)"', content):
                module_path = m.group(1).replace(".", "/") + ".py"
                full = os.path.join(repo_path, module_path)
                if os.path.isfile(full):
                    _add(module_path, "cli")

        # setup.py entry_points console_scripts
        setup_py = os.path.join(repo_path, "setup.py")
        if os.path.isfile(setup_py):
            content = read_file(setup_py)
            for m in re.finditer(r"'([^']+)=([^']+):(\w+)'", content):
                module_path = m.group(2).strip().replace(".", "/") + ".py"
                full = os.path.join(repo_path, module_path)
                if os.path.isfile(full):
                    _add(module_path, "cli")

        return results

    # ------------------------------------------------------------------
    # Private helpers — tests
    # ------------------------------------------------------------------

    def _find_test_info(
        self,
        repo_path: str,
        package_managers: list[PackageManagerInfo],
    ) -> tuple[bool, list[str], str | None]:
        """
        Detects test directories, individual test files, and the active test
        runner.

        Returns:
            Tuple of (has_tests, test_paths, test_framework_name | None).
        """
        test_paths: list[str] = []
        seen: set[str] = set()

        # Check for well-known test directories.
        for tdir in _TEST_DIRS:
            full = os.path.join(repo_path, tdir)
            if os.path.isdir(full) and tdir not in seen:
                seen.add(tdir)
                test_paths.append(tdir + "/")

        # Check for individual test files in the root (common in small projects).
        try:
            root_entries = os.listdir(repo_path)
        except OSError:
            root_entries = []

        for fname in root_entries:
            for pattern in _TEST_FILE_PATTERNS:
                if pattern.match(fname):
                    frel = fname
                    if frel not in seen:
                        seen.add(frel)
                        test_paths.append(frel)
                    break

        has_tests = bool(test_paths)

        # Detect test framework.
        test_framework: str | None = None

        # Priority: check for framework-specific config files in root.
        for config_fname, fw_name in _TEST_FRAMEWORK_INDICATORS:
            if config_fname.startswith(".") or "/" not in config_fname:
                if config_fname in root_entries:
                    # Validate pytest: setup.cfg / pyproject.toml must contain [tool:pytest] or [tool.pytest]
                    if fw_name == "pytest" and config_fname in ("setup.cfg", "pyproject.toml"):
                        content = read_file(os.path.join(repo_path, config_fname))
                        if "pytest" not in content.lower():
                            continue
                    test_framework = fw_name
                    break

        # Fallback: infer from package manager.
        if test_framework is None:
            pm_names = {pm.name for pm in package_managers}
            if any(n in pm_names for n in ("pip", "poetry", "pipenv", "setuptools")):
                # Check for pytest or unittest imports in any test file.
                pytest_hits = search_files(repo_path, r"import pytest|from pytest", "*.py", 5)
                if pytest_hits:
                    test_framework = "pytest"
                elif has_tests:
                    test_framework = "unittest"   # Python default

        return has_tests, test_paths, test_framework

    # ------------------------------------------------------------------
    # Private helpers — documentation
    # ------------------------------------------------------------------

    def _find_documentation(self, repo_path: str) -> DocumentationInfo:
        """
        Detects README, CONTRIBUTING, CHANGELOG files, and a dedicated docs
        directory within the repository root.
        """
        try:
            root_all = set(os.listdir(repo_path))
        except OSError:
            return DocumentationInfo()

        readme_path: str | None = None
        for candidate in _README_CANDIDATES:
            if candidate in root_all:
                readme_path = candidate
                break

        contributing_path: str | None = None
        for candidate in _CONTRIBUTING_CANDIDATES:
            if candidate in root_all:
                contributing_path = candidate
                break

        changelog_path: str | None = None
        for candidate in _CHANGELOG_CANDIDATES:
            if candidate in root_all:
                changelog_path = candidate
                break

        docs_dir: str | None = None
        for ddir in _DOCS_DIRS:
            if ddir in root_all and os.path.isdir(os.path.join(repo_path, ddir)):
                docs_dir = ddir + "/"
                break

        return DocumentationInfo(
            readme_path=readme_path,
            docs_dir=docs_dir,
            has_contributing=contributing_path is not None,
            contributing_path=contributing_path,
            has_changelog=changelog_path is not None,
            changelog_path=changelog_path,
        )

    # ------------------------------------------------------------------
    # Private helpers — complexity
    # ------------------------------------------------------------------

    def _compute_complexity(
        self,
        repo_tree: list[TreeNode],
        languages: dict[str, LanguageStat],
    ) -> ComplexityMetrics:
        """
        Computes a multi-dimensional complexity assessment from the repo tree
        and language metrics.

        Score breakdown (0–100):
        - **files** (0–25): 1 pt per 10 source files, capped at 250 files.
        - **lines** (0–35): 1 pt per 500 lines of code, capped at 17 500 lines.
        - **max_depth** (0–20): 2 pts per directory nesting level, capped at depth 10.
        - **languages** (0–20): 5 pts per language beyond the first, capped at 4 extras.

        Levels: 0–25 → Low, 26–50 → Medium, 51–75 → High, 76–100 → Very High.
        """
        file_nodes = [n for n in repo_tree if n.node_type == "file"]
        total_files = len(file_nodes)
        total_lines = sum(stat.line_count for stat in languages.values())
        lang_count = len(languages)

        # Max directory depth from tree node paths.
        max_depth = 0
        for node in repo_tree:
            depth = node.path.rstrip("/").count("/")
            if depth > max_depth:
                max_depth = depth

        # Weighted score.
        files_score     = min(_COMPLEXITY_WEIGHTS["files"],     total_files  // 10)
        lines_score     = min(_COMPLEXITY_WEIGHTS["lines"],     total_lines  // 500)
        depth_score     = min(_COMPLEXITY_WEIGHTS["max_depth"], max_depth    *  2)
        lang_score      = min(_COMPLEXITY_WEIGHTS["languages"], max(0, lang_count - 1) * 5)
        score           = files_score + lines_score + depth_score + lang_score

        # Derive level from score.
        level: ComplexityLevel = "Low"
        for threshold, label in _COMPLEXITY_THRESHOLDS:
            if score >= threshold:
                level = label
                break

        return ComplexityMetrics(
            score=score,
            level=level,
            files=total_files,
            lines=total_lines,
            max_depth=max_depth,
            languages=lang_count,
        )

    # ------------------------------------------------------------------
    # Private helpers — recommended reading order
    # ------------------------------------------------------------------

    def _compute_reading_order(
        self,
        repo_path: str,
        documentation: DocumentationInfo,
        entry_points: list[EntryPoint],
        package_managers: list[PackageManagerInfo],
        primary_language: str | None,
    ) -> list[str]:
        """
        Derives a heuristic reading sequence for a new contributor.

        Algorithm (in priority order):
        1. README — orientation and project overview.
        2. CONTRIBUTING — contribution guidelines.
        3. Primary package manager config — dependency context.
        4. Entry point(s) — execution starting point (up to 2).
        5. Main package ``__init__.py`` or ``index`` — core module entry.
        6. CHANGELOG — historical context (optional).

        Only paths that actually exist on disk are included.
        """
        order: list[str] = []
        seen: set[str] = set()

        def _add(rel_path: str) -> None:
            norm = rel_path.replace("\\", "/")
            if norm in seen:
                return
            full = os.path.join(repo_path, norm)
            if os.path.isfile(full):
                seen.add(norm)
                order.append(norm)

        # 1. README
        if documentation.readme_path:
            _add(documentation.readme_path)

        # 2. CONTRIBUTING
        if documentation.contributing_path:
            _add(documentation.contributing_path)

        # 3. Primary package manager config (most information-dense single file)
        pm_priority = ["pyproject.toml", "package.json", "Cargo.toml", "go.mod",
                       "pom.xml", "build.gradle", "requirements.txt", "Gemfile"]
        for pm_fname in pm_priority:
            full = os.path.join(repo_path, pm_fname)
            if os.path.isfile(full):
                _add(pm_fname)
                break

        # 4. Entry points (first two only — don't overwhelm)
        for ep in entry_points[:2]:
            _add(ep.path)

        # 5. Main package __init__.py / index file (walk top-level Python packages)
        if primary_language == "Python":
            try:
                root_entries = os.listdir(repo_path)
            except OSError:
                root_entries = []
            for entry in sorted(root_entries):
                pkg_init = os.path.join(repo_path, entry, "__init__.py")
                if (
                    os.path.isdir(os.path.join(repo_path, entry))
                    and entry not in _SKIP_DIRS
                    and not entry.startswith(".")
                    and os.path.isfile(pkg_init)
                ):
                    _add(f"{entry}/__init__.py")
                    break   # Only add the first (likely main) package

        elif primary_language in ("JavaScript", "TypeScript"):
            for candidate in ("src/index.js", "src/index.ts", "src/app.js", "src/app.ts",
                              "lib/index.js", "lib/index.ts"):
                fpath = os.path.join(repo_path, *candidate.split("/"))
                if os.path.isfile(fpath):
                    _add(candidate)
                    break

        # 6. CHANGELOG — useful historical context
        if documentation.changelog_path:
            _add(documentation.changelog_path)

        return order
