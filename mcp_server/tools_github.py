"""
GitHub REST API tools for the RepoBuddy MCP server.

All functions perform authenticated (or anonymous) HTTP requests against the
GitHub REST API v3. No AI reasoning is involved — every result is derived
from raw API responses.

Authentication:
    Set GITHUB_TOKEN in your .env file. Functions will automatically include
    the token in the Authorization header, raising the rate limit from 60 to
    5 000 requests/hour. If no token is present the tools operate in
    unauthenticated mode and log a one-time advisory.

Security:
    The token value is never logged or printed. All diagnostic output uses
    the sanitised request URL only.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_API_BASE: str = "https://api.github.com"
_DEFAULT_ACCEPT: str = "application/vnd.github.v3+json"
_API_VERSION: str = "2022-11-28"
_REQUEST_TIMEOUT: float = 30.0
_TOPICS_ACCEPT: str = "application/vnd.github.mercy-preview+json"

#: Suppress the "unauthenticated" advisory after the first call.
_warned_unauthenticated: bool = False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_headers(accept: str = _DEFAULT_ACCEPT) -> dict[str, str]:
    """
    Constructs request headers, injecting the Bearer token when available.

    The token is sourced from the ``GITHUB_TOKEN`` environment variable.
    The variable is read at call-time so that ``load_dotenv()`` in the
    application entry point has already populated it.

    The token value is never exposed in logs or return values.
    """
    global _warned_unauthenticated

    headers: dict[str, str] = {
        "Accept": accept,
        "User-Agent": "RepoBuddy/1.0 (https://github.com/RepoBuddy)",
        "X-GitHub-Api-Version": _API_VERSION,
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif not _warned_unauthenticated:
        _warned_unauthenticated = True
        print(
            "[tools_github] GITHUB_TOKEN is not set — operating in unauthenticated mode "
            "(60 requests/hour limit). Set GITHUB_TOKEN in .env to increase to 5 000/hour.",
            file=sys.stderr,
        )
    return headers


def _check_rate_limit(response: httpx.Response) -> None:
    """
    Inspects rate-limit headers and logs a warning when the quota is nearly
    exhausted. Never raises; callers decide how to handle low quota.
    """
    try:
        remaining = int(response.headers.get("X-RateLimit-Remaining", "-1"))
        limit = int(response.headers.get("X-RateLimit-Limit", "-1"))
        reset = response.headers.get("X-RateLimit-Reset", "unknown")
        if remaining != -1 and remaining <= 5:
            print(
                f"[tools_github] Rate limit nearly exhausted: "
                f"{remaining}/{limit} requests remaining. Resets at Unix time {reset}.",
                file=sys.stderr,
            )
    except (ValueError, TypeError):
        pass


def _github_request(
    path: str,
    params: dict[str, Any] | None = None,
    accept: str = _DEFAULT_ACCEPT,
) -> dict | list | None:
    """
    Makes an authenticated GET request to the GitHub REST API.

    Args:
        path (str): API path relative to the base URL (e.g. '/repos/owner/repo').
        params (dict | None): Optional query parameters.
        accept (str): Value for the ``Accept`` header.

    Returns:
        dict | list | None: Parsed JSON body on success, or ``None`` on any
        error (4xx, 5xx, network failure, timeout, or rate limit exceeded).
        Errors are logged to stderr without exposing secret values.
    """
    url = f"{_API_BASE}{path}"
    headers = _build_headers(accept)

    try:
        response = httpx.get(
            url, headers=headers, params=params, timeout=_REQUEST_TIMEOUT, follow_redirects=True
        )
        _check_rate_limit(response)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 202:
            # GitHub returns 202 while computing async statistics (e.g. contributors).
            print(
                f"[tools_github] GitHub is still computing data for {url} (202 Accepted). "
                "Consider retrying in a few seconds.",
                file=sys.stderr,
            )
            return None

        if response.status_code == 204:
            # No content — valid empty response.
            return {}

        if response.status_code == 301:
            print(f"[tools_github] Repository moved permanently: {url}", file=sys.stderr)
            return None

        if response.status_code == 404:
            print(
                f"[tools_github] Resource not found (404): {url}. "
                "The repository may be private, renamed, or deleted.",
                file=sys.stderr,
            )
            return None

        if response.status_code in (403, 429):
            remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
            reset = response.headers.get("X-RateLimit-Reset", "unknown")
            print(
                f"[tools_github] Access denied or rate-limited ({response.status_code}): {url}. "
                f"Remaining quota: {remaining}. Resets at: {reset}.",
                file=sys.stderr,
            )
            return None

        # Any other non-2xx status.
        print(
            f"[tools_github] Unexpected HTTP {response.status_code} for {url}.",
            file=sys.stderr,
        )
        return None

    except httpx.TimeoutException:
        print(f"[tools_github] Request timed out after {_REQUEST_TIMEOUT}s: {url}", file=sys.stderr)
        return None

    except httpx.NetworkError as exc:
        print(f"[tools_github] Network error for {url}: {type(exc).__name__}", file=sys.stderr)
        return None

    except Exception as exc:  # noqa: BLE001
        print(
            f"[tools_github] Unexpected error for {url}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return None


# ---------------------------------------------------------------------------
# Repository metadata tools
# ---------------------------------------------------------------------------


def get_repository_metadata(repo_owner: str, repo_name: str) -> dict:
    """
    Fetches high-level repository metadata from the GitHub REST API.

    Returns a normalised flat dictionary covering identity, popularity,
    activity counters, feature flags, and timestamps. All optional fields
    default to safe zero/None values when absent from the API response.

    Args:
        repo_owner (str): Repository owner login (e.g. ``'google'``).
        repo_name (str): Repository name (e.g. ``'adk-python'``).

    Returns:
        dict: Normalised metadata dictionary, or ``{}`` on failure.
    """
    data = _github_request(f"/repos/{repo_owner}/{repo_name}")
    if not isinstance(data, dict) or not data:
        return {}

    license_info: dict = data.get("license") or {}
    owner_info: dict = data.get("owner") or {}

    return {
        "name":                 data.get("name", repo_name),
        "owner":                owner_info.get("login", repo_owner),
        "full_name":            data.get("full_name", f"{repo_owner}/{repo_name}"),
        "description":          data.get("description"),
        "default_branch":       data.get("default_branch", "main"),
        "homepage":             data.get("homepage") or None,
        "stars":                data.get("stargazers_count", 0),
        "forks":                data.get("forks_count", 0),
        "watchers":             data.get("subscribers_count", data.get("watchers_count", 0)),
        "open_issues_count":    data.get("open_issues_count", 0),
        "topics":               data.get("topics", []),
        "archived":             data.get("archived", False),
        "disabled":             data.get("disabled", False),
        "has_wiki":             data.get("has_wiki", False),
        "has_discussions":      data.get("has_discussions", False),
        "has_projects":         data.get("has_projects", False),
        "has_downloads":        data.get("has_downloads", False),
        "visibility":           data.get("visibility", "public"),
        "size_kb":              data.get("size", 0),
        "created_at":           data.get("created_at"),
        "updated_at":           data.get("updated_at"),
        "pushed_at":            data.get("pushed_at"),
        "license_name":         license_info.get("name") if license_info else None,
        "license_spdx":         license_info.get("spdx_id") if license_info else None,
        "license_key":          license_info.get("key") if license_info else None,
    }


def get_default_branch(repo_owner: str, repo_name: str) -> str:
    """
    Returns the default branch name of the repository.

    This is a convenience wrapper over ``get_repository_metadata`` for
    callers that need only the branch name.

    Args:
        repo_owner (str): Repository owner login.
        repo_name (str): Repository name.

    Returns:
        str: Default branch name (e.g. ``'main'`` or ``'master'``), or
        ``'main'`` on failure.
    """
    data = _github_request(f"/repos/{repo_owner}/{repo_name}")
    if isinstance(data, dict):
        return data.get("default_branch", "main")
    return "main"


def get_repository_topics(repo_owner: str, repo_name: str) -> list[str]:
    """
    Fetches the topic tags applied to the repository.

    Uses the dedicated topics endpoint (which may return different data from
    the topics embedded in the repository metadata response).

    Args:
        repo_owner (str): Repository owner login.
        repo_name (str): Repository name.

    Returns:
        list[str]: Topic names, or ``[]`` on failure / no topics.
    """
    data = _github_request(
        f"/repos/{repo_owner}/{repo_name}/topics",
        accept=_TOPICS_ACCEPT,
    )
    if isinstance(data, dict):
        return data.get("names", [])
    return []


def get_repository_license(repo_owner: str, repo_name: str) -> dict | None:
    """
    Fetches detailed license information for the repository.

    Args:
        repo_owner (str): Repository owner login.
        repo_name (str): Repository name.

    Returns:
        dict | None: License details with keys ``key``, ``name``,
        ``spdx_id``, and ``html_url``, or ``None`` if no license is
        detected or the request fails.
    """
    data = _github_request(f"/repos/{repo_owner}/{repo_name}/license")
    if not isinstance(data, dict):
        return None
    license_info: dict = data.get("license") or {}
    if not license_info:
        return None
    return {
        "key":      license_info.get("key", ""),
        "name":     license_info.get("name", ""),
        "spdx_id":  license_info.get("spdx_id", ""),
        "html_url": license_info.get("html_url"),
    }


def get_repository_languages(repo_owner: str, repo_name: str) -> dict[str, int]:
    """
    Fetches the language breakdown of the repository as reported by GitHub's
    linguist analysis.

    Args:
        repo_owner (str): Repository owner login.
        repo_name (str): Repository name.

    Returns:
        dict[str, int]: Language name → byte count mapping, ordered by byte
        count descending (as returned by the API). ``{}`` on failure.
    """
    data = _github_request(f"/repos/{repo_owner}/{repo_name}/languages")
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if isinstance(v, int)}
    return {}


def get_latest_release(repo_owner: str, repo_name: str) -> dict | None:
    """
    Fetches the most recent published (non-draft, non-pre-release) release.

    Falls back to the latest release of any kind if no stable release exists.

    Args:
        repo_owner (str): Repository owner login.
        repo_name (str): Repository name.

    Returns:
        dict | None: Release fields (``tag_name``, ``name``, ``published_at``,
        ``prerelease``, ``draft``, ``html_url``), or ``None`` if the repository
        has no releases or the request fails.
    """
    data = _github_request(f"/repos/{repo_owner}/{repo_name}/releases/latest")
    if not isinstance(data, dict) or not data:
        return None
    return {
        "tag_name":     data.get("tag_name", ""),
        "name":         data.get("name"),
        "published_at": data.get("published_at"),
        "prerelease":   data.get("prerelease", False),
        "draft":        data.get("draft", False),
        "html_url":     data.get("html_url", ""),
    }


# ---------------------------------------------------------------------------
# Community & activity tools
# ---------------------------------------------------------------------------


def get_open_issues(
    repo_owner: str, repo_name: str, max_count: int = 100
) -> list[dict]:
    """
    Fetches a sample of open issues from the repository.

    Pull requests are automatically excluded — GitHub's issues endpoint
    returns both issues and PRs; this function filters PRs by checking for
    the ``pull_request`` key in each item.

    Args:
        repo_owner (str): Repository owner login.
        repo_name (str): Repository name.
        max_count (int): Maximum number of issues to return (capped at 100).

    Returns:
        list[dict]: Open issue records with keys:
            ``number``, ``title``, ``state``, ``labels``, ``created_at``,
            ``updated_at``, ``comments``, ``user_login``.
    """
    data = _github_request(
        f"/repos/{repo_owner}/{repo_name}/issues",
        params={
            "state":     "open",
            "per_page":  min(max_count, 100),
            "sort":      "created",
            "direction": "desc",
        },
    )
    if not isinstance(data, list):
        return []

    results: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # Exclude pull requests — they appear in the issues feed.
        if item.get("pull_request"):
            continue
        results.append(
            {
                "number":     item.get("number", 0),
                "title":      item.get("title", ""),
                "state":      item.get("state", "open"),
                "labels":     [lbl.get("name", "") for lbl in item.get("labels", [])],
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "comments":   item.get("comments", 0),
                "user_login": (item.get("user") or {}).get("login", ""),
            }
        )
    return results


def get_pull_requests(
    repo_owner: str, repo_name: str, state: str = "open", max_count: int = 50
) -> list[dict]:
    """
    Fetches a sample of pull requests from the repository.

    Args:
        repo_owner (str): Repository owner login.
        repo_name (str): Repository name.
        state (str): PR state filter — ``'open'``, ``'closed'``, or ``'all'``
            (default ``'open'``).
        max_count (int): Maximum number of PRs to return (capped at 100).

    Returns:
        list[dict]: Pull request records with keys:
            ``number``, ``title``, ``state``, ``labels``, ``created_at``,
            ``updated_at``, ``merged_at``, ``draft``, ``user_login``,
            ``head_ref``.
    """
    data = _github_request(
        f"/repos/{repo_owner}/{repo_name}/pulls",
        params={
            "state":     state,
            "per_page":  min(max_count, 100),
            "sort":      "created",
            "direction": "desc",
        },
    )
    if not isinstance(data, list):
        return []

    results: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "number":     item.get("number", 0),
                "title":      item.get("title", ""),
                "state":      item.get("state", "open"),
                "labels":     [lbl.get("name", "") for lbl in item.get("labels", [])],
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "merged_at":  item.get("merged_at"),
                "draft":      item.get("draft", False),
                "user_login": (item.get("user") or {}).get("login", ""),
                "head_ref":   (item.get("head") or {}).get("ref", ""),
            }
        )
    return results


def get_labels(repo_owner: str, repo_name: str) -> list[dict]:
    """
    Fetches all issue and PR labels defined in the repository.

    Args:
        repo_owner (str): Repository owner login.
        repo_name (str): Repository name.

    Returns:
        list[dict]: Label records with keys ``name``, ``color``,
        ``description``. Returns ``[]`` on failure or empty repository.
    """
    data = _github_request(
        f"/repos/{repo_owner}/{repo_name}/labels",
        params={"per_page": 100},
    )
    if not isinstance(data, list):
        return []

    return [
        {
            "name":        item.get("name", ""),
            "color":       item.get("color", ""),
            "description": item.get("description"),
        }
        for item in data
        if isinstance(item, dict)
    ]


def get_recent_commits(
    repo_owner: str, repo_name: str, count: int = 10
) -> list[dict]:
    """
    Fetches the most recent commits to gauge repository activity.

    Args:
        repo_owner (str): Repository owner login.
        repo_name (str): Repository name.
        count (int): Number of commits to fetch (default 10, max 100).

    Returns:
        list[dict]: Commit records with keys ``sha`` (8-char short),
        ``message`` (first line, up to 120 chars), ``author``, ``date``.
    """
    data = _github_request(
        f"/repos/{repo_owner}/{repo_name}/commits",
        params={"per_page": min(count, 100)},
    )
    if not isinstance(data, list):
        return []

    results: list[dict] = []
    for item in data[:count]:
        if not isinstance(item, dict):
            continue
        commit_obj: dict = item.get("commit") or {}
        author_obj: dict = commit_obj.get("author") or {}
        full_message: str = commit_obj.get("message") or ""
        results.append(
            {
                "sha":     (item.get("sha") or "")[:8],
                "message": full_message.split("\n")[0][:120],
                "author":  author_obj.get("name", ""),
                "date":    author_obj.get("date"),
            }
        )
    return results


def get_contributors(
    repo_owner: str, repo_name: str, max_count: int = 50
) -> list[dict]:
    """
    Fetches the top contributors sorted by commit count.

    Note: GitHub may respond with ``202 Accepted`` for repositories whose
    contributor statistics are still being computed. In that case this
    function returns ``[]`` and logs a warning.

    Args:
        repo_owner (str): Repository owner login.
        repo_name (str): Repository name.
        max_count (int): Maximum number of contributors to return (default 50).

    Returns:
        list[dict]: Contributor records with keys ``login``,
        ``contributions`` (commit count), ``html_url``.
    """
    data = _github_request(
        f"/repos/{repo_owner}/{repo_name}/contributors",
        params={"per_page": min(max_count, 100), "anon": "false"},
    )
    if not isinstance(data, list):
        return []

    return [
        {
            "login":         item.get("login", ""),
            "contributions": item.get("contributions", 0),
            "html_url":      item.get("html_url", ""),
        }
        for item in data[:max_count]
        if isinstance(item, dict) and item.get("login")  # exclude anonymous contributors
    ]
