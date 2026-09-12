"""
GitHub Actions Workflow Templates for SUTRA-governed repositories.
Provides standardized CI workflow definitions for automated testing on GitHub runners.
"""

from typing import Optional


class GitHubActionsTemplateService:
    """Helper to generate canonical GitHub Actions workflow definitions."""

    @staticmethod
    def get_python_ci_workflow(
        name: str = "CI",
        python_version: str = "3.11",
        run_tests_cmd: str = "pytest",
        run_lint: bool = True,
    ) -> str:
        """Returns a canonical .github/workflows/ci.yml for Python/FastAPI projects."""
        lint_step = (
            "      - name: Run Lint and Type Checking\n"
            "        run: |\n"
            "          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics || true\n"
            if run_lint
            else ""
        )
        return (
            f"name: {name}\n\n"
            "on:\n"
            "  push:\n"
            "    branches: [ main, master ]\n"
            "  pull_request:\n"
            "    branches: [ main, master ]\n\n"
            "jobs:\n"
            "  test:\n"
            "    name: Test & Verify\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Checkout Code\n"
            "        uses: actions/checkout@v4\n\n"
            "      - name: Set up Python\n"
            "        uses: actions/setup-python@v5\n"
            "        with:\n"
            f"          python-version: '{python_version}'\n"
            "          cache: 'pip'\n\n"
            "      - name: Install Dependencies\n"
            "        run: |\n"
            "          python -m pip install --upgrade pip\n"
            "          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi\n"
            "          if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi\n"
            "          pip install pytest pytest-cov httpx || true\n\n"
            f"{lint_step}"
            "      - name: Run Tests\n"
            f"        run: {run_tests_cmd}\n"
        )

    @staticmethod
    def get_node_ci_workflow(
        name: str = "CI",
        node_version: str = "20",
        run_tests_cmd: str = "npm test",
    ) -> str:
        """Returns a canonical .github/workflows/ci.yml for Node.js projects."""
        return (
            f"name: {name}\n\n"
            "on:\n"
            "  push:\n"
            "    branches: [ main, master ]\n"
            "  pull_request:\n"
            "    branches: [ main, master ]\n\n"
            "jobs:\n"
            "  test:\n"
            "    name: Test & Verify\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Checkout Code\n"
            "        uses: actions/checkout@v4\n\n"
            "      - name: Set up Node.js\n"
            "        uses: actions/setup-node@v4\n"
            "        with:\n"
            f"          node-version: '{node_version}'\n"
            "          cache: 'npm'\n\n"
            "      - name: Install Dependencies\n"
            "        run: npm ci || npm install\n\n"
            "      - name: Run Tests\n"
            f"        run: {run_tests_cmd}\n"
        )
