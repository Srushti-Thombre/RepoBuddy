"""
RepositoryContext and supporting Pydantic v2 models.

These models represent the complete structured output of a local repository
analysis pass. They are intentionally free of any AI-reasoning logic — every
field is populated by deterministic, heuristic analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class LanguageStat(BaseModel):
    """Line and file count statistics for a single programming language."""

    file_count: int = Field(..., description="Number of source files for this language.")
    line_count: int = Field(..., description="Total lines of code across all files.")
    percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Percentage share by line count (0–100)."
    )


class PackageManagerInfo(BaseModel):
    """A detected package manager and its primary configuration file."""

    name: str = Field(
        ...,
        description=(
            "Human-readable package manager name "
            "(e.g. 'pip', 'poetry', 'npm', 'yarn', 'cargo', 'go modules')."
        ),
    )
    config_file: str = Field(
        ...,
        description="Relative path (forward slashes) to the primary config file.",
    )


class BuildSystemInfo(BaseModel):
    """A detected build system or CI/CD tool and its configuration file."""

    name: str = Field(
        ...,
        description=(
            "Human-readable build system name "
            "(e.g. 'make', 'cmake', 'webpack', 'Docker', 'GitHub Actions')."
        ),
    )
    config_file: str = Field(
        ...,
        description="Relative path (forward slashes) to the primary config file.",
    )


class EntryPoint(BaseModel):
    """A detected application entry point file."""

    path: str = Field(
        ...,
        description="Relative path (forward slashes) to the entry point file.",
    )
    entry_type: str = Field(
        ...,
        description=(
            "Semantic type of the entry point: "
            "'main', 'wsgi', 'asgi', 'cli', 'index', 'module', or 'unknown'."
        ),
    )


class DocumentationInfo(BaseModel):
    """Detected documentation structure within the repository."""

    readme_path: str | None = Field(
        None, description="Relative path to the primary README file, if found."
    )
    docs_dir: str | None = Field(
        None, description="Relative path to a dedicated docs directory, if found."
    )
    has_contributing: bool = Field(
        False, description="Whether a CONTRIBUTING file is present."
    )
    contributing_path: str | None = Field(
        None, description="Relative path to the CONTRIBUTING file, if present."
    )
    has_changelog: bool = Field(
        False, description="Whether a CHANGELOG or HISTORY file is present."
    )
    changelog_path: str | None = Field(
        None, description="Relative path to the CHANGELOG/HISTORY file, if present."
    )


TreeNodeType = Literal["file", "directory"]

ComplexityLevel = Literal["Low", "Medium", "High", "Very High"]


class TreeNode(BaseModel):
    """A single node in the repository file tree."""

    path: str = Field(
        ...,
        description=(
            "Relative path (forward slashes). "
            "Directories end with '/'; files do not."
        ),
    )
    node_type: TreeNodeType = Field(..., description="'file' or 'directory'.")
    size_bytes: int | None = Field(
        None,
        description="File size in bytes. None for directories.",
    )


class ComplexityMetrics(BaseModel):
    """
    Multi-dimensional complexity assessment derived from static file metrics.

    The score (0–100) is computed as a weighted sum of four independent signals:
    file count, total lines, directory nesting depth, and language diversity.
    The level label provides a human-readable tier for downstream consumers
    (e.g. the ArchitectureAgent) to interpret without re-implementing thresholds.
    """

    score: int = Field(..., ge=0, le=100, description="Composite complexity score (0–100).")
    level: ComplexityLevel = Field(..., description="Complexity tier derived from score.")
    files: int = Field(..., description="Total number of source files analyzed.")
    lines: int = Field(..., description="Total lines of code across all source files.")
    max_depth: int = Field(..., description="Maximum directory nesting depth.")
    languages: int = Field(..., description="Number of distinct programming languages detected.")


# ---------------------------------------------------------------------------
# Top-level model
# ---------------------------------------------------------------------------


class RepositoryContext(BaseModel):
    """
    Complete structured output of a RepositoryAgent analysis pass.

    All fields are populated by deterministic, heuristic filesystem analysis.
    This model is the primary handoff artifact between the RepositoryAgent and
    downstream agents (ArchitectureAgent, ContributionAgent, ReportAgent).

    Consumers that need a plain dict can call ``context.model_dump()``.
    """

    repo_path: str = Field(..., description="Absolute path to the analyzed repository.")

    # Language distribution
    languages: dict[str, LanguageStat] = Field(
        default_factory=dict,
        description="Language name → LanguageStat. Ordered by descending line count.",
    )
    primary_language: str | None = Field(
        None, description="Dominant language by line count."
    )

    # Technology stack
    frameworks: list[str] = Field(
        default_factory=list,
        description="Detected frameworks and major libraries (e.g. 'Django', 'React', 'FastAPI').",
    )
    package_managers: list[PackageManagerInfo] = Field(
        default_factory=list,
        description="All detected package managers with their config file paths.",
    )
    build_systems: list[BuildSystemInfo] = Field(
        default_factory=list,
        description="All detected build tools, bundlers, and CI/CD systems.",
    )

    # Codebase structure
    entry_points: list[EntryPoint] = Field(
        default_factory=list,
        description="Detected application entry point files.",
    )

    # Testing
    test_framework: str | None = Field(
        None, description="Detected primary test runner (e.g. 'pytest', 'jest', 'unittest')."
    )
    has_tests: bool = Field(False, description="Whether test files or directories were found.")
    test_paths: list[str] = Field(
        default_factory=list,
        description="Relative paths to detected test directories or files.",
    )

    # Documentation
    documentation: DocumentationInfo = Field(
        default_factory=DocumentationInfo,
        description="Detected documentation structure.",
    )

    # Repository tree and complexity
    repo_tree: list[TreeNode] = Field(
        default_factory=list,
        description=(
            "Flat list of repository tree nodes (up to 1 000 entries). "
            "Directories end with '/'."
        ),
    )
    complexity: ComplexityMetrics = Field(
        ...,
        description="Multi-dimensional complexity metrics derived from static analysis.",
    )

    # Mentor-specific field
    recommended_reading_order: list[str] = Field(
        default_factory=list,
        description=(
            "Heuristically derived file reading sequence for a new contributor. "
            "Intended as the seed for a ContributionAgent learning path."
        ),
    )

    # Metadata
    analysis_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of when this analysis was produced (timezone-aware).",
    )
