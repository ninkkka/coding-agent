import os
import sys
import argparse
from dotenv import load_dotenv
from code_agent import CodeAgent
from reviewer_agent import ReviewerAgent

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Coding Agent System")
    parser.add_argument("--mode", choices=["code", "review"], required=True)
    parser.add_argument("--issue", type=int, help="Issue number")
    parser.add_argument("--pr", type=int, help="Pull Request number")
    parser.add_argument("--repo", type=str, default=os.getenv("GITHUB_REPOSITORY"))

    args = parser.parse_args()

    required_vars = ["GITHUB_TOKEN", "OPENAI_API_KEY"]
    for var in required_vars:
        if not os.getenv(var):
            print(f"Error: {var} not set")
            sys.exit(1)

    if args.mode == "code":
        if not args.issue:
            print("Error: --issue required for code mode")
            sys.exit(1)

        agent = CodeAgent(
            repo_path=".",
            github_token=os.getenv("GITHUB_TOKEN"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        print(f"Analyzing issue #{args.issue}...")
        analysis = agent.analyze_issue(args.issue)

        print("Implementing changes...")
        if agent.implement_changes(analysis["analysis"]):
            print("Creating Pull Request...")
            pr = agent.create_pull_request(args.issue)
            if pr:
                print(f"PR created: {pr.html_url}")
            else:
                print("Failed to create PR")
        else:
            print("Failed to implement changes")

    elif args.mode == "review":
        if not args.pr:
            print("Error: --pr required for review mode")
            sys.exit(1)

        reviewer = ReviewerAgent(
            github_token=os.getenv("GITHUB_TOKEN"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

        print(f"Reviewing PR #{args.pr}...")
        result = reviewer.review_pull_request(args.repo, args.pr)

        print(f"Review completed. Needs changes: {result['needs_changes']}")


if __name__ == "__main__":
    main()
