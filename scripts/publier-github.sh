#!/usr/bin/env bash
# Publish a snapshot of this repository to the public GitHub repository, which GitHub Pages serves.
#
# The local history stays private: it names the pilot family and carries a personal address.
# The public repository has its own history, kept on the local branch `public` and built in a
# separate worktree (data/build/publication, git-ignored) from the current working tree:
#   - every file git would commit (tracked + untracked, minus .gitignore), except .scratch/;
#   - plus site/data/: GitHub Pages serves only what is in the repository.
# Before committing, it runs the tests, the site verifier (privacy and Filae clause) and gitleaks
# over the snapshot. It commits with the GitHub no-reply identity, then pushes `public` to `main`
# of the remote `public`, and nothing else: a pre-push hook it installs refuses any other branch.
#
# Usage:
#   scripts/publier-github.sh                # check, commit the snapshot, push it
#   scripts/publier-github.sh --simulation   # check and show what would change; no commit, no push
#
# Exit codes: 0 published (or nothing to publish); 1 a check failed; 2 bad usage.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
W="$ROOT/data/build/publication"
BRANCH=public
REMOTE=public
NAME="Grinbel"
EMAIL="51087413+Grinbel@users.noreply.github.com"
SIMULATION=0

case "${1:-}" in
  "") ;;
  --simulation) SIMULATION=1 ;;
  -h|--aide) sed -n '2,19p' "$0"; exit 0 ;;
  *) echo "Option inconnue : $1 (voir --aide)" >&2; exit 2 ;;
esac

dire() { printf '%s\n' "$*"; }
echec() { printf 'ÉCHEC : %s\n' "$*" >&2; exit 1; }

cd "$ROOT"

dire "== Garde : seule la branche « $BRANCH » peut quitter cette machine"
HOOK="$(git rev-parse --git-common-dir)/hooks/pre-push"
cat > "$HOOK" <<'HOOK_EOF'
#!/bin/sh
# Installed by scripts/publier-github.sh: only the branch `public` may leave this machine.
# The local history (main and the research branches) stays private.
while read -r local_ref _local_sha _remote_ref _remote_sha; do
  case "$local_ref" in
    refs/heads/public|"(delete)") ;;
    *) echo "pre-push : refusé — seule la branche « public » peut être poussée, pas $local_ref" >&2; exit 1 ;;
  esac
done
HOOK_EOF
chmod +x "$HOOK"

dire "== Tests et vérification, sur cette machine"
# outputs are captured first: with pipefail, an early-exiting grep -q could fail the pipeline
py_out="$(python3 -m unittest discover -s tests -t . -q 2>&1 || true)"
grep -qE '^OK' <<< "$(tail -1 <<< "$py_out")" || echec "tests Python"
node_out="$(node --test tests/js/ 2>&1 || true)"
grep -qE '^# fail 0$' <<< "$node_out" || echec "tests Node"
python3 -m decretas verifier > /dev/null || echec "python3 -m decretas verifier (le relancer pour lire le détail)"

dire "== Copie publique dans $W"
if [ ! -e "$W/.git" ]; then
  if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git worktree add "$W" "$BRANCH" > /dev/null
  else
    git worktree add --orphan -b "$BRANCH" "$W" > /dev/null
  fi
fi
find "$W" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
git ls-files -co --exclude-standard -z | grep -zv '^\.scratch/' | xargs -0 cp --parents -t "$W"
cp -r --parents site/data "$W"
# in the public copy, the name index is tracked: drop its ignore rule
sed -i '/^# Generated site data/,/^\/site\/data\/$/d' "$W/.gitignore"

dire "== Contrôles sur la copie publique (comme GitHub Actions)"
py_out="$(cd "$W" && python3 -m unittest discover -s tests -t . -q 2>&1 || true)"
grep -qE '^OK' <<< "$(tail -1 <<< "$py_out")" || echec "tests Python dans la copie publique"
( cd "$W" && python3 -m decretas verifier --sans-base > /dev/null ) || echec "vérification dans la copie publique"
( cd "$W" && gitleaks dir . --redact --no-banner --log-level warn ) || echec "gitleaks a trouvé un secret possible dans la copie publique"

git -C "$W" add -A
if git -C "$W" diff --cached --quiet; then
  dire "Rien à publier : la copie publique est identique au dernier envoi."
  exit 0
fi
git -C "$W" diff --cached --stat | tail -1
if [ "$SIMULATION" = 1 ]; then
  git -C "$W" reset -q
  dire "Simulation : rien n'est commité ni envoyé."
  exit 0
fi

MESSAGE="Publish a snapshot of the decree search site

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
if git -C "$W" rev-parse --verify --quiet HEAD > /dev/null; then
  git -C "$W" -c user.name="$NAME" -c user.email="$EMAIL" commit -q -m "$MESSAGE"
else
  git -C "$W" -c user.name="$NAME" -c user.email="$EMAIL" commit -q -m "Publish the decree search site

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
fi
dire "== Envoi : $BRANCH → $REMOTE/main"
git push "$REMOTE" "$BRANCH:main"
dire "Publié. GitHub Actions construit le site : gh run list --repo Grinbel/decretas"
