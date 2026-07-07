"""
Integration test for the AI Reasoning Layer (ArchitectureAgent and ContributionAgent).

Run from project root:
    python -m tests.test_reasoning_layer
"""

import sys
from dotenv import load_dotenv

load_dotenv()

from agents.repository_agent import RepositoryAgent
from agents.github_agent import GitHubAgent
from agents.architecture_agent import ArchitectureAgent
from agents.contribution_agent import ContributionAgent


def main():
    print("--- 1. Running Deterministic Analysis ---")
    
    # 1. Local Repository Analysis
    repo_agent = RepositoryAgent()
    repo_ctx = repo_agent.analyze_repository(".")
    
    # 2. GitHub Intelligence
    github_agent = GitHubAgent()
    github_ctx = github_agent.analyze_repository("https://github.com/google/adk-python")
    
    print("\n--- 2. AI Reasoning: Architecture Analysis ---")
    
    arch_agent = ArchitectureAgent()
    arch_analysis = arch_agent.classify_architecture(repo_ctx, github_ctx)
    
    print("\n[Architecture Analysis Results]")
    print(f"Project Type       : {arch_analysis.project_type}")
    print(f"Architecture Style : {arch_analysis.architecture_style}")
    print(f"Primary Framework  : {arch_analysis.primary_framework}")
    print(f"Components         : {len(arch_analysis.major_components)} found")
    print(f"Testing Strategy   : {arch_analysis.testing_strategy}")
    print(f"Improvements       : {len(arch_analysis.potential_improvements)} noted")
    
    print("\n--- 3. AI Reasoning: Contribution Mentorship ---")
    
    contrib_agent = ContributionAgent()
    recommendations = contrib_agent.identify_contributions(repo_ctx, github_ctx, arch_analysis)
    
    print(f"\n[Contribution Recommendations Generated: {len(recommendations)}]")
    
    for i, rec in enumerate(recommendations[:3], 1):
        print(f"\nRecommendation #{i}: {rec.title}")
        print(f"  Category       : {rec.category}")
        print(f"  Difficulty     : {rec.difficulty}")
        print(f"  Duplicate Risk : {rec.duplicate_risk} ({rec.duplicate_risk_reasoning[:100]}...)")
        print(f"  Files          : {rec.suggested_files}")
        print(f"  Why it matters : {rec.why_this_matters}")
        print(f"  Learning steps : {len(rec.learning_path.steps)} steps (Est: {rec.learning_path.estimated_learning_time})")
        print(f"  Advice         : {rec.mentor_advice[0] if rec.mentor_advice else 'None'}")

    print("\n--- PASS ---")


if __name__ == "__main__":
    main()
