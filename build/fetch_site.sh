#!/usr/bin/env bash
# Bring the currently published data (data/ on the gh-pages branch) into the working tree before a build.
set -euo pipefail
cd "$(dirname "$0")/.."
if git fetch -q --depth=1 origin gh-pages; then
  rm -rf data && git --work-tree=. checkout FETCH_HEAD -- data && git reset -q -- data 2>/dev/null || true
  echo "data/ restored from gh-pages ($(ls data | wc -l) files)"
else
  echo "no gh-pages branch yet - using data/ from main"
fi
