#!/usr/bin/env bash
#
# scrub_check.sh — refuse to publish anything this repository must never contain.
#
# This repository was extracted from a private working repository whose history carries
# AI co-author trailers, an employer-domain author identity, credentials, and personal
# documents. The extraction dropped all of that by starting a fresh history. This script
# is what keeps it dropped.
#
# It scans BOTH the working tree and the full git history (every commit message, every
# author and committer identity, and every blob ever committed), because a secret removed
# from the tip is still published if it is reachable from any commit.
#
# Run it before making the repository public, and again before every push. CI runs it too.
#
#   scripts/scrub_check.sh            scan tree and history
#   scripts/scrub_check.sh --tree     scan the working tree only (faster; used by pre-commit)
#
# Exit status 0 means clean. Any other status means do not publish.

set -uo pipefail

cd "$(dirname "$0")/.." || exit 2

TREE_ONLY=0
[ "${1:-}" = "--tree" ] && TREE_ONLY=1

FAILURES=0

red()  { printf '\033[31m%s\033[0m\n' "$*"; }
green(){ printf '\033[32m%s\033[0m\n' "$*"; }

fail() {
    red "FAIL: $1"
    shift
    printf '%s\n' "$@" | sed 's/^/      /'
    FAILURES=$((FAILURES + 1))
}

# ---------------------------------------------------------------------------
# Patterns that must never appear anywhere.
#
# NOTE ON ALLOWLISTING. The bare words "claude" and "anthropic" DO legitimately appear in
# upstream AMD files -- submission/dcp_optimizer.py carries the upstream help example
# `--model anthropic/claude-sonnet-4`, and upstream MCP documentation mentions the vendor.
# Those are AMD's text, not this project's attribution, and they stay. So this script does
# not grep for the bare vendor names. It greps for ATTRIBUTION, which is the actual concern:
# co-author trailers, generated-by footers, and the noreply address.
# ---------------------------------------------------------------------------

FORBIDDEN='Co-Authored-By:[[:space:]]*Claude|noreply@anthropic\.com|Generated with \[?Claude Code|baykar|PC_9959|sk-or-v1-|sk-ant-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|BEGIN OPENSSH PRIVATE KEY'

# Private infrastructure and personal-document markers. Kept separate so the report says
# which class of problem was found.
PRIVATE='vivado-dev[0-9]?|fpl26contest-key|FPL26CONTEST_TOKEN|OPENROUTER_API_KEY[[:space:]]*=[[:space:]]*[A-Za-z0-9]|passport|visa application|Aufenthalt'

ALLOWED_EMAIL='misteruzbekguy@gmail\.com'

# Identities GitHub itself writes into the history once the repository is hosted there.
# Dependabot opens its update branches under its own account and GitHub signs the resulting
# commits as the committer, so `git log --all` sees both. Neither is ours to scrub, and
# refusing them would only teach the reader to ignore this check. Anything else still fails.
ALLOWED_BOTS='<[0-9]+\+dependabot\[bot\]@users\.noreply\.github\.com>|<noreply@github\.com>'

# ---------------------------------------------------------------------------
# 1. Working tree
# ---------------------------------------------------------------------------

echo "== working tree =="

# This script necessarily contains the patterns it looks for, so it excludes itself from
# both scans. Everything else in the tree is scanned, including untracked files -- without
# --untracked, `git grep` searches only what is already staged and a fresh extraction would
# pass while carrying anything at all.
SELF=':!scripts/scrub_check.sh'

hits=$(git grep --untracked -nIE "$FORBIDDEN" -- . "$SELF" 2>/dev/null)
[ -n "$hits" ] && fail "forbidden attribution / credential pattern in the working tree" "$hits"

hits=$(git grep --untracked -nIE "$PRIVATE" -- . "$SELF" ':!SECURITY.md' 2>/dev/null)
[ -n "$hits" ] && fail "private infrastructure or personal-document marker in the working tree" "$hits"

# A committed .env is the single most common way a key ships by accident.
tracked_env=$(git ls-files | grep -E '(^|/)\.env($|\.)' || true)
[ -n "$tracked_env" ] && fail "a .env file is tracked" "$tracked_env"

# Private keys by filename, independent of content.
tracked_keys=$(git ls-files | grep -E '\.(pem|key|p12|pfx)$' || true)
[ -n "$tracked_keys" ] && fail "a key file is tracked" "$tracked_keys"

# The private working repository's own planning documents must not have come along.
strays=$(git ls-files | grep -EI '^(HANDOFF|WIN_PLAN|ZAMAN_LOG|NOTEBOOK|RUNNING|STRATEJI|DURUM|LESSONS_FROM)' || true)
[ -n "$strays" ] && fail "a private working document was included" "$strays"

[ "$FAILURES" -eq 0 ] && green "  clean"

# ---------------------------------------------------------------------------
# 2. History
# ---------------------------------------------------------------------------

if [ "$TREE_ONLY" -eq 0 ]; then
    echo "== history =="

    # Commit messages, including trailers in the body.
    hits=$(git log --all --format='%H%n%s%n%b' | grep -nEi "$FORBIDDEN" || true)
    [ -n "$hits" ] && fail "forbidden pattern in a commit message" "$hits"

    # Author and committer identities on every commit.
    idents=$(git log --all --format='%an <%ae>%n%cn <%ce>' | sort -u)
    bad_idents=$(printf '%s\n' "$idents" | grep -vE "<$ALLOWED_EMAIL>|$ALLOWED_BOTS" || true)
    if [ -n "$bad_idents" ]; then
        fail "an unexpected author or committer identity is in the history" "$bad_idents" \
             "(expected only <${ALLOWED_EMAIL//\\/}>)"
    fi

    # The content of every commit, not just the tip: a secret deleted at the tip is still
    # published if any commit still reaches it. `git grep` over the full revision list does this
    # in one process; walking blobs individually spawns three git calls each and is slow enough
    # that the check stops being run, which is worse than not having it.
    #
    # This script is excluded by path for the same reason it is excluded from the tree scan: it
    # contains the patterns by definition.
    blob_hits=$(
        git rev-list --all |
        xargs -r git grep -lIE "$FORBIDDEN" -- ':!scripts/scrub_check.sh' 2>/dev/null |
        sort -u
    )
    [ -n "$blob_hits" ] && fail "forbidden pattern inside a committed blob" "$blob_hits"

    [ "$FAILURES" -eq 0 ] && green "  clean"
fi

# ---------------------------------------------------------------------------

echo
if [ "$FAILURES" -eq 0 ]; then
    green "scrub check passed — safe to publish"
    exit 0
fi
red "scrub check failed with $FAILURES problem(s) — DO NOT PUBLISH"
exit 1
