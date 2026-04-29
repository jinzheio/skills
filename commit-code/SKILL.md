---
name: commit-code
description: Review workspace changes, report risks, and create clean scoped commits after user confirmation.
---

# Commit Code Skill

Run a lightweight code review on workspace changes, wait for user confirmation, then split the changes into clean functional commits.

## Step-by-Step Instructions

### Step 1: Analyze Workspace Changes

Run `git status` to list all changed files, including tracked and untracked files.

For every changed file, run `git diff HEAD -- <file>` for tracked files or inspect the full contents for untracked files. Review the complete diff before judging the change.

**Code Review Checklist:**

1. **Logic completeness**: Does the new behavior connect end to end across API, data, and UI boundaries?
2. **Dead code**: Are there unused variables, imports, props, functions, files, or stale branches?
3. **Error handling**: Do async paths handle failures? Are loading or cleanup states released correctly?
4. **Type safety**: Do TypeScript types match the actual data shape?
5. **Security**: Are user inputs validated? Is there any injection, secret exposure, or trust-boundary risk?
6. **Side effects**: Are polling loops, timers, subscriptions, file writes, or network calls controlled and cleaned up?
7. **Breaking changes**: Could the change affect existing APIs, schema, deployment flows, or running agents?

Group findings by severity: high, medium, and low.

### Step 2: Report to the User

Report the review result in this format:

```
## Code Review Summary

### High Risk
- [Issue description]

### Medium Risk
- [Issue description]

### Low Risk / Suggestions
- [Issue description]

### Files With No Issues
- [List files]
```

If no issues are found, say so clearly.

Then ask the user:
**"Do you confirm that I should commit these changes? If anything needs to be fixed first, tell me; otherwise reply with 'confirm commit'."**

WAIT for the user to explicitly reply before proceeding to Step 3.

### Step 3: Plan Commit Groups

After the user confirms, group changed files by function or module:

- Put frontend and backend files for the same feature in the same commit.
- Put standalone runner, shell, or install scripts in their own commit.
- Put pure UI or styling changes in their own commit.
- Put documentation-only changes in their own commit.
- Put schema changes in their own commit because they may trigger migrations.
- Include untracked files in the commit group that owns their functionality.

List the planned commit groups, for example:

```
Commit 1: feat(api): ...
  - src/app/api/...
  - src/app/[locale]/...

Commit 2: feat(runner): ...
  - src/lib/runner/...

Commit 3: docs: ...
  - docs/...
```

### Step 4: Commit Each Group

For each group:

1. Run `git add <file1> <file2> ...` with exact paths. Do not use `git add .`.
2. `git commit -m "<type>(<scope>): <summary>\n\n<bullet points>"`

Use Conventional Commits:

- type: `feat` / `fix` / `refactor` / `docs` / `chore` / `style`
- scope: module name, such as `profile`, `runner`, `api`, or `admin`
- summary: English, under 50 characters, starting with a verb
- body: key changes, with each item starting with `-`

### Step 5: Finish

Run `git log --oneline -<N>` to show the new commits, then report the result to the user.
