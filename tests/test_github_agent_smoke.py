"""
Integration smoke test — run GitHubAgent against google/adk-python.

Run from project root:
    python -m tests.test_github_agent_smoke
"""
import sys
from dotenv import load_dotenv

load_dotenv()

from agents.github_agent import GitHubAgent

agent = GitHubAgent()
ctx = agent.analyze_repository("https://github.com/google/adk-python")
d = ctx.model_dump()
h = d["repository_health"]

print("--- GitHubContext ---")
print(f"full_name        : {d['full_name']}")
print(f"description      : {(d['description'] or '')[:80]}")
print(f"default_branch   : {d['default_branch']}")
print(f"license          : {d['license']} ({d['license_spdx']})")
print(f"stars            : {d['stars']}")
print(f"forks            : {d['forks']}")
print(f"watchers         : {d['watchers']}")
print(f"open_issue_count : {d['open_issue_count']}")
print(f"topics           : {d['topics']}")
print(f"latest_release   : {d['latest_release']['tag_name'] if d['latest_release'] else 'none'}")
print(f"created_at       : {d['created_at']}")
print(f"pushed_at        : {d['pushed_at']}")
print(f"open_issues      : {len(d['open_issues'])} sampled")
print(f"open_prs         : {len(d['open_pull_requests'])} sampled")
print(f"labels           : {len(d['labels'])} labels")
print(f"contributors     : {len(d['contributors'])} top")
print(f"maintainers      : {d['maintainers']}")
print(f"languages_api    : {list(d['languages_from_api'].keys())}")
print(f"commits          : {len(d['recent_commits'])} recent")
if d['recent_commits']:
    c = d['recent_commits'][0]
    print(f"  latest sha     : {c['sha']} | {c['message'][:60]}")
print("--- Health ---")
print(f"score            : {h['score']} / 100")
print(f"level            : {h['level']}")
print(f"last_commit_age  : {h['last_commit_age_days']} days")
print(f"commit_frequency : {h['commit_frequency']}")
print(f"issue_activity   : {h['issue_activity']}")
print(f"pr_activity      : {h['pull_request_activity']}")
print(f"responsiveness   : {h['maintainer_responsiveness']}")
print(f"archived         : {h['archived']}")
print(f"has_releases     : {h['has_releases']}")
print("--- PASS ---")
