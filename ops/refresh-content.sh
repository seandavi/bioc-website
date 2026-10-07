#!/usr/bin/env bash
#
# Refresh the prose and assets in the CI data snapshot from
# Bioconductor/bioconductor.org, then rebuild the site. Run by
# ops/systemd/bioc-site-refresh.timer; safe to run by hand.
#
#   ops/refresh-content.sh            # no-op unless upstream devel moved
#   FORCE=1 ops/refresh-content.sh    # refresh regardless
#
# Only data/site and public are regenerated. data/<release>/ (package data)
# is carried over from the current snapshot untouched: ops/refresh-packages.sh
# refreshes it.
#
# Every snapshot this replaces is kept under $WORK/snapshots, so any build
# can be traced back to the exact data it was built from.
set -euo pipefail

UPSTREAM=https://github.com/Bioconductor/bioconductor.org
SNAPSHOT=r2:bioc-site/_ci/site-data.tar.zst
WORK=${WORK:-/data/davsean/bioc-site-refresh}
KEEP_DAYS=${KEEP_DAYS:-90}
cd "$(dirname "$0")/.."

mkdir -p "$WORK/snapshots"
head=$(git ls-remote "$UPSTREAM" refs/heads/devel | cut -f1)
last=$(cat "$WORK/upstream-head" 2>/dev/null || true)
if [[ -z ${FORCE:-} && $head == "$last" ]]; then
  echo "upstream devel unchanged at $head"
  exit 0
fi
echo "upstream devel ${last:-<none>} -> $head"

# Shared with refresh-packages.sh: both download, modify and upload the same
# snapshot, so neither may read it while the other has yet to upload. That
# run can take a while; upstream-head is not updated, so the next run retries.
exec 9>"$WORK/snapshot.lock"
flock -n 9 || { echo "snapshot locked by another refresh; retrying next run"; exit 0; }

# Start from the snapshot CI builds from, not from whatever is on disk.
git clean -fdxq astro/data astro/public
ts=$(date -u +%Y%m%dT%H%M%SZ)
prev=$WORK/snapshots/site-data.$ts.prev.tar.zst
rclone copyto "$SNAPSHOT" "$prev"
zstd -dcq "$prev" | tar -C astro -xf -
cp astro/data/site/pages.json "$WORK/pages.prev.json"

./bioc.py fetch-site
./bioc.py assets
./bioc.py content
built=$(git -C .cache/bioconductor.org rev-parse HEAD)

# Which pages changed, for the journal. Not a gate: assets can change
# with no page diff, and a rebuild is cheap.
python3 - "$WORK/pages.prev.json" astro/data/site/pages.json <<'EOF'
import json, sys
a, b = ({p["url"]: p for p in json.load(open(f))} for f in sys.argv[1:])
changed = sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))
print("%d page(s) changed%s" % (len(changed), "".join("\n  " + k for k in changed)))
EOF

new=$WORK/snapshots/site-data.$ts.tar.zst
tar -C astro -cf - data/site $(cd astro && ls -d data/[0-9]*) public | zstd -T0 -8 -q > "$new"
rclone copyto "$new" "$SNAPSHOT"
gh workflow run site.yml -R seandavi/bioc-website --ref main
echo "$built" > "$WORK/upstream-head"
echo "snapshot $new uploaded for bioconductor.org@$built; site build dispatched"

find "$WORK/snapshots" -name 'site-data.*.tar.zst' -mtime +"$KEEP_DAYS" -delete
