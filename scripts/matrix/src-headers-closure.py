#!/usr/bin/env python3
"""Compute the transitive #include closure of a set of V8 internal headers.

Prints one checkout-relative path per line, for package-src-headers.sh to feed
to tar. Public headers under include/ are excluded: every release slice already
ships those.

Every #include is followed regardless of the surrounding #if, so the result is
a superset of what any single build configuration compiles -- the safe
direction. Headers that do not resolve inside the checkout (system headers,
<v8-*.h> from include/) are skipped.

Usage: src-headers-closure.py <v8-dir> <entry-point>...
"""
import os
import re
import sys

INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    base = os.path.abspath(sys.argv[1])
    entries = sys.argv[2:]

    # Mirrors how consumers configure their compiler.
    search = [base, os.path.join(base, 'include'),
              os.path.join(base, 'third_party/abseil-cpp')]

    def resolve(inc, from_dir):
        cands = ([os.path.join(from_dir, inc)] if from_dir else []) + \
                [os.path.join(r, inc) for r in search]
        for c in cands:
            c = os.path.normpath(c)
            if c.startswith(base) and os.path.isfile(c):
                return os.path.relpath(c, base)
        return None

    seen, queue = set(), []
    for e in entries:
        rel = resolve(e, None)
        if rel is None:
            print(f"error: entry point not found in {base}: {e}", file=sys.stderr)
            return 1
        if rel not in seen:
            seen.add(rel)
            queue.append(rel)

    while queue:
        rel = queue.pop()
        path = os.path.join(base, rel)
        try:
            text = open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for inc in INCLUDE_RE.findall(text):
            target = resolve(inc, os.path.dirname(path))
            if target is None or target in seen:
                continue
            seen.add(target)
            queue.append(target)

    for rel in sorted(seen):
        # include/ ships with every slice already.
        if not rel.startswith('include/'):
            print(rel)
    return 0


if __name__ == '__main__':
    sys.exit(main())
