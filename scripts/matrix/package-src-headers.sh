#!/bin/bash
set -e
#
# Packages the V8 *internal* headers into dist/src-headers/.
#
# Both runtimes' inspector glue compiles against src/inspector and what it
# transitively pulls in, none of which is public API. Keeping that copy on a
# different V8 than the libraries is an ABI mismatch, so it has to travel with a
# release -- otherwise a consumer still needs a full V8 checkout to produce it,
# which defeats the point of shipping artifacts at all.
#
# Only the transitive #include closure of ENTRY_POINTS is shipped: 66 headers
# rather than the 2223 in src/ + third_party. This used to ship whole subtrees,
# which is the wrong granularity -- a subtree drags in headers no consumer
# includes, and *those* reach further still (src/debug alone pulls in
# src/objects, src/execution, src/parsing...). Shipping src/{base,common,debug,
# inspector} wholesale is not even self-contained: 24 of its headers include
# things outside those four directories.
#
# ENTRY_POINTS are the headers a consumer includes *directly*. Add to this list
# when a consumer starts including a new V8 internal header; the closure takes
# care of everything below it. A consumer that includes something not reachable
# from here gets a hard compile error naming the missing file, never a silent
# misbuild.
#
# Usage: package-src-headers.sh [--v8-dir <path>] --gen-dir <path>
#

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT_DIR/config.env"

V8_DIR="$ROOT_DIR/.v8/v8"
GEN_DIR=""

ENTRY_POINTS=(
    src/inspector/string-util.h
    src/inspector/v8-console-message.h
    src/inspector/v8-inspector-impl.h
    src/inspector/v8-inspector-session-impl.h
    src/inspector/v8-runtime-agent-impl.h
    src/inspector/v8-stack-trace-impl.h
)

while [ $# -gt 0 ]; do
    case "$1" in
        --v8-dir)   V8_DIR="$2"; shift 2 ;;
        --v8-dir=*) V8_DIR="${1#*=}"; shift ;;
        --gen-dir)  GEN_DIR="$2"; shift 2 ;;
        --gen-dir=*) GEN_DIR="${1#*=}"; shift ;;
        -h|--help)  echo "Usage: $(basename "$0") [--v8-dir <path>] --gen-dir <path>"; exit 0 ;;
        *)          echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

[ -d "$V8_DIR/src" ] || { echo "No V8 sources at $V8_DIR" >&2; exit 1; }

# src/inspector/protocol/*.h are generated into the build directory rather than
# living in the source tree, but the closure runs straight through them
# (Forward.h -> Protocol.h -> the per-domain headers), so they must be in place
# before it is computed. A real V8 build puts gen/ on the include path; staging
# them into the checkout is the same thing by other means.
if [ -z "$GEN_DIR" ] || [ ! -d "$GEN_DIR/src/inspector/protocol" ]; then
    echo "--gen-dir must point at a build's gen/ containing src/inspector/protocol" >&2
    exit 1
fi
mkdir -p "$V8_DIR/src/inspector/protocol"
cp "$GEN_DIR/src/inspector/protocol/"*.h "$V8_DIR/src/inspector/protocol/"

DIST="$ROOT_DIR/dist/src-headers"
rm -rf "$DIST"
mkdir -p "$DIST"

MANIFEST="$(mktemp)"
trap 'rm -f "$MANIFEST"' EXIT

python3 "$ROOT_DIR/scripts/matrix/src-headers-closure.py" "$V8_DIR" "${ENTRY_POINTS[@]}" \
    > "$MANIFEST"

[ -s "$MANIFEST" ] || { echo "error: closure came back empty" >&2; exit 1; }

(cd "$V8_DIR" && tar -cf - -T "$MANIFEST") | (cd "$DIST" && tar -xf -)

# The closure is self-contained by construction, but assert it: a bug in the
# scanner would otherwise ship a subtly incomplete package.
python3 "$ROOT_DIR/scripts/matrix/check-src-headers-closed.py" "$DIST" "$V8_DIR"

echo "$V8_VERSION" > "$DIST/V8_VERSION"

echo "packaged $(wc -l < "$MANIFEST" | tr -d ' ') headers"
du -sh "$DIST"
