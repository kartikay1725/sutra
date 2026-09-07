import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.repository import GitHubRepositoryProvider


OWNER = "kartikay1725"
REPO = "dam-project"
BRANCH = "master"
PATH = "README.md"


def main():
    auth_service = GitHubAppAuthService(
        app_id=settings.github_app_id,
        private_key_pem=settings.github_private_key_pem,
        base_url=settings.github_api_base_url,
    )

    provider = GitHubRepositoryProvider(
        auth_service=auth_service,
        base_url=settings.github_api_base_url,
    )

    print(f"Testing blame for {OWNER}/{REPO}")
    print(f"Branch: {BRANCH}")
    print(f"File:   {PATH}")
    print()

    ranges = provider.get_file_blame(
        owner=OWNER,
        name=REPO,
        path=PATH,
        ref=BRANCH,
    )

    print(f"Blame ranges returned: {len(ranges)}")
    print("=" * 80)

    for i, item in enumerate(ranges, start=1):
        print(f"Range #{i}")
        print(f"  Lines:       {item['start_line']} - {item['end_line']}")
        print(f"  Commit:      {item['short_commit']}")
        print(f"  Author:      {item['author_name']}")
        print(f"  Email:       {item['author_email']}")
        print(f"  GitHub user: {item['github_login']}")
        print(f"  Subject:     {item['subject']}")
        print(f"  Authored:    {item['authored_at']}")
        print("-" * 80)


if __name__ == "__main__":
    main()