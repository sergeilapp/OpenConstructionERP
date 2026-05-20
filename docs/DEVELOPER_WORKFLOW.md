# OpenConstructionERP — Developer Workflow Guide

> How we use Git, GitHub, branches, and the roadmap for day-to-day development.

---

## 1. Branch Strategy

### Branch Naming Convention

```
<prefix>/<short-description>
```

| Prefix | Purpose | Example |
|--------|---------|---------|
| `custom/` | Feature branches (custom development) | `custom/webhook-leads-direct-mapping` |
| `scripts/` | Utility/one-off scripts (reference material) | `scripts/tcg-utilities` |
| `docs/` | Documentation updates | `docs/us-cost-db-methodology-update` |
| `fix/` | Hotfixes or bug fixes | `fix/login-session-expiry` |

### Long-lived Branches

| Branch | Purpose |
|--------|---------|
| `main` | Current development state — all features merged in |
| `origin/main` | Upstream (canonical OCE releases) |
| `fork/main` | Your fork on GitHub |

### Short-lived Branches

| Branch | Lifecycle |
|--------|-----------|
| Feature branches | Created → developed → merged into `main` → optionally deleted |
| Scripts branches | Created → committed → pushed → kept for reference (don't delete) |

---

## 2. Feature Branch Workflow

### Creating a Feature Branch

```bash
# Start from clean main
git checkout main
git pull origin main          # sync with upstream
git pull fork main            # sync with your fork

# Create feature branch
git checkout -b custom/feature-name
```

### Developing on a Feature Branch

```bash
# Make changes, commit frequently
git add <files>
git commit -m "feat(scope): description"

# Push to your fork
git push -u fork custom/feature-name
```

### Merging a Feature into Main

```bash
# Switch to main
git checkout main

# Merge with --no-ff to create a merge commit (preserves feature in history)
git merge --no-ff custom/feature-name -m "Merge custom/feature-name — description"

# Push to your fork
git push fork main
```

**Why `--no-ff`?** It creates a visible merge commit so you can:
- See exactly when a feature was integrated
- Revert an entire feature with a single commit revert
- Keep clean, auditable history

### Deleting a Feature Branch (Optional)

```bash
# Delete remote branch (via GitHub PR UI or CLI)
git push fork --delete custom/feature-name

# Delete local branch
git branch -d custom/feature-name
```

> **Note**: Keep `scripts/` branches — they're reference material. Only delete `custom/` branches after merging.

---

## 3. Updating from Upstream Releases

### When Upstream Releases a New Version

```bash
# Fetch latest from upstream
git fetch origin

# Check what's new
git log --oneline origin/main -10

# Update your local main
git checkout main
git merge origin/main --no-edit

# Push to your fork
git push fork main
```

### If You Have Uncommitted Changes

```bash
# Stash your changes
git stash

# Pull upstream
git checkout main
git merge origin/main --no-edit

# Pop your changes back
git stash pop
```

### If There Are Merge Conflicts

```bash
# Git will mark conflicted files
git status

# Edit conflicted files, remove conflict markers (<<<<<<<, =======, >>>>>>>)
# Then mark as resolved and commit
git add <resolved-files>
git merge --continue
```

---

## 4. When to Use Branches vs Issues vs Roadmap

### Roadmap (`ROADMAP.md`)

Use for **high-level planning**:
- "Now" — actively being built this sprint
- "Next" — validated, ready to build
- "Later" — ideas, exploration
- "Done" — shipped (reference only)

### GitHub Issues

Use for **specific, actionable work**:
- Bug reports (`type: bug`)
- Feature requests (`type: feature`)
- Enhancements (`type: enhancement`)
- Tech debt (`type: tech-debt`)

**Workflow**:
1. Create issue → label it (`type: feature`, `status: idea`)
2. When validated → move to `status: accepted`
3. Link issue to roadmap entry
4. Create feature branch → reference issue in commits
5. Close issue when merged

### Feature Branches

Use for **actual code changes**:
- Any code modification → create a branch
- One branch per feature/fix
- Don't commit directly to `main`

### Decision Tree

```
Have an idea?
  └── Open GitHub Discussion or Issue (status: idea)

Idea validated?
  └── Update Issue (status: accepted) + add to ROADMAP.md (Next)

Ready to build?
  └── Create feature branch (custom/feature-name)

Code written and tested?
  └── Merge into main + close Issue + update ROADMAP.md (Done)
```

---

## 5. Testing Before Merging

### Before Every Commit

```bash
# Backend lint
make lint

# Backend format
make format

# Backend typecheck
make typecheck

# Run tests
make test-backend
```

### Before Merging to Main

```bash
# Full test suite
make test

# Verify no merge conflicts
git diff main..custom/feature-name

# Check branch diff
git log --oneline main..custom/feature-name
```

---

## 6. Server Management

### Starting the Server

**Option A: Two terminals (recommended for hot-reload)**

```bash
# Terminal 1 — Backend
make dev-backend

# Terminal 2 — Frontend
make dev-frontend
```

**Option B: Single script (backgrounds both)**

```bash
./start-dev.sh
# Logs: /tmp/ocerp-backend.log, /tmp/ocerp-frontend.log
```

**Option C: Docker infra + local app**

```bash
# Start infrastructure (postgres, redis, minio)
docker compose up -d postgres redis minio

# Then start backend/frontend in separate terminals
make dev-backend
make dev-frontend
```

### Stopping the Server

```bash
# If using start-dev.sh
pkill -f 'uvicorn app.main:create_app'
pkill -f 'vite'

# If using Docker infra
docker compose down
```

### Restarting the Server

```bash
# Kill existing processes
pkill -f 'uvicorn app.main:create_app'
pkill -f 'vite'

# Restart
./start-dev.sh
# OR
make dev-backend   # (in terminal 1)
make dev-frontend  # (in terminal 2)
```

### When to Restart

| Situation | Restart Required? |
|-----------|-------------------|
| Backend code change | No (uvicorn `--reload` auto-restarts) |
| Frontend code change | No (vite HMR auto-updates) |
| New dependency installed | Yes (pip/npm packages need restart) |
| Database migration | Yes (backend needs to reconnect) |
| `.env` or `.env.local` change | Yes (config loaded at startup) |
| Merge conflict resolved in backend | Yes (syntax errors crash the server) |
| Redis container restarted | Yes (sessions cleared) |

### Troubleshooting Login Issues After Restart

1. **Clear browser localStorage** for `localhost:5180` (or use incognito)
2. **Check backend logs**: `tail -f /tmp/ocerp-backend.log`
3. **Verify backend is running**: `curl http://localhost:8000/api/v1/health`
4. **Check demo credentials**: `cat ~/.openestimator/.demo_credentials.json`

Common causes:
- Merge conflict marker left in code → `SyntaxError` on startup
- Redis restarted → all sessions invalidated
- DB migration pending → backend crashes on startup

---

## 7. Resolving Merge Conflicts

### When Conflicts Happen

- Pulling upstream changes into `main`
- Merging feature branches with overlapping changes
- Rebasing onto newer upstream

### Resolution Process

```bash
# 1. See what's conflicted
git status

# 2. Open conflicted files, look for markers:
#    <<<<<<< HEAD
#    (your changes)
#    =======
#    (incoming changes)
#    >>>>>>> branch-name

# 3. Edit to keep what you want, remove ALL markers

# 4. Mark as resolved
git add <resolved-file>

# 5. Complete the merge
git commit    # (or git merge --continue)
```

### Prevention Tips

- Merge upstream into `main` **before** creating feature branches
- Keep feature branches short-lived (merge within days, not weeks)
- Communicate about shared files (e.g., `service.py`, `router.py`)

---

## 8. Git Hygiene

### Commit Message Format

```
<type>(<scope>): <description>
```

| Type | When to Use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change without behavior change |
| `docs` | Documentation only |
| `test` | Adding/updating tests |
| `chore` | Maintenance, config, tooling |
| `perf` | Performance improvement |
| `ci` | CI/CD changes |
| `build` | Build system changes |
| `style` | Formatting, whitespace (no code change) |

### Examples

```
feat(webhook-leads): add direct payload mapping fallback
fix(backend): resolve merge conflict in llm_translator.py
docs(agents): add local dev infrastructure section
chore(dev): add backup/restore scripts
```

### Before Pushing

```bash
# Check what you're about to push
git log --oneline fork/main..HEAD

# Verify working tree is clean
git status

# Run lint and tests
make lint
make test-backend
```

---

## 9. Quick Reference

### Common Commands

```bash
# See all branches
git branch -a

# See what's different between local and remote
git log --oneline main..fork/main
git log --oneline fork/main..main

# See commits not in upstream
git log --oneline main --not origin/main

# Check if working tree is clean
git status

# View uncommitted changes
git diff

# View staged changes
git diff --cached

# Undo last commit (keeps changes unstaged)
git reset HEAD~1

# Discard all uncommitted changes
git checkout -- .

# Stash current changes
git stash

# Apply stashed changes
git stash pop
```

### File Locations

| File | Purpose |
|------|---------|
| `/tmp/ocerp-backend.log` | Backend server logs |
| `/tmp/ocerp-frontend.log` | Frontend dev server logs |
| `~/.openestimator/.demo_credentials.json` | Demo account passwords |
| `.env.local` | Local dev overrides |
| `ROADMAP.md` | Product roadmap |
| `docs/adr/` | Architecture Decision Records |
| `docs/rfc/` | Request for Comments (feature specs) |
