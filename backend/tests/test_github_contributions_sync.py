import pytest
from app.services.github_contributions_service import clean_github_username, fetch_github_contributions


def test_clean_github_username():
    assert clean_github_username("https://github.com/octocat") == "octocat"
    assert clean_github_username("https://github.com/octocat/") == "octocat"
    assert clean_github_username("github.com/torvalds") == "torvalds"
    assert clean_github_username("@torvalds") == "torvalds"
    assert clean_github_username("  kartikay1725  ") == "kartikay1725"
    assert clean_github_username("") is None
    assert clean_github_username(None) is None


def test_fetch_github_contributions_live():
    res, ok = fetch_github_contributions("kartikay1725")
    assert ok is True
    assert len(res) > 0
    assert sum(res.values()) > 0
    # Date format YYYY-MM-DD
    first_date = next(iter(res.keys()))
    assert len(first_date) == 10
    assert first_date[4] == "-" and first_date[7] == "-"
