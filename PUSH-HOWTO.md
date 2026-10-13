# How to push BokenJapan staging branches from this box

Plain `git push https://…` fails here with `could not read Username` (no interactive TTY). Use the GitHub CLI credential helper instead.

## Prerequisites
- `gh` installed and logged in (`gh auth status` shows an account with `repo` scope).
- Repo remote is HTTPS, e.g. `origin https://github.com/<org>/<repo>.git`.

## One-time setup (optional)
```bash
gh auth setup-git
```
This registers `gh` as a git credential helper for github.com.

## Push a local branch tip to a staging branch
From the clone or worktree that has the commit:

```bash
# Example: push current HEAD to origin staging/aomori-hokkaido
GIT_TERMINAL_PROMPT=0 git -c credential.helper='!gh auth git-credential' \
  push origin HEAD:staging/aomori-hokkaido
```

Or, if you are already on that branch and the upstream name matches:

```bash
GIT_TERMINAL_PROMPT=0 git -c credential.helper='!gh auth git-credential' \
  push origin staging/aomori-hokkaido
```

## Verify
```bash
git ls-remote origin refs/heads/staging/aomori-hokkaido
git rev-parse HEAD   # should match the remote sha you expect
```

## Rules for this project
- **Staging only** (`staging/aomori-hokkaido`, `staging/iwate`, …). Do **not** push `main` or `gh-pages` unless explicitly ordered.
- If another worker may have pushed the same branch: `git pull --rebase origin <branch>` **before** pushing (with the same `credential.helper` on fetch/pull if needed).
- Never print tokens, `gh` host YAML, or `Authorization` headers into logs or docs.

## Worktrees
Pushes from a linked worktree use the same remotes/credentials as the main clone. After a branch is fully merged/pushed and the worktree is unused, free disk with:

```bash
git -C /path/to/main-clone worktree remove /path/to/wt-<name>
```

Do not remove worktrees that other agents are still using.
