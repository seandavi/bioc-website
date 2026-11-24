#!/usr/bin/env bash
#
# Refresh the package data (data/<release>/) in the CI data snapshot for every
# version in it, then rebuild the site (both builders). Run daily by
# ops/systemd/bioc-site-packages.timer; safe to run by hand.
#
#   ops/refresh-packages.sh             # refresh, check, upload, rebuild
#   DRY_RUN=1 ops/refresh-packages.sh   # everything but the upload and dispatch
#   ADD_RELEASE=3.25 ops/refresh-packages.sh   # also build a release not in it yet
#
# The live releases are the data/<release> directories already in the
# snapshot. ADD_RELEASE adds one (the next devel, ahead of release day); from
# then on it is in the snapshot and every run refreshes it. Which of them are
# release and devel is config.yaml's call, not this script's. Retiring one is
# still done by hand.
# data/site and public are carried over untouched (ops/refresh-content.sh
# owns them). `since` and `releases` need every release from 2.5 on disk, so
# the frozen history (2.5-3.22) is extracted once from site-data-full into
# $WORK/history and linked in beside the live releases.
#
# pipeline/refresh_check.py gates the upload: a drop of more than 2% in any
# release/repository, or a record without since, DownloadRank or releases
# (an ADD_RELEASE version included), fails the run with nothing uploaded. So does any pipeline failure.
#
# Every snapshot this replaces is kept under $WORK/snapshots, so any build
# can be traced back to the exact data it was built from.
set -euo pipefail

SNAPSHOT=r2:bioc-site/_ci/site-data.tar.zst
FULL=r2:bioc-site/_ci/site-data-full.tar.zst
WORK=${WORK:-/data/davsean/bioc-site-refresh}
KEEP_DAYS=${KEEP_DAYS:-90}
cd "$(dirname "$0")/.."

mkdir -p "$WORK/snapshots"
# Shared with refresh-content.sh: both download, modify and upload the same
# snapshot, so neither may read it while the other has yet to upload.
exec 9>"$WORK/snapshot.lock"
flock -w 1800 9 || { echo "snapshot still locked after 30 min; giving up" >&2; exit 1; }

run=$WORK/packages
rm -rf "$run" && mkdir -p "$run/new"
ts=$(date -u +%Y%m%dT%H%M%SZ)
prev=$WORK/snapshots/site-data.$ts.packages.prev.tar.zst
rclone copyto "$SNAPSHOT" "$prev"
zstd -dcq "$prev" | tar -C "$run/new" -xf -
live=$(cd "$run/new" && ls -d data/[0-9]* | sort -V)
if [[ -n ${ADD_RELEASE:-} ]]; then
  [[ $ADD_RELEASE =~ ^[0-9]+\.[0-9]+$ ]] || { echo "ADD_RELEASE=$ADD_RELEASE is not a version" >&2; exit 1; }
  [[ ! -e $run/new/data/$ADD_RELEASE ]] || { echo "data/$ADD_RELEASE is already in the snapshot" >&2; exit 1; }
fi
cp -a "$run/new/data" "$run/old"

hist=$WORK/history
if [[ ! -d $hist ]]; then
  rm -rf "$hist.tmp" && mkdir "$hist.tmp"
  rclone cat "$FULL" | zstd -dcq | tar -C "$hist.tmp" -xf - --wildcards 'data/[0-9]*'
  # site-data-full also holds the live releases as of its upload; drop them.
  for d in $live; do rm -rf "${hist:?}.tmp/$d"; done
  mv "$hist.tmp/data" "$hist" && rmdir "$hist.tmp"
fi
# ln fails, aborting the run, if a history release is also live.
ln -s "$hist"/* "$run/new/data/"

# The added release first, so the live ones' `releases` lists include it; then
# in version order, since a release's `releases` lists read the others on disk.
if [[ -n ${ADD_RELEASE:-} ]]; then
  ./bioc.py packages --bioc "$ADD_RELEASE" --out "$run/new/data"
  ./bioc.py tree --bioc "$ADD_RELEASE" --out "$run/new/data"
  live=$(printf '%s\n' $live "data/$ADD_RELEASE" | sort -V)
fi
for d in $live; do
  [[ $d == "data/${ADD_RELEASE:-}" ]] && continue
  ./bioc.py packages --bioc "${d#data/}" --out "$run/new/data"
  ./bioc.py tree --bioc "${d#data/}" --out "$run/new/data"
done
python3 -m pipeline.refresh_check "$run/old" "$run/new/data"

new=$WORK/snapshots/site-data.$ts.packages${DRY_RUN:+.dry-run}.tar.zst
tar -C "$run/new" -cf - data/site $live public | zstd -T0 -8 -q > "$new"
if [[ -n ${DRY_RUN:-} ]]; then
  echo "DRY_RUN: built $new; not uploaded, no build dispatched"
else
  rclone copyto "$new" "$SNAPSHOT"
  # Both builders rebuild on the new snapshot; whichever has PUBLISH_LATEST
  # on serves production (seandavi/bioc-website#84).
  gh workflow run site.yml -R seandavi/bioc-website --ref main
  gh workflow run astro.yml -R seandavi/bioconductor.org --ref astro
  echo "snapshot $new uploaded; site builds dispatched"
fi

find "$WORK/snapshots" -name 'site-data.*.tar.zst' -mtime +"$KEEP_DAYS" -delete
