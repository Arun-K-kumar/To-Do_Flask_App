#!/usr/bin/env python3
"""Supervisor + Aider loop.

Usage:
  python agent003.py "build X" --test-cmd "pytest -x -q"
"""
import argparse, json, os, re, subprocess, sys, time
import requests

OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
LOG_FILE = ".agent_log.jsonl"

SUPERVISOR_SYS = """You are a strict project supervisor reviewing a coder's work.
You get: the project goal, the instructions already tried, the latest git diff, and test/lint output.
Respond with ONLY a JSON object:
{"verdict": "approve" | "continue", "next_instruction": "...", "files": ["path", ...]}
Rules:
- Approve only if the goal is genuinely met AND tests pass. Never approve on failing tests.
- next_instruction must be ONE small, concrete task (not a rewrite of the whole goal).
- Do not repeat an instruction that was already tried; change approach if it didn't work.
- files: the files the coder should edit next (may be empty). Use 'done' as next_instruction when approving."""

SUPERVISOR_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "continue"]},
        "next_instruction": {"type": "string"},
        "files": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "next_instruction"],
}

CODER_GUARDRAILS = """IMPORTANT CONSTRAINTS - follow on every change:
- Do NOT run `pip install .` or install packages globally.
- Make the smallest change that completes the task below.
- Do not delete or rewrite existing tests to make them pass.
- Do not touch .env or any secrets file.

TASK:
"""


# ---------- helpers ----------
def run(cmd, cwd, timeout=None, shell=False):
    """Run a command, never raise, always return (returncode, combined_output)."""
    try:
        p = subprocess.run(
            cmd, cwd=cwd, shell=shell, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"(timed out after {timeout}s)"
    except FileNotFoundError as e:
        return 127, f"(command not found: {e})"


def git(cwd, *args):
    return run(["git", *args], cwd)


def log(cwd, **event):
    event["ts"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(cwd, LOG_FILE), "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def ensure_gitignore(cwd):
    path = os.path.join(cwd, ".gitignore")
    needed = [".env", ".aider*", LOG_FILE]
    existing = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()
    have = {l.strip() for l in existing.splitlines()}
    missing = [n for n in needed if n not in have]
    if missing:
        with open(path, "a", encoding="utf-8") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")  # avoid gluing onto the last line
            f.write("\n".join(missing) + "\n")


def prepare_repo(cwd, use_branch):
    """Make sure we're in a git repo, on a scratch branch, with a clean baseline commit."""
    code, _ = git(cwd, "rev-parse", "--is-inside-work-tree")
    if code != 0:
        print("Not a git repo - running git init.")
        git(cwd, "init")
    ensure_gitignore(cwd)
    if use_branch:
        branch = "agent/" + time.strftime("%Y%m%d-%H%M%S")
        git(cwd, "checkout", "-b", branch)
        print(f"Working on branch {branch} (your original branch is untouched).")
    # Baseline commit so round 1's diff only contains the coder's work
    # (and so HEAD exists even in a brand-new repo).
    git(cwd, "add", "-A")
    git(cwd, "commit", "--allow-empty", "-m", "agent baseline")


def commit_round(cwd, n):
    """Commit and return the patch, or None if nothing changed."""
    _, status = git(cwd, "status", "--porcelain")
    if not status.strip():
        return None
    git(cwd, "add", "-A")
    code, out = git(cwd, "commit", "-m", f"agent round {n}")
    if code != 0:
        print(f"  git commit failed:\n{out}")
        return None
    _, stat = git(cwd, "show", "HEAD", "--format=", "--stat")
    _, patch = git(cwd, "show", "HEAD", "--format=", "--patch")
    return stat, patch


def rollback_last_round(cwd):
    git(cwd, "reset", "--hard", "HEAD~1")


# ---------- coder ----------
def run_aider(cwd, model, instruction, files):
    cmd = [
        "aider", "--model", model.strip(),   # .strip(): a stray space breaks the model name
        "--edit-format", "diff",
        "--yes-always", "--no-auto-commits", "--no-check-update",
        "--message", CODER_GUARDRAILS + instruction,
    ]
    cmd += files or []
    try:
        code = subprocess.run(cmd, cwd=cwd).returncode  # no check=True: don't crash the loop
    except FileNotFoundError:
        sys.exit("aider not found on PATH. Install it or activate its venv.")
    if code != 0:
        print(f"  aider exited with code {code}")
    return code


# ---------- verification ----------
def run_tests(cwd, test_cmd, timeout=300):
    if not test_cmd:
        return None, "(no test command configured)"
    code, out = run(test_cmd, cwd, timeout=timeout, shell=True)
    return code == 0, out[-3000:]  # tail is where the failures are


# ---------- supervisor ----------
def extract_json(raw):
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)  # reasoning models
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", raw, re.DOTALL)
        if brace:
            raw = brace.group(0)
    return json.loads(raw)


def call_supervisor(model, goal, history, stat, patch, tests_ok, test_out, retries=5, max_diff=8000):
    tried = "\n".join(f"{i+1}. {h}" for i, h in enumerate(history)) or "(none)"
    prompt = (
        f"Project goal: {goal}\n\n"
        f"Instructions tried so far:\n{tried}\n\n"
        f"Tests passing: {tests_ok}\nTest output (tail):\n{test_out}\n\n"
        f"Diffstat:\n{stat}\n\nLatest diff (may be truncated):\n{patch[:max_diff]}"
    )
    for attempt in range(1, retries + 1):
        try:
            r = requests.post(OLLAMA, timeout=300, json={
                "model": model,
                "messages": [{"role": "system", "content": SUPERVISOR_SYS},
                             {"role": "user", "content": prompt}],
                "stream": False,
                "format": SUPERVISOR_SCHEMA,          # Ollama enforces valid JSON
                "options": {"temperature": 0.2},
            })
            r.raise_for_status()
            v = extract_json(r.json()["message"]["content"])
            if v.get("verdict") in ("approve", "continue") and v.get("next_instruction"):
                v.setdefault("files", [])
                return v
        except (requests.RequestException, KeyError, json.JSONDecodeError, AttributeError) as e:
            print(f"  supervisor attempt {attempt}/{retries} failed: {type(e).__name__}: {e}")
            time.sleep(min(2 ** attempt, 10))
    return None


# ---------- main loop ----------
def perfect_project(args):
    cwd = os.getcwd()
    prepare_repo(cwd, not args.no_branch)

    goal, instruction, files = args.goal, args.goal, []
    history, no_change_streak = [], 0

    for n in range(1, args.max_rounds + 1):
        print(f"\n=== Round {n}/{args.max_rounds}: {instruction} ===")
        history.append(instruction)
        run_aider(cwd, args.coder, instruction, files)

        result = commit_round(cwd, n)
        if result is None:
            no_change_streak += 1
            log(cwd, round=n, event="no_changes", instruction=instruction)
            if no_change_streak >= 2:
                print("Aider made no changes twice in a row - stopping. Debug manually.")
                return
            instruction = ("Your previous attempt changed nothing. Be concrete: name the file and "
                           "function to edit and make the change. Task: " + instruction)
            continue
        no_change_streak = 0
        stat, patch = result

        tests_ok, test_out = run_tests(cwd, args.test_cmd)
        print(f"  tests: {'PASS' if tests_ok else 'FAIL' if tests_ok is False else 'skipped'}")

        v = call_supervisor(args.supervisor, goal, history, stat, patch, tests_ok, test_out)
        if v is None:
            print("Supervisor unreliable - stopping. Review `git log -p` manually.")
            return
        log(cwd, round=n, instruction=instruction, tests_ok=tests_ok, verdict=v)
        print(f"Supervisor: {v['verdict']} - {v['next_instruction']}")

        if v["verdict"] == "approve":
            if tests_ok is False:  # hard gate: the model doesn't get to overrule the tests
                print("  Approval overridden: tests are failing.")
                instruction = "Fix the failing tests. Output:\n" + test_out
                files = []
                continue
            print("Project approved. Stopping.")
            return

        instruction, files = v["next_instruction"], v["files"]
        if tests_ok is False:
            instruction += "\n\nCurrent test failures:\n" + test_out
        if instruction in history:
            instruction += "\n\nThis was tried before and did not work. Use a different approach."

    print("Hit max rounds without approval - review manually from here.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("goal", nargs="?", help="project goal (prompted if omitted)")
    ap.add_argument("--coder", default="ollama/jackod-aider:latest")
    ap.add_argument("--supervisor", default="qwen3.5:9b")
    ap.add_argument("--test-cmd", default=None, help='e.g. "pytest -x -q" or "npm test"')
    ap.add_argument("--max-rounds", type=int, default=15)
    ap.add_argument("--no-branch", action="store_true", help="commit on the current branch")
    args = ap.parse_args()
    args.goal = args.goal or input("Project goal: ")
    try:
        perfect_project(args)
    except KeyboardInterrupt:
        print("\nInterrupted. Work so far is committed on the agent branch.")