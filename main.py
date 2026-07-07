import os
import sys
import argparse
from dotenv import load_dotenv

from agents import OrchestratorAgent

def initialize_directories():
    """
    Ensures that report output directory and other project structures exist.
    """
    os.makedirs("reports", exist_ok=True)
    os.makedirs("prompts", exist_ok=True)
    os.makedirs("agents", exist_ok=True)
    os.makedirs("mcp_server", exist_ok=True)
    print("[INIT] Verified local project directories (reports/, agents/, mcp_server/).")

def main():
    """
    Main entry point for RepoBuddy initialization and orchestration.
    """
    parser = argparse.ArgumentParser(description="RepoBuddy - AI Mentorship for Open Source")
    parser.add_argument(
        "repo_url",
        nargs="?",
        default="https://github.com/google/adk-python",
        help="The GitHub repository URL to analyze (default: https://github.com/google/adk-python)"
    )
    args = parser.parse_args()
    target_repo = args.repo_url

    # 1. Load env variables from .env
    load_dotenv()

    gemini_key = os.getenv("GEMINI_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")

    print("==============================================")
    print("RepoBuddy - Your Personal Open Source Mentor")
    print("==============================================")

    if not gemini_key:
        print("\n[ERROR] GEMINI_API_KEY is missing from .env.", file=sys.stderr)
        print("RepoBuddy requires a Gemini API key to run its reasoning layer.", file=sys.stderr)
        print("Please add it to your .env file and try again.", file=sys.stderr)
        sys.exit(1)
    else:
        print("[INFO] GEMINI_API_KEY detected.")

    if not github_token:
        print("[WARNING] GITHUB_TOKEN is missing from .env.", file=sys.stderr)
        print("Operating in unauthenticated mode (strict 60 requests/hour limit).", file=sys.stderr)
    else:
        print("[INFO] GITHUB_TOKEN detected.")

    # 2. Setup directory tree
    initialize_directories()

    # 3. Instantiate OrchestratorAgent
    print("\n[ORCHESTRATOR] Instantiating OrchestratorAgent...")
    orchestrator = OrchestratorAgent()

    # 4. Trigger Orchestrator mentorship flow
    try:
        results = orchestrator.run_mentorship_flow(repo_url=target_repo, output_dir="reports")
        
        print("\n==============================================")
        print("✓ Orchestration run completed successfully!")
        print("----------------------------------------------")
        print("Deliverables:")
        print(f"1. Project Analysis: {results['project_analysis_path']}")
        print(f"2. Contribution Roadmap: {results['contribution_roadmap_path']}")
        print("==============================================")

    except Exception as e:
        print("\n==============================================", file=sys.stderr)
        print(f"❌ [ERROR] Mentorship flow failed:", file=sys.stderr)
        print(f"   {type(e).__name__}: {e}", file=sys.stderr)
        print("==============================================", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
