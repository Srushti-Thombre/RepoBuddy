"""
GitHubAgent — deterministic GitHub repository intelligence.

Orchestrates the GitHub MCP tools into a fully-populated ``GitHubContext``
without any AI reasoning. All data is sourced from the GitHub REST API; all
scoring and classification is heuristic and rule-based.

The agent performs 8 sequential API calls and assembles the results into a
single, structured context object that downstream agents can consume directly
or via ``context.model_dump()``.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone

from google.adk import Agent

from models.github_context import (
    CommitRecord,
    ContributorRecord,
    GitHubContext,
    HealthLevel,
    IssueRecord,
    LabelRecord,
    PullRequestRecord,
    ReleaseRecord,
    RepositoryHealth,
)
from mcp_server.tools_github import (
    get_contributors,
    get_labels,
    get_latest_release,
    get_open_issues,
    get_pull_requests,
    get_recent_commits,
    get_repository_languages,
    get_repository_metadata,
    get_repository_topics,
)


# ---------------------------------------------------------------------------
# Health scoring constants
# ---------------------------------------------------------------------------

#: Weighted contribution caps for each signal (must sum to 100).
_HEALTH_WEIGHTS: dict[str, int] = {
    "availability":   25,  # not archived, not disabled
    "commit_recency": 30,  # days since last commit
    "release":        20,  # age of latest release
    "issues":         15,  # open issue volume
    "community":      10,  # contributors, wiki, discussions, projects
}

_HEALTH_LEVELS: list[tuple[int, HealthLevel]] = [
    (80, "Excellent"),
    (60, "Good"),
    (40, "Fair"),
    (0,  "Poor"),
]

#: Regex patterns for parsing GitHub repository URLs.
_GITHUB_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s?#]+?)(?:\.git)?/?$"
)
_SHORT_REPO_PATTERN = re.compile(r"^([^/\s]+)/([^/\s]+)$")


# ===========================================================================
# GitHubAgent
# ===========================================================================


class GitHubAgent:
    """
    GitHubAgent gathers and analyses telemetry directly from the GitHub repository API.

    Responsibilities:
    - Interface with GitHub tools to collect repository metadata, issues, and PRs.
    - Check for duplicate ideas or overlap by scanning current issues and PR requests.
    - Analyse repository health parameters (activity frequency, commit intervals, pull request close rate).
    - Estimate maintainer responsiveness to evaluate how quickly new contributions are reviewed.
    """

    def __init__(self) -> None:
        """
        Initializes the GitHubAgent and configures its underlying ADK Agent structure
        with all GitHub MCP tools registered.
        """
        self.adk_agent = Agent(
            name="GitHubAgent",
            instruction=(
                "You are an API integration agent. Your goal is to gather pull requests, issues, commits, "
                "and label data from public GitHub repositories, inspect them for duplicate suggestions, "
                "and compute overall repository health metrics."
            ),
            tools=[
                get_repository_metadata,
                get_open_issues,
                get_pull_requests,
                get_labels,
                get_recent_commits,
                get_contributors,
                get_repository_languages,
                get_repository_topics,
                get_latest_release,
            ],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_repository(self, repo_url: str) -> GitHubContext:
        """
        Collects full GitHub intelligence for the repository identified by
        ``repo_url`` and returns a structured ``GitHubContext``.

        All API calls are made synchronously. No AI reasoning is performed.

        Args:
            repo_url (str): A GitHub repository URL in any of the supported
                formats (see ``_parse_repo_url`` for accepted patterns).

        Returns:
            GitHubContext: Fully populated context object.

        Raises:
            ValueError: If the URL cannot be parsed or the repository does
                not exist / is inaccessible.
        """
        owner, repo_name = self._parse_repo_url(repo_url)
        print(
            f"[GitHubAgent] Analysing {owner}/{repo_name} …",
            file=sys.stderr,
        )

        # 1. Repository metadata (single API call, covers most scalar fields).
        metadata = get_repository_metadata(owner, repo_name)
        if not metadata:
            raise ValueError(
                f"Repository '{owner}/{repo_name}' was not found or is inaccessible. "
                "Ensure the repository is public and the URL is correct."
            )
        print("[GitHubAgent] Metadata fetched.", file=sys.stderr)

        # 2. Issues (filters out PRs automatically in the tool).
        raw_issues = get_open_issues(owner, repo_name, max_count=100)
        print(f"[GitHubAgent] Issues: {len(raw_issues)} open.", file=sys.stderr)

        # 3. Pull requests.
        raw_prs = get_pull_requests(owner, repo_name, state="open", max_count=50)
        print(f"[GitHubAgent] PRs: {len(raw_prs)} open.", file=sys.stderr)

        # 4. Labels.
        raw_labels = get_labels(owner, repo_name)
        print(f"[GitHubAgent] Labels: {len(raw_labels)}.", file=sys.stderr)

        # 5. Recent commits.
        raw_commits = get_recent_commits(owner, repo_name, count=10)
        print(f"[GitHubAgent] Commits: {len(raw_commits)} fetched.", file=sys.stderr)

        # 6. Contributors.
        raw_contributors = get_contributors(owner, repo_name, max_count=50)
        print(f"[GitHubAgent] Contributors: {len(raw_contributors)}.", file=sys.stderr)

        # 7. Language breakdown from GitHub API.
        languages_from_api = get_repository_languages(owner, repo_name)
        print(
            f"[GitHubAgent] Languages (API): {list(languages_from_api.keys())}.",
            file=sys.stderr,
        )

        # 8. Latest release.
        raw_release = get_latest_release(owner, repo_name)
        print(
            f"[GitHubAgent] Latest release: {raw_release.get('tag_name') if raw_release else 'none'}.",
            file=sys.stderr,
        )

        # Assemble and return the full context.
        context = self._build_context(
            owner=owner,
            repo_name=repo_name,
            metadata=metadata,
            raw_issues=raw_issues,
            raw_prs=raw_prs,
            raw_labels=raw_labels,
            raw_commits=raw_commits,
            raw_contributors=raw_contributors,
            languages_from_api=languages_from_api,
            raw_release=raw_release,
        )
        print("[GitHubAgent] Analysis complete.", file=sys.stderr)
        return context

    def gather_github_metadata(self, repo_owner: str, repo_name: str) -> dict:
        """
        Compatibility shim kept for the OrchestratorAgent scaffold.

        Calls ``analyze_repository`` and returns a ``model_dump()`` dict
        in the shape expected by the original stub.

        Args:
            repo_owner (str): Repository owner login.
            repo_name (str): Repository name.

        Returns:
            dict: Serialised ``GitHubContext`` plus convenience top-level keys.
        """
        ctx = self.analyze_repository(f"https://github.com/{repo_owner}/{repo_name}")
        d = ctx.model_dump()
        # Surface a few keys at the top level for backward compat with the stub.
        return {
            "metadata":             d,
            "open_issues":          d["open_issues"],
            "open_prs":             d["open_pull_requests"],
            "labels":               d["labels"],
            "recent_commits":       d["recent_commits"],
            "repository_health": {
                "active_maintenance":            not d["repository_health"]["archived"],
                "commit_frequency_rating":       d["repository_health"]["commit_frequency"],
                "maintainer_responsiveness_score": d["repository_health"]["maintainer_responsiveness"],
                "overall_health_rating":         d["repository_health"]["level"],
            },
            "duplicate_risk_database": [
                {"title": i["title"], "labels": i["labels"]}
                for i in d["open_issues"]
            ],
        }

    # ------------------------------------------------------------------
    # Private helpers — URL parsing
    # ------------------------------------------------------------------

    def _parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """
        Parses a GitHub repository URL into (owner, repo_name).

        Accepted formats::

            https://github.com/google/adk-python
            https://github.com/google/adk-python.git
            github.com/google/adk-python
            google/adk-python

        Args:
            repo_url (str): Repository identifier in any supported format.

        Returns:
            tuple[str, str]: ``(owner, repo_name)`` with ``.git`` suffix stripped.

        Raises:
            ValueError: If the URL cannot be matched to a known pattern.
        """
        url = repo_url.strip()

        m = _GITHUB_URL_PATTERN.search(url)
        if m:
            return m.group(1), m.group(2).removesuffix(".git")

        m = _SHORT_REPO_PATTERN.match(url)
        if m:
            return m.group(1), m.group(2).removesuffix(".git")

        raise ValueError(
            f"Cannot parse GitHub repository URL: '{repo_url}'. "
            "Expected formats: 'https://github.com/owner/repo' or 'owner/repo'."
        )

    # ------------------------------------------------------------------
    # Private helpers — datetime
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_dt(value: str | None) -> datetime | None:
        """
        Parses an ISO-8601 date-time string returned by the GitHub API into a
        timezone-aware ``datetime`` object.

        Handles both ``'Z'`` suffix and explicit ``+00:00`` offset. Returns
        ``None`` for missing or malformed values without raising.
        """
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    # ------------------------------------------------------------------
    # Private helpers — model conversion
    # ------------------------------------------------------------------

    def _to_commits(self, raw: list[dict]) -> list[CommitRecord]:
        return [
            CommitRecord(
                sha=item.get("sha", ""),
                message=item.get("message", ""),
                author=item.get("author", ""),
                date=self._parse_dt(item.get("date")),
            )
            for item in raw
            if isinstance(item, dict)
        ]

    def _to_issues(self, raw: list[dict]) -> list[IssueRecord]:
        return [
            IssueRecord(
                number=item.get("number", 0),
                title=item.get("title", ""),
                state=item.get("state", "open"),
                labels=item.get("labels", []),
                created_at=self._parse_dt(item.get("created_at")),
                updated_at=self._parse_dt(item.get("updated_at")),
                comments=item.get("comments", 0),
                user_login=item.get("user_login", ""),
            )
            for item in raw
            if isinstance(item, dict)
        ]

    def _to_prs(self, raw: list[dict]) -> list[PullRequestRecord]:
        return [
            PullRequestRecord(
                number=item.get("number", 0),
                title=item.get("title", ""),
                state=item.get("state", "open"),
                labels=item.get("labels", []),
                created_at=self._parse_dt(item.get("created_at")),
                updated_at=self._parse_dt(item.get("updated_at")),
                merged_at=self._parse_dt(item.get("merged_at")),
                draft=item.get("draft", False),
                user_login=item.get("user_login", ""),
                head_ref=item.get("head_ref", ""),
            )
            for item in raw
            if isinstance(item, dict)
        ]

    def _to_labels(self, raw: list[dict]) -> list[LabelRecord]:
        return [
            LabelRecord(
                name=item.get("name", ""),
                color=item.get("color", ""),
                description=item.get("description"),
            )
            for item in raw
            if isinstance(item, dict)
        ]

    def _to_contributors(self, raw: list[dict]) -> list[ContributorRecord]:
        return [
            ContributorRecord(
                login=item.get("login", ""),
                contributions=item.get("contributions", 0),
                html_url=item.get("html_url", ""),
            )
            for item in raw
            if isinstance(item, dict)
        ]

    def _to_release(self, raw: dict | None) -> ReleaseRecord | None:
        if not raw:
            return None
        return ReleaseRecord(
            tag_name=raw.get("tag_name", ""),
            name=raw.get("name"),
            published_at=self._parse_dt(raw.get("published_at")),
            prerelease=raw.get("prerelease", False),
            draft=raw.get("draft", False),
            html_url=raw.get("html_url", ""),
        )

    # ------------------------------------------------------------------
    # Private helpers — repository health
    # ------------------------------------------------------------------

    def _compute_repository_health(
        self,
        metadata: dict,
        commits: list[CommitRecord],
        issues: list[IssueRecord],
        prs: list[PullRequestRecord],
        release: ReleaseRecord | None,
        contributors: list[ContributorRecord],
    ) -> RepositoryHealth:
        """
        Computes a multi-dimensional repository health score from the
        gathered API data.

        Score breakdown (0–100 — see ``_HEALTH_WEIGHTS``):

        1. **Availability** (25 pts): +15 if not archived, +10 if not disabled.
        2. **Commit recency** (30 pts): based on days since most recent commit.
        3. **Release cadence** (20 pts): based on age of the latest release.
        4. **Issue management** (15 pts): based on total open issue count.
        5. **Community signals** (10 pts): contributor count, wiki, discussions, projects.

        All signals are computed deterministically from the available data.
        """
        now = datetime.now(timezone.utc)
        archived = metadata.get("archived", False)
        disabled = metadata.get("disabled", False)
        score = 0

        # ── 1. Availability (25 pts) ──────────────────────────────────
        if not archived:
            score += 15
        if not disabled:
            score += 10

        # ── 2. Commit recency (30 pts) ────────────────────────────────
        last_commit_age_days: int | None = None
        if commits and commits[0].date is not None:
            last_commit_age_days = max(0, (now - commits[0].date).days)
            if last_commit_age_days <= 7:
                score += 30
            elif last_commit_age_days <= 30:
                score += 22
            elif last_commit_age_days <= 90:
                score += 12
            elif last_commit_age_days <= 365:
                score += 5
            # else 0 pts — inactive

        # ── 3. Release cadence (20 pts) ───────────────────────────────
        if release and release.published_at is not None:
            release_age = max(0, (now - release.published_at).days)
            if release_age <= 90:
                score += 20
            elif release_age <= 180:
                score += 14
            elif release_age <= 365:
                score += 8
            elif release_age <= 730:
                score += 3
            # else 0 pts — stale release

        # ── 4. Issue management (15 pts) ──────────────────────────────
        open_count = metadata.get("open_issues_count", len(issues))
        if open_count <= 10:
            score += 15
        elif open_count <= 50:
            score += 10
        elif open_count <= 200:
            score += 5
        # else 0 pts — high issue backlog

        # ── 5. Community signals (10 pts) ─────────────────────────────
        contrib_count = len(contributors)
        if contrib_count >= 10:
            score += 5
        elif contrib_count >= 3:
            score += 3
        if metadata.get("has_wiki") or metadata.get("has_discussions"):
            score += 3
        if metadata.get("has_projects"):
            score += 2

        score = min(100, score)

        # ── Level ─────────────────────────────────────────────────────
        level: HealthLevel = "Poor"
        for threshold, label in _HEALTH_LEVELS:
            if score >= threshold:
                level = label
                break

        # ── Commit frequency label ────────────────────────────────────
        if last_commit_age_days is None:
            commit_frequency = "Unknown"
        elif last_commit_age_days <= 7:
            commit_frequency = "Very Active"
        elif last_commit_age_days <= 30:
            commit_frequency = "Active"
        elif last_commit_age_days <= 90:
            commit_frequency = "Moderate"
        elif last_commit_age_days <= 365:
            commit_frequency = "Low"
        else:
            commit_frequency = "Inactive"

        # ── Issue activity (issues opened in last 30 days) ────────────
        recent_issues = self._count_recent(issues, days=30)
        if recent_issues >= 10:
            issue_activity = "High"
        elif recent_issues >= 3:
            issue_activity = "Medium"
        else:
            issue_activity = "Low"

        # ── PR activity (PRs opened in last 30 days) ──────────────────
        recent_prs = self._count_recent(prs, days=30)
        if recent_prs >= 5:
            pr_activity = "High"
        elif recent_prs >= 2:
            pr_activity = "Medium"
        else:
            pr_activity = "Low"

        # ── Maintainer responsiveness (proxy: issue update lag) ────────
        maintainer_responsiveness = self._estimate_responsiveness(issues, now)

        return RepositoryHealth(
            score=score,
            level=level,
            last_commit_age_days=last_commit_age_days,
            commit_frequency=commit_frequency,
            issue_activity=issue_activity,
            pull_request_activity=pr_activity,
            maintainer_responsiveness=maintainer_responsiveness,
            archived=archived,
            disabled=disabled,
            has_wiki=metadata.get("has_wiki", False),
            has_discussions=metadata.get("has_discussions", False),
            has_projects=metadata.get("has_projects", False),
            has_releases=release is not None,
            open_issues_count=open_count,
            open_prs_count=len(prs),
            issue_close_rate=None,  # Requires additional historical API calls
        )

    def _count_recent(
        self,
        records: list[IssueRecord] | list[PullRequestRecord],
        days: int,
    ) -> int:
        """Counts records whose ``created_at`` falls within the last ``days`` days."""
        now = datetime.now(timezone.utc)
        count = 0
        for rec in records:
            if rec.created_at is not None:
                try:
                    age = (now - rec.created_at).days
                    if age <= days:
                        count += 1
                except TypeError:
                    pass
        return count

    def _estimate_responsiveness(
        self,
        issues: list[IssueRecord],
        now: datetime,
    ) -> str | None:
        """
        Estimates maintainer responsiveness as a qualitative label.

        Proxy metric: average number of days between ``created_at`` and
        ``updated_at`` across the first 20 open issues (where both values are
        available). A small gap suggests that maintainers engaged quickly.

        Returns ``None`` when there is insufficient data.
        """
        if not issues:
            return None

        lags: list[float] = []
        for issue in issues[:20]:
            if issue.created_at is not None and issue.updated_at is not None:
                try:
                    lag = max(0.0, (issue.updated_at - issue.created_at).total_seconds() / 86400)
                    lags.append(lag)
                except TypeError:
                    pass

        if not lags:
            return None

        avg_days = sum(lags) / len(lags)
        if avg_days <= 2:
            return "Highly Responsive"
        if avg_days <= 7:
            return "Responsive"
        if avg_days <= 30:
            return "Moderately Responsive"
        return "Slow"

    # ------------------------------------------------------------------
    # Private helpers — context assembly
    # ------------------------------------------------------------------

    def _build_context(
        self,
        owner: str,
        repo_name: str,
        metadata: dict,
        raw_issues: list[dict],
        raw_prs: list[dict],
        raw_labels: list[dict],
        raw_commits: list[dict],
        raw_contributors: list[dict],
        languages_from_api: dict[str, int],
        raw_release: dict | None,
    ) -> GitHubContext:
        """
        Assembles a ``GitHubContext`` from the raw tool outputs.

        Converts all raw dicts into typed sub-models, computes derived fields
        (health, maintainers), and returns the complete context.
        """
        commits      = self._to_commits(raw_commits)
        issues       = self._to_issues(raw_issues)
        prs          = self._to_prs(raw_prs)
        labels       = self._to_labels(raw_labels)
        contributors = self._to_contributors(raw_contributors)
        release      = self._to_release(raw_release)

        # Heuristic maintainers: top contributors by commit count.
        if len(contributors) >= 10:
            maintainers = [c.login for c in contributors[:5]]
        elif contributors:
            maintainers = [c.login for c in contributors[:3]]
        else:
            maintainers = []

        health = self._compute_repository_health(
            metadata=metadata,
            commits=commits,
            issues=issues,
            prs=prs,
            release=release,
            contributors=contributors,
        )

        return GitHubContext(
            # Core identity
            repository_name=metadata.get("name", repo_name),
            owner=metadata.get("owner", owner),
            full_name=metadata.get("full_name", f"{owner}/{repo_name}"),
            description=metadata.get("description"),
            default_branch=metadata.get("default_branch", "main"),
            license=metadata.get("license_name"),
            license_spdx=metadata.get("license_spdx"),
            topics=metadata.get("topics", []),
            homepage=metadata.get("homepage"),
            # Popularity
            stars=metadata.get("stars", 0),
            forks=metadata.get("forks", 0),
            watchers=metadata.get("watchers", 0),
            # Counts
            open_issue_count=metadata.get("open_issues_count", len(issues)),
            open_pull_request_count=len(prs),
            # Release
            latest_release=release,
            # Timestamps
            created_at=self._parse_dt(metadata.get("created_at")),
            updated_at=self._parse_dt(metadata.get("updated_at")),
            pushed_at=self._parse_dt(metadata.get("pushed_at")),
            # Activity
            recent_commits=commits,
            open_issues=issues,
            open_pull_requests=prs,
            labels=labels,
            contributors=contributors,
            maintainers=maintainers,
            # API languages
            languages_from_api=languages_from_api,
            # Health
            repository_health=health,
        )
