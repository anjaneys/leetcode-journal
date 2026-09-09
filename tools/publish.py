"""Committing a solve and pushing it to GitHub.

Guards against the two ways this repo can quietly break:

  1. A video larger than GitHub's 100 MB hard limit sneaking into a commit
     because LFS was not initialised in this clone. Once such a blob is in
     history, the push is rejected and cleaning it up means rewriting history.
  2. Silently blowing through the 1 GB free LFS quota. Each push reports the
     running total so it is never a surprise.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import env

GITHUB_HARD_LIMIT_MB = 100


def git(*args, check: bool = True, capture: bool = True):
    result = subprocess.run(
        ["git"] + list(args),
        cwd=str(env.REPO),
        capture_output=capture,
        text=True,
    )
    if check and result.returncode != 0:
        raise SystemExit("error: git {} failed\n{}".format(
            " ".join(args), (result.stderr or result.stdout).strip()))
    return result


def ensure_lfs(log=print) -> None:
    """Install LFS hooks in this repo and confirm the filters are live."""
    result = subprocess.run(["git", "lfs", "install", "--local"],
                            cwd=str(env.REPO), capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            "error: git-lfs is not working in this repo.\n"
            "       " + (result.stderr or result.stdout).strip())
    filt = git("config", "--get", "filter.lfs.clean", check=False).stdout.strip()
    if not filt:
        raise SystemExit("error: LFS clean filter is not configured; videos would "
                         "be committed as raw blobs. Run: git lfs install")


def lfs_usage_mb() -> float:
    """Approximate LFS storage used, by summing the local LFS object store."""
    store = env.REPO / ".git" / "lfs" / "objects"
    if not store.exists():
        return 0.0
    total = sum(p.stat().st_size for p in store.rglob("*") if p.is_file())
    return total / (1024 * 1024)


def oversized_files(paths) -> list:
    """Any staged file above the GitHub hard limit that LFS is NOT handling."""
    bad = []
    for path in paths:
        p = Path(path)
        if not p.exists() or not p.is_file():
            continue
        mb = p.stat().st_size / (1024 * 1024)
        if mb <= GITHUB_HARD_LIMIT_MB:
            continue
        check = git("check-attr", "filter", "--", str(p), check=False).stdout
        if "filter: lfs" not in check:
            bad.append((str(p), mb))
    return bad


def has_remote() -> bool:
    return bool(git("remote", check=False).stdout.strip())


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip() or "main"


def commit_solve(folder: Path, meta: dict, message: str | None = None, log=print) -> bool:
    ensure_lfs(log)

    git("add", "-A", str(folder), "README.md", check=False)
    git("add", "-A", ".gitattributes", ".gitignore", "config.json", check=False)

    staged = [line for line in
              git("diff", "--cached", "--name-only", check=False).stdout.splitlines()
              if line.strip()]
    if not staged:
        log("Nothing new to commit.")
        return False

    bad = oversized_files([env.REPO / s for s in staged])
    if bad:
        listing = "\n".join("  {}  ({:.0f} MB)".format(p, mb) for p, mb in bad)
        raise SystemExit(
            "error: these staged files exceed GitHub's {} MB limit and are not "
            "tracked by LFS:\n{}\n"
            "       Fix .gitattributes, then run: git add --renormalize .".format(
                GITHUB_HARD_LIMIT_MB, listing))

    msg = message or "{} {} - solution, notes, and recording".format(
        meta.get("id", ""), meta.get("title", folder.name))
    git("commit", "-m", msg)
    log("Committed: " + msg)
    return True


def push(log=print) -> None:
    if not has_remote():
        log("No git remote set - commit stays local.")
        log("Run 'lc init-repo' to create and link a GitHub repository.")
        return
    branch = current_branch()
    log("Pushing to origin/{} (uploading LFS objects)...".format(branch))
    result = subprocess.run(["git", "push", "-u", "origin", branch],
                            cwd=str(env.REPO), capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        log("Push failed:")
        for line in output.splitlines()[-12:]:
            log("  " + line)
        if "exceeds" in output or "large" in output.lower():
            log("\n  A file was too large. Check .gitattributes covers it, then:")
            log("    git add --renormalize . && git commit --amend --no-edit")
        return
    for line in output.splitlines()[-4:]:
        if line.strip():
            log("  " + line)
    log("Pushed. LFS store is now ~{:.0f} MB of the 1 GB free tier.".format(
        lfs_usage_mb()))


def init_repo(cfg: dict, name: str, private: bool, log=print) -> str | None:
    """Create the GitHub repo with gh and wire it up as origin."""
    gh = env.which("gh")
    if not gh:
        log("GitHub CLI not found. Create the repo manually, then run:")
        log("  git remote add origin https://github.com/<you>/{}.git".format(name))
        return None

    auth = subprocess.run([gh, "auth", "status"], capture_output=True, text=True)
    if auth.returncode != 0:
        log("You are not signed in to GitHub CLI yet. Run this, then re-run 'lc init-repo':")
        log("  gh auth login")
        return None

    visibility = "--private" if private else "--public"
    result = subprocess.run(
        [gh, "repo", "create", name, visibility, "--source", ".", "--remote", "origin"],
        cwd=str(env.REPO), capture_output=True, text=True,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        log("Could not create the repository:")
        for line in output.splitlines()[-8:]:
            log("  " + line)
        return None

    slug = git("remote", "get-url", "origin", check=False).stdout.strip()
    slug = slug.replace("https://github.com/", "").replace(".git", "").strip()
    cfg.setdefault("github", {})["repo"] = slug
    env.save_config(cfg)
    log("Created https://github.com/{}".format(slug))
    return slug
