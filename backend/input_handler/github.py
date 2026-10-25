# FILE: backend\input_handler\github.py
import re

_GITHUB_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))"
    r"/(?P<repo>[A-Za-z0-9._-]{1,100})"
    r"(?:\.git)?/?(?:\?.*)?$"
)

_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


def validate_github_url(url: str) -> dict:
    if not url or not url.strip():
        return _err("URL is empty.")

    m = _GITHUB_RE.match(url.strip())
    if not m:
        return _err("Not a valid GitHub repo URL. Expected https://github.com/owner/repo")

    owner = m.group("owner")
    repo = m.group("repo")
    if repo.endswith(".git"):
        repo = repo[:-4]

    if not _OWNER_RE.match(owner):
        return _err("Invalid owner name.")
    if not _REPO_RE.match(repo):
        return _err("Invalid repository name.")

    return {
        "valid": True,
        "owner": owner,
        "repo": repo,
        "normalized": f"https://github.com/{owner}/{repo}",
        "error": None,
    }


def _err(msg: str) -> dict:
    return {"valid": False, "owner": None, "repo": None, "normalized": None, "error": msg}