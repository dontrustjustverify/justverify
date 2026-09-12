#!/bin/bash
# Pinned upstream application built natively; no Docker daemon or SDK in the image.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
work=${1:?new absolute Linux build directory}
[[ $(uname -m) = aarch64 && $(uname -s) = Linux && "$work" = /* && ! -e "$work" ]]
commit=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["commit"])' "$root/catalog/mempool.json")
git clone --depth 1 --branch v3.3.1 https://github.com/mempool/mempool.git "$work"
[[ $(git -C "$work" rev-parse HEAD) = "$commit" ]]
cd "$work"
git apply "$root/image/mempool/loopback.patch"
git apply "$root/image/mempool/local-ui.patch"
npm install --prefix "$work/build-tools" --no-audit --no-fund npm@11.8.0
export PATH="$work/build-tools/node_modules/.bin:$HOME/.cargo/bin:$PATH" MEMPOOL_COMMIT_HASH="$commit" DOCKER_COMMIT_HASH="$commit" CYPRESS_INSTALL_BINARY=0 NG_CLI_ANALYTICS=false
# Freeze the NAPI CLI and its entire graph; keep upstream Cargo.lock.
python3 - <<'NAPI'
import json,pathlib
p=pathlib.Path('rust/gbt/package.json');c=json.loads(p.read_text());c.setdefault('devDependencies',{})['@napi-rs/cli']='2.18.0';p.write_text(json.dumps(c,indent=2)+'\n')
NAPI
cp "$root/image/mempool/gbt-package-lock.json" rust/gbt/package-lock.json
(cd rust/gbt && npm ci --no-audit --no-fund && npm run build-release && npm run to-backend)
(cd backend && npm ci --ignore-scripts --no-audit --no-fund && npm run build)
(cd frontend && npm ci --no-audit --no-fund)
cp "$root/image/mempool/frontend-config.json" frontend/mempool-frontend-config.json
python3 - <<'LOCALES'
import json,pathlib
p=pathlib.Path('frontend/angular.json');c=json.loads(p.read_text());c['projects']['mempool']['architect']['build']['configurations']['production']['localize']=['en-US','ko','ja'];p.write_text(json.dumps(c,indent=2)+'\n')
LOCALES
(cd frontend && npm run generate-themes && npm run generate-config && NODE_OPTIONS=--max-old-space-size=4096 NG_BUILD_MAX_WORKERS=2 npm run ng -- build --configuration production && npm run copy-themes)
mkdir -p bundle/backend bundle/web bundle/source
cp -a backend/dist/. bundle/backend/
(cd backend && npm prune --omit=dev --ignore-scripts --no-audit --no-fund)
cp -a backend/node_modules bundle/backend/
if [[ -L bundle/backend/node_modules/rust-gbt ]]; then rm bundle/backend/node_modules/rust-gbt; cp -a backend/rust-gbt bundle/backend/node_modules/; fi
rm -rf bundle/backend/node_modules/typescript bundle/backend/node_modules/@types
cp -a frontend/dist/mempool/browser/. bundle/web/
cp -a frontend/src/resources bundle/web/
cp LICENSE COPYING.md bundle/
cp LICENSE COPYING.md bundle/source/
cp "$root/image/mempool/BUILD.md" bundle/source/
cp "$root/catalog/mempool.json" bundle/manifest.json
# Corresponding upstream source, exact build modifications and lockfiles are shipped.
git diff > bundle/source/justverify.patch
git archive --format=tar HEAD | gzip -n > bundle/source/mempool-3.3.1.tar.gz
cp "$root/scripts/build_mempool.sh" "$root/image/mempool/frontend-config.json" bundle/source/
cp rust/gbt/Cargo.lock bundle/source/gbt-Cargo.lock
cp rust/gbt/package-lock.json bundle/source/gbt-package-lock.json
cp -a "$root/image/mempool/pools-v2.json" "$root/image/mempool/pools-tree.json" "$root/image/mempool/POOLS-LICENSE" bundle/web/resources/
(node --version; npm --version; (cd rust/gbt && cargo --version && rustc --version); git rev-parse HEAD) > bundle/build-versions.txt
(cd bundle && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
tar -C bundle -czf "$work/bundle.tar.gz" .
sha256sum "$work/bundle.tar.gz"
