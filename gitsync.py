"""
gitsync.py — minimal git-CLI wrapper powering Weave's two-machine sync feature.

Design constraints (see design spec this was built from):
  - Single user, two machines. Not multi-user collaboration.
  - No bundled git library, no auth/credential handling — we shell out to
    whatever `git` is already installed/configured on the machine (SSH keys,
    credential helpers, etc.) and trust it completely.
  - Never auto-merge graph JSON. A conflict means: stop, tell the user,
    leave the repo in a clean (non-rebasing) state, let them sort it out.

Everything here is UI-agnostic — it returns plain data (GitResult / dicts /
status strings) and never pops a dialog itself. ui.py / main.py decide how
to present results to the user.
"""
import os
import datetime
import subprocess


# ── Low-level git runner ───────────────────────────────────────────────────────
class GitResult:
    """Outcome of a single git subprocess call. Never raises on non-zero exit."""

    def __init__(self, ok, stdout="", stderr="", returncode=0):
        self.ok = ok
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return f"GitResult(ok={self.ok}, returncode={self.returncode})"


def _run(args, cwd=None, timeout=30):
    """Run `git <args>` and capture the result. Never throws.

    stdin is explicitly closed (DEVNULL): if git/ssh would otherwise prompt
    interactively for a password, passphrase, or host-key confirmation, this
    makes it fail immediately with a clear stderr message instead of hanging
    silently until `timeout` expires.
    """
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        return GitResult(proc.returncode == 0, proc.stdout.strip(),
                          proc.stderr.strip(), proc.returncode)
    except FileNotFoundError:
        return GitResult(False, "", "git executable not found — is git installed and on PATH?", -1)
    except subprocess.TimeoutExpired:
        return GitResult(False, "", "git command timed out (network issue?)", -1)
    except Exception as e:
        return GitResult(False, "", str(e), -1)


# ── Inspection helpers ─────────────────────────────────────────────────────────
def is_git_repo(path):
    """True if `path` is (the top of) a git working copy."""
    return bool(path) and os.path.isdir(os.path.join(path, ".git"))


def folder_is_empty(path):
    """Non-existent folder counts as empty (it'll be created by clone/init)."""
    if not os.path.isdir(path):
        return True
    return len(os.listdir(path)) == 0


def current_remote_url(repo_path):
    res = _run(["remote", "get-url", "origin"], cwd=repo_path)
    return res.stdout.strip() if res.ok else None


def remote_has_commits(url, timeout=15):
    """
    Check whether the remote already has at least one ref/commit.
    Returns (has_commits: bool | None, error: str | None).
    None means we couldn't tell (network/auth failure) — treat as a hard
    error upstream rather than guessing.
    """
    res = _run(["ls-remote", "--heads", url], timeout=timeout)
    if not res.ok:
        return None, res.stderr or "Could not reach remote repository."
    return bool(res.stdout.strip()), None


def find_weave_files(folder):
    """List of .weave filenames (not .bweave — that format is untouched by sync)
    directly inside `folder`."""
    if not os.path.isdir(folder):
        return []
    return sorted(f for f in os.listdir(folder) if f.lower().endswith(".weave"))


# ── Link / Init — case detection ───────────────────────────────────────────────
# Returns (case, info) where case is one of:
#   "clone"              - empty/missing local folder, remote has commits
#   "init_new"            - not yet a repo, remote is empty/new
#   "repoint"             - already a repo, but origin points elsewhere (info=old url)
#   "already_linked"      - already a repo, origin already matches (info=url)
#   "conflict_ambiguous"  - non-empty non-repo folder + remote with commits -> refuse
#   "error"               - couldn't determine (info=message)
def detect_link_case(local_path, remote_url):
    if not remote_url:
        return "error", "Remote URL is required."
    if not local_path:
        return "error", "Repo path is required."

    if is_git_repo(local_path):
        existing = current_remote_url(local_path)
        if existing and existing != remote_url:
            return "repoint", existing
        return "already_linked", existing or ""

    has_commits, err = remote_has_commits(remote_url)
    if has_commits is None:
        return "error", f"Could not reach remote to check its state:\n{err}"

    empty = folder_is_empty(local_path)

    if has_commits:
        if empty:
            return "clone", ""
        return "conflict_ambiguous", ""
    else:
        # Remote is empty/new — safe to init locally regardless of whether
        # the folder already has files in it (e.g. an existing .weave file).
        return "init_new", ""


# ── Link / Init — actions ──────────────────────────────────────────────────────
def do_clone(remote_url, local_path, timeout=60):
    os.makedirs(os.path.dirname(os.path.abspath(local_path)) or ".", exist_ok=True)
    if os.path.isdir(local_path) and folder_is_empty(local_path):
        # `git clone` is happy to clone into an existing *empty* directory.
        return _run(["clone", remote_url, local_path], timeout=timeout)
    return _run(["clone", remote_url, local_path], timeout=timeout)


def do_init_new(local_path, remote_url):
    os.makedirs(local_path, exist_ok=True)
    res = _run(["init"], cwd=local_path)
    if not res.ok:
        return res
    return _run(["remote", "add", "origin", remote_url], cwd=local_path)


def do_repoint(local_path, remote_url):
    return _run(["remote", "set-url", "origin", remote_url], cwd=local_path)


def do_first_commit_push(local_path, filenames, timeout=60):
    """Commit + push whatever .weave files already exist locally, right after
    an `init_new` link, so the user isn't left 'linked' with an empty remote."""
    if not filenames:
        return GitResult(True, "", "", 0)
    res = _run(["add"] + filenames, cwd=local_path)
    if not res.ok:
        return res
    res = _run(["commit", "-m", "Initial Weave sync commit"], cwd=local_path)
    if not res.ok and "nothing to commit" not in (res.stdout + res.stderr).lower():
        return res
    branch_res = _run(["branch", "--show-current"], cwd=local_path)
    branch = branch_res.stdout.strip() or "main"
    return _run(["push", "-u", "origin", branch], cwd=local_path, timeout=timeout)


# ── Daily-use sync action ──────────────────────────────────────────────────────
def sync_now(repo_path, filenames, timeout=60):
    """
    add -> commit (only if there are changes) -> pull --rebase -> push.

    Returns dict: {"status": "synced" | "conflict" | "error", "message": str}
    Never attempts to auto-merge graph JSON — on conflict, aborts the rebase
    (so the repo is left clean/usable) and reports back instead of guessing.
    """
    if not is_git_repo(repo_path):
        return {"status": "error",
                "message": "This folder isn't a linked git repo yet.\n"
                            "Use Settings → Sync to link it first."}
    if not filenames:
        return {"status": "error",
                "message": f"No .weave file found in:\n{repo_path}"}

    add_res = _run(["add"] + filenames, cwd=repo_path)
    if not add_res.ok:
        return {"status": "error", "message": f"git add failed:\n{add_res.stderr}"}

    status_res = _run(["status", "--porcelain", "--"] + filenames, cwd=repo_path)
    has_pending_changes = bool(status_res.stdout.strip())

    if has_pending_changes:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Scoped with `--` so this only ever commits the .weave file(s) we
        # just staged — never anything else that happened to be sitting in
        # the index (e.g. a .bweave staged manually outside the app).
        commit_res = _run(["commit", "-m", f"Weave sync — {ts}", "--"] + filenames, cwd=repo_path)
        if not commit_res.ok:
            combined = (commit_res.stdout + commit_res.stderr).lower()
            if "nothing to commit" not in combined:
                return {"status": "error", "message": f"git commit failed:\n{commit_res.stderr}"}

    pull_res = _run(["pull", "--rebase"], cwd=repo_path, timeout=timeout)
    if not pull_res.ok:
        combined = (pull_res.stdout + "\n" + pull_res.stderr).lower()
        if "conflict" in combined or "could not apply" in combined or "unmerged" in combined:
            # Leave the repo in a clean state — never sit mid-rebase, and
            # never attempt to resolve the conflict ourselves.
            _run(["rebase", "--abort"], cwd=repo_path)
            return {"status": "conflict",
                    "message": "Sync conflict — both local and remote have unsaved changes.\n"
                                "Resolve manually, then click Sync again.\n\n"
                                "Your local changes are still committed locally and were not lost.\n\n"
                                f"{pull_res.stderr.strip()}"}
        return {"status": "error", "message": f"git pull failed:\n{pull_res.stderr}"}

    push_res = _run(["push"], cwd=repo_path, timeout=timeout)
    if not push_res.ok:
        return {"status": "error", "message": f"git push failed:\n{push_res.stderr}"}

    return {"status": "synced", "message": "Synced."}