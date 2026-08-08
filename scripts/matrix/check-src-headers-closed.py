#!/usr/bin/env python3
"""Verify a packaged src-headers tree is closed under #include.

package-src-headers.sh ships only the subtrees embedders actually reach, not
all of V8's src/. That is only safe if nothing shipped includes something left
out -- otherwise the gap shows up as a confusing compile error in a consumer's
build long after the release is cut. This walks every shipped header and
reports includes that resolve into the *full* checkout but not into the
package.

Usage: check-src-headers-closed.py <dist-dir> <v8-dir>
Exits non-zero and lists the offenders if the package is not closed.
"""
import os
import re
import sys

INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', re.M)

# Include roots, mirroring how consumers configure their compiler: the V8
# checkout root, its public include/, and Abseil's own root.
def roots(base):
    return [base, os.path.join(base, 'include'),
            os.path.join(base, 'third_party/abseil-cpp')]


def resolve(inc, from_dir, base):
    cands = [os.path.join(from_dir, inc)] if from_dir else []
    cands += [os.path.join(r, inc) for r in roots(base)]
    for c in cands:
        c = os.path.normpath(c)
        if c.startswith(base) and os.path.isfile(c):
            return os.path.relpath(c, base)
    return None


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    dist, v8 = (os.path.abspath(p) for p in sys.argv[1:3])

    shipped = set()
    for dirpath, _, files in os.walk(dist):
        for f in files:
            shipped.add(os.path.relpath(os.path.join(dirpath, f), dist))

    missing = {}
    for rel in sorted(shipped):
        if not rel.endswith(('.h', '.inc')):
            continue
        path = os.path.join(dist, rel)
        try:
            text = open(path, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for inc in INCLUDE_RE.findall(text):
            # Resolve against the full checkout: an include that does not
            # resolve there either is a system/public header, not our problem.
            target = resolve(inc, os.path.dirname(path).replace(dist, v8), v8)
            if target is None or target in shipped:
                continue
            # include/ is V8's public API and ships in every slice already.
            if target.startswith('include/'):
                continue
            missing.setdefault(target, []).append(rel)

    if missing:
        print(f"error: package is not closed under #include "
              f"({len(missing)} missing headers)", file=sys.stderr)
        for target, needed_by in sorted(missing.items())[:40]:
            print(f"  {target}  <- {needed_by[0]}"
                  f"{f' (+{len(needed_by)-1} more)' if len(needed_by) > 1 else ''}",
                  file=sys.stderr)
        if len(missing) > 40:
            print(f"  ... and {len(missing) - 40} more", file=sys.stderr)
        print("\nAdd the containing subtree to package-src-headers.sh.",
              file=sys.stderr)
        return 1

    print(f"package is closed under #include ({len(shipped)} files)")
    return 0


if __name__ == '__main__':
    sys.exit(main())
