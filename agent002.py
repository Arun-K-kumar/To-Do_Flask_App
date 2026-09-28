import subprocess, requests, json, sys, os, re

PROJECT_DIR = os.getcwd()   # or r"C:\Users\arnkm\WorkBench\SRMchan"
CODER_MODEL = "ollama/jackod-aider:latest "
SUPERVISOR_MODEL = "qwen3.5:9b"
OLLAMA = "http://localhost:11434/api/chat"
MAX_ROUNDS = 15
SUPERVISOR_RETRIES = 5

SUPERVISOR_SYS = """You are a strict project supervisor reviewing a coder's changes.
Given the project goal and the git diff of the latest round, respond with ONLY raw JSON, no markdown fences, no explanation, no extra text:
{"verdict": "approve" or "continue", "next_instruction": "specific next task for the coder, or 'done' if approving"}
Approve only when the diff shows the goal is genuinely met — don't approve prematurely."""

CODER_GUARDRAILS = """IMPORTANT CONSTRAINTS — follow these on every change-
- Do NOT  run pip install .
"""


def ensure_gitignore():
    gitignore_path = os.path.join(PROJECT_DIR, ".gitignore")
    needed = [".env", ".aider.chat.history.md", ".aider.input.history", ".aider.tags.cache.v4/"]
    existing = set()
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            existing = set(line.strip() for line in f)
    with open(gitignore_path, "a", encoding="utf-8") as f:
        for entry in needed:
            if entry not in existing:
                f.write(entry + "\n")


def extract_json(raw):
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", raw, re.DOTALL)
        if brace:
            raw = brace.group(0)
    return json.loads(raw)


def call_supervisor(goal, diff):
    prompt = f"Project goal: {goal}\n\nLatest diff:\n{diff[:6000]}"
    last_raw = ""
    for attempt in range(1, SUPERVISOR_RETRIES + 1):
        r = requests.post(OLLAMA, json={
            "model": SUPERVISOR_MODEL,
            "messages": [{"role": "system", "content": SUPERVISOR_SYS},
                         {"role": "user", "content": prompt}],
            "stream": False
        })
        raw = r.json()["message"]["content"]
        last_raw = raw
        try:
            verdict = extract_json(raw)
            if "verdict" in verdict and "next_instruction" in verdict:
                return verdict
        except (json.JSONDecodeError, AttributeError):
            pass
        print(f"  (supervisor gave bad JSON on attempt {attempt}/{SUPERVISOR_RETRIES}, retrying supervisor call...)")

    print(f"  Supervisor failed to return valid JSON after {SUPERVISOR_RETRIES} attempts. Last raw output:\n{last_raw[:500]}")
    return {"verdict": "continue", "next_instruction": "__SUPERVISOR_FAILED__"}


def run_aider(instruction):
    full_instruction = CODER_GUARDRAILS + "\n" + instruction
    subprocess.run([
        "aider", "--model", CODER_MODEL,
        "--edit-format", "diff",
        "--yes-always", "--no-auto-commits",
        "--message", full_instruction
    ], cwd=PROJECT_DIR, check=True)


def has_changes():
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_DIR, capture_output=True, text=True,
        encoding="utf-8", errors="replace"
    )
    return bool(result.stdout.strip())


def git_commit_and_diff(round_num):
    if not has_changes():
        print("  ⚠ No file changes detected after Aider ran this round.")
        return None

    subprocess.run(["git", "add", "-A"], cwd=PROJECT_DIR)
    commit_result = subprocess.run(
        ["git", "commit", "-m", f"round {round_num}"],
        cwd=PROJECT_DIR, capture_output=True, text=True,
        encoding="utf-8", errors="replace"
    )
    if commit_result.returncode != 0:
        print(f"  ⚠ git commit failed:\n{commit_result.stdout}\n{commit_result.stderr}")
        return None

    diff_result = subprocess.run(
        ["git", "diff", "HEAD~1", "HEAD"],
        cwd=PROJECT_DIR, capture_output=True, text=True,
        encoding="utf-8", errors="replace"
    )
    return diff_result.stdout or "(no changes detected)"


def perfect_project(goal):
    ensure_gitignore()
    instruction = goal
    for round_num in range(1, MAX_ROUNDS + 1):
        print(f"\n=== Round {round_num}: Coder working on: {instruction} ===")
        run_aider(instruction)
        diff = git_commit_and_diff(round_num)

        if diff is None:
            print("Stopping — Aider made no changes this round. Run it manually to debug:")
            print(f'  aider --model {CODER_MODEL} --edit-format diff --message "{instruction}"')
            return

        verdict = call_supervisor(goal, diff)
        print(f"Supervisor: {verdict['verdict']} — {verdict['next_instruction']}")

        if verdict["verdict"] == "approve":
            print("Project approved. Stopping.")
            return
        if verdict["next_instruction"] == "__SUPERVISOR_FAILED__":
            print("Stopping run — supervisor is unreliable right now, review the diff manually.")
            return
        instruction = verdict["next_instruction"]

    print("Hit max rounds without approval — review manually from here.")


if __name__ == "__main__":
    goal = sys.argv[1] if len(sys.argv) > 1 else input("Project goal: ")
    perfect_project(goal)