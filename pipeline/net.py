"""Fetching and parsing shared by every data source.

One place for the three things every source needs: HTTP with a real timeout and
a retry, DCF parsing (R's metadata format), and a bounded thread pool. Sources
import from here so that "how we talk to the network" is one decision rather
than five slightly different ones.
"""

import concurrent.futures
import re
import sys
import time
import urllib.error
import urllib.request

UA = {"User-Agent": "bioc-website/pipeline (+https://github.com/seandavi/bioc-website)"}

# Default origin for artifacts that only exist in a package repository (tarballs,
# PACKAGES, config.yaml). Since the cutover on 2026-09-28 bioconductor.org itself
# is served from our R2 mirror, so it is the canonical host; the legacy servers
# stay reachable at master.bioconductor.org until they are retired.
MIRROR = "https://bioconductor.org"


class FetchError(Exception):
    pass


def fetch(url, optional=False, retries=2, timeout=120, headers=None):
    """GET a URL as text. Returns None only when optional and it failed."""
    body = fetch_bytes(url, optional=optional, retries=retries, timeout=timeout,
                       headers=headers)
    return None if body is None else body.decode("utf-8", "replace")


def fetch_bytes(url, optional=False, retries=2, timeout=120, headers=None):
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # A 4xx will not fix itself; only retry server-side and transport errors.
            last = e
            if e.code < 500:
                break
        except Exception as e:  # timeouts, DNS, resets
            last = e
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    if optional:
        print(f"  ! optional fetch failed {url}: {last}", file=sys.stderr)
        return None
    raise FetchError(f"{url}: {last}")


def fetch_range(url, nbytes, optional=False, timeout=60):
    """First nbytes of a URL. Servers may ignore Range and send the whole body;
    callers must therefore treat the result as *at least* what they asked for,
    never as exactly it."""
    return fetch_bytes(url, optional=optional, timeout=timeout,
                       headers={"Range": "bytes=0-%d" % (nbytes - 1)})


def parse_dcf(text):
    """R's Debian Control Format -> {package name: {field: value}}.

    Continuation lines are folded into one space, which is what VIEWS does and
    what the rendered pages have always shown.
    """
    recs, cur, key = [], {}, None
    for line in text.splitlines():
        if not line.strip():
            if cur:
                recs.append(cur)
                cur, key = {}, None
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_.@/-]*):\s?(.*)$", line)
        if m:
            key, cur[m.group(1)] = m.group(1), m.group(2)
        elif key:
            cur[key] += " " + line.strip()
    if cur:
        recs.append(cur)
    return {r["Package"]: r for r in recs if "Package" in r}


def split_list(v):
    """A comma-separated DESCRIPTION field -> list, preserving version constraints."""
    return [x.strip() for x in re.split(r",\s*", v) if x.strip()] if v else []


def dep_name(entry):
    """'R (>= 3.6.0)' -> 'R'."""
    return re.split(r"[ (]", str(entry))[0]


def parallel(fn, items, workers=12, label=None):
    """Map fn over items with a bounded pool, in order, reporting progress.

    Failures are returned as None rather than raising: one unreachable tarball
    out of 1,392 must not lose the other 1,391. Callers filter and report.
    """
    out = [None] * len(items)
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn, it): i for i, it in enumerate(items)}
        for fut in concurrent.futures.as_completed(futures):
            i = futures[fut]
            try:
                out[i] = fut.result()
            except Exception as e:
                print(f"  ! {label or 'task'} [{i}] failed: {e}", file=sys.stderr)
            done += 1
            if label and (done % 200 == 0 or done == len(items)):
                print(f"  {label}: {done}/{len(items)}", file=sys.stderr)
    return out
