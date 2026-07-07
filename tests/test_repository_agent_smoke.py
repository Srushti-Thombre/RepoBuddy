"""Integration smoke test — run RepositoryAgent against RepoBuddy itself."""
import sys
from agents.repository_agent import RepositoryAgent

agent = RepositoryAgent()
ctx = agent.analyze_repository(".")
d = ctx.model_dump()

print("--- RepositoryContext ---")
print("primary_language :", d["primary_language"])
print("frameworks       :", d["frameworks"])
print("package_managers :", [pm["name"] for pm in d["package_managers"]])
print("build_systems    :", [bs["name"] for bs in d["build_systems"]])
print("entry_points     :", [(ep["path"], ep["entry_type"]) for ep in d["entry_points"]])
print("has_tests        :", d["has_tests"])
print("test_framework   :", d["test_framework"])
print("test_paths       :", d["test_paths"])
print("readme           :", d["documentation"]["readme_path"])
print("docs_dir         :", d["documentation"]["docs_dir"])
print("tree nodes       :", len(d["repo_tree"]))
c = d["complexity"]
print("complexity       :", f"score={c['score']} level={c['level']} files={c['files']} lines={c['lines']} depth={c['max_depth']} langs={c['languages']}")
print("reading_order    :", d["recommended_reading_order"])
print("languages        :", list(d["languages"].keys()))
print("--- PASS ---")
