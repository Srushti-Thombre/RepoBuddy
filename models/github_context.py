"""
GitHubContext and supporting Pydantic v2 models.

These models represent the complete GitHub intelligence gathered from a
repository via the GitHub REST API. All fields are populated by deterministic
API calls — no AI reasoning is involved.

Downstream agents (ArchitectureAgent, ContributionAgent, ReportAgent) receive
the ``GitHubContext`` directly. Consumers that need a plain dict can call
``context.model_dump()``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

HealthLevel = Literal["Excellent", "Good", "Fair", "Poor"]


# ---------------------------------------------------------------------------
# Activity record sub-models
# ---------------------------------------------------------------------------


class CommitRecord(BaseModel):
    """A summarised commit entry from the repository history."""

    sha: str = Field(..., description="Short commit SHA (8 characters).")
    message: str = Field(
        "", description="First line of the commit message (up to 120 characters)."
    )
    author: str = Field("", description="Commit author display name.")
    date: datetime | None = Field(None, description="Commit timestamp (UTC).")


class IssueRecord(BaseModel):
    """A summarised open issue entry."""

    number: int = Field(..., description="GitHub issue number.")
    title: str = Field(..., description="Issue title.")
    state: str = Field("open", description="Issue state — 'open' or 'closed'.")
    labels: list[str] = Field(
        default_factory=list, description="Label names applied to this issue."
    )
    created_at: datetime | None = Field(None, description="Issue creation timestamp (UTC).")
    updated_at: datetime | None = Field(None, description="Last activity timestamp (UTC).")
    comments: int = Field(0, description="Number of comments on this issue.")
    user_login: str = Field("", description="GitHub username of the issue author.")


class PullRequestRecord(BaseModel):
    """A summarised open pull request entry."""

    number: int = Field(..., description="GitHub PR number.")
    title: str = Field(..., description="PR title.")
    state: str = Field("open", description="PR state — 'open', 'closed', or 'merged'.")
    labels: list[str] = Field(
        default_factory=list, description="Label names applied to this PR."
    )
    created_at: datetime | None = Field(None, description="PR creation timestamp (UTC).")
    updated_at: datetime | None = Field(None, description="Last activity timestamp (UTC).")
    merged_at: datetime | None = Field(None, description="Merge timestamp if merged, else None.")
    draft: bool = Field(False, description="True if the PR is still a draft.")
    user_login: str = Field("", description="GitHub username of the PR author.")
    head_ref: str = Field("", description="Source branch name.")


class LabelRecord(BaseModel):
    """A GitHub issue / PR label."""

    name: str = Field(..., description="Label name (e.g. 'good first issue').")
    color: str = Field("", description="6-digit hex colour code (without '#').")
    description: str | None = Field(None, description="Human-readable label description.")


class ContributorRecord(BaseModel):
    """A contributor to the repository, sorted by commit count."""

    login: str = Field(..., description="GitHub username.")
    contributions: int = Field(0, description="Total number of commits attributed.")
    html_url: str = Field("", description="GitHub profile URL.")


class ReleaseRecord(BaseModel):
    """The most recent published release of the repository."""

    tag_name: str = Field(..., description="Release tag (e.g. 'v1.2.3').")
    name: str | None = Field(None, description="Release title, if set.")
    published_at: datetime | None = Field(None, description="Publication timestamp (UTC).")
    prerelease: bool = Field(False, description="True if labelled as a pre-release.")
    draft: bool = Field(False, description="True if the release is still a draft.")
    html_url: str = Field("", description="Release page URL on GitHub.")


# ---------------------------------------------------------------------------
# Repository health sub-model
# ---------------------------------------------------------------------------


class RepositoryHealth(BaseModel):
    """
    Multi-dimensional repository health assessment derived entirely from
    GitHub REST API data.

    The composite ``score`` (0–100) is computed from five independent signals:

    1. **Availability** (25 pts): not archived / not disabled.
    2. **Commit recency** (30 pts): days since most recent push.
    3. **Release cadence** (20 pts): age of the latest published release.
    4. **Issue management** (15 pts): absolute open issue count.
    5. **Community signals** (10 pts): contributor count, wiki, discussions, projects.
    """

    score: int = Field(..., ge=0, le=100, description="Composite health score (0–100).")
    level: HealthLevel = Field(
        ...,
        description="Health tier derived from score: Excellent (≥80), Good (≥60), Fair (≥40), Poor (<40).",
    )

    # Commit activity
    last_commit_age_days: int | None = Field(
        None, description="Days since the most recent commit, or None if unknown."
    )
    commit_frequency: str = Field(
        ...,
        description=(
            "Qualitative frequency label: 'Very Active' (≤7d), 'Active' (≤30d), "
            "'Moderate' (≤90d), 'Low' (≤365d), 'Inactive' (>365d), or 'Unknown'."
        ),
    )

    # Activity signals
    issue_activity: str = Field(
        ...,
        description="Issue open-rate in the last 30 days: 'High' (≥10), 'Medium' (≥3), or 'Low'.",
    )
    pull_request_activity: str = Field(
        ...,
        description="PR open-rate in the last 30 days: 'High' (≥5), 'Medium' (≥2), or 'Low'.",
    )
    maintainer_responsiveness: str | None = Field(
        None,
        description=(
            "Estimated responsiveness from issue update-lag proxy: "
            "'Highly Responsive' (≤2d avg), 'Responsive' (≤7d), "
            "'Moderately Responsive' (≤30d), 'Slow' (>30d), or None if indeterminate."
        ),
    )

    # Repository flags
    archived: bool = Field(False, description="Repository is archived (read-only).")
    disabled: bool = Field(False, description="Repository is disabled.")
    has_wiki: bool = Field(False, description="GitHub Wiki is enabled.")
    has_discussions: bool = Field(False, description="GitHub Discussions is enabled.")
    has_projects: bool = Field(False, description="GitHub Projects is enabled.")
    has_releases: bool = Field(False, description="At least one published release exists.")

    # Count snapshots
    open_issues_count: int = Field(0, description="Total open issues as reported by the API.")
    open_prs_count: int = Field(0, description="Number of open pull requests in the sample.")
    issue_close_rate: float | None = Field(
        None,
        description=(
            "Fraction of issues that are closed vs total (None when total is unavailable "
            "from the sampled data alone)."
        ),
    )


# ---------------------------------------------------------------------------
# Top-level context model
# ---------------------------------------------------------------------------


class GitHubContext(BaseModel):
    """
    Complete GitHub intelligence for a single repository.

    Populated entirely from GitHub REST API responses — no AI reasoning
    involved. This is the primary handoff artifact from ``GitHubAgent`` to
    ``ArchitectureAgent``, ``ContributionAgent``, and ``ReportAgent``.

    Consumers that need a plain dict can call ``context.model_dump()``.
    """

    # Core identity
    repository_name: str = Field(..., description="Repository name without owner prefix.")
    owner: str = Field(..., description="Owner login (user or organisation).")
    full_name: str = Field(..., description="Canonical '{owner}/{repo}' identifier.")
    description: str | None = Field(None, description="Repository description from GitHub.")
    default_branch: str = Field("main", description="Default branch name.")
    license: str | None = Field(None, description="Full license name, e.g. 'MIT License'.")
    license_spdx: str | None = Field(None, description="SPDX license ID, e.g. 'MIT'.")
    topics: list[str] = Field(default_factory=list, description="Repository topic tags.")
    homepage: str | None = Field(None, description="Project homepage URL if configured.")

    # Popularity
    stars: int = Field(0, description="Stargazer count.")
    forks: int = Field(0, description="Fork count.")
    watchers: int = Field(0, description="Subscriber / watcher count.")

    # Activity counts
    open_issue_count: int = Field(0, description="Total open issue count from API metadata.")
    open_pull_request_count: int = Field(0, description="Open PRs in the sampled window.")

    # Release
    latest_release: ReleaseRecord | None = Field(
        None,
        description="Most recent published release, or None if the repository has no releases.",
    )

    # Timestamps
    created_at: datetime | None = Field(None, description="Repository creation timestamp (UTC).")
    updated_at: datetime | None = Field(None, description="Last metadata update timestamp (UTC).")
    pushed_at: datetime | None = Field(None, description="Last git push timestamp (UTC).")

    # Sampled activity data
    recent_commits: list[CommitRecord] = Field(
        default_factory=list, description="Most recent commits (up to 10)."
    )
    open_issues: list[IssueRecord] = Field(
        default_factory=list,
        description="Sample of open issues (up to 100, pull requests excluded).",
    )
    open_pull_requests: list[PullRequestRecord] = Field(
        default_factory=list, description="Sample of open pull requests (up to 50)."
    )
    labels: list[LabelRecord] = Field(
        default_factory=list, description="All repository labels."
    )
    contributors: list[ContributorRecord] = Field(
        default_factory=list,
        description="Top contributors sorted by commit count (up to 50).",
    )
    maintainers: list[str] = Field(
        default_factory=list,
        description=(
            "Heuristically determined maintainer logins: top contributors by commit count "
            "(top 5 when ≥10 total contributors, otherwise top 3)."
        ),
    )

    # GitHub API language breakdown (bytes per language)
    languages_from_api: dict[str, int] = Field(
        default_factory=dict,
        description="Language → byte count as reported by GitHub's linguist analysis.",
    )

    # Health assessment
    repository_health: RepositoryHealth = Field(
        ..., description="Structured health assessment derived from API data."
    )

    # Metadata
    analysis_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of when this analysis was produced (timezone-aware).",
    )
