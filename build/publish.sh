#!/usr/bin/env bash
# Publish the generated site (index.html, dashboard-single.html, data/) to the gh-pages branch as ONE commit that
# replaces the previous one, so the repository does not grow with every weekly refresh. GitHub Pages serves gh-pages.
set -euo pipefail
cd "$(dirname "$0")/.."
touch .nojekyll
export GIT_INDEX_FILE="$(mktemp)"; rm -f "$GIT_INDEX_FILE"       # a private, empty index: main's index is untouched
git add -f index.html dashboard-single.html .nojekyll data
tree=$(git write-tree)
commit=$(GIT_AUTHOR_NAME=dashboard-bot GIT_AUTHOR_EMAIL=bot@users.noreply.github.com GIT_COMMITTER_NAME=dashboard-bot GIT_COMMITTER_EMAIL=bot@users.noreply.github.com \
         git commit-tree "$tree" -m "Site build $(date -u +'%F %H:%M UTC') from main $(git rev-parse --short HEAD)")
git push -f origin "$commit:refs/heads/gh-pages"
rm -f "$GIT_INDEX_FILE" .nojekyll
echo "Published $(git rev-parse --short "$commit") to gh-pages"
