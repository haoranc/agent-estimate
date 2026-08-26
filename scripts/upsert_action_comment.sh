#!/usr/bin/env bash
set -euo pipefail

kind="${1:?usage: upsert_action_comment.sh <issue|pr> <number> <owner/repo>}"
number="${2:?usage: upsert_action_comment.sh <issue|pr> <number> <owner/repo>}"
repo="${3:?usage: upsert_action_comment.sh <issue|pr> <number> <owner/repo>}"

if [ "$kind" != "issue" ] && [ "$kind" != "pr" ]; then
  printf 'comment kind must be issue or pr, got: %s\n' "$kind" >&2
  exit 2
fi
if ! [[ "$number" =~ ^[0-9]+$ ]]; then
  printf 'comment number must be numeric, got: %s\n' "$number" >&2
  exit 2
fi
if ! [[ "$repo" =~ ^[^/]+/[^/]+$ ]]; then
  printf 'repo must be owner/name, got: %s\n' "$repo" >&2
  exit 2
fi

marker='<!-- agent-estimate:forecast -->'
report="$(cat)"
body="$(printf '%s\n\n%s' "$marker" "$report")"

comment_id="$(
  gh api --paginate "repos/${repo}/issues/${number}/comments?per_page=100" \
    --jq '.[] | select(.user.type == "Bot" and ((.body // "") | startswith("<!-- agent-estimate:forecast -->"))) | .id' \
    | tail -n 1
)"

if [[ "$comment_id" =~ ^[0-9]+$ ]]; then
  gh api --method PATCH "repos/${repo}/issues/comments/${comment_id}" \
    --raw-field "body=${body}"
else
  gh "$kind" comment "$number" --repo "$repo" --body "$body"
fi
