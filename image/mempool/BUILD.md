# Corresponding source for the bundled mempool 3.3.1

Upstream: https://github.com/mempool/mempool, commit `9332d9db97bcc7beed079acc8f79aa21c9b12a3b`.
The unmodified source archive, complete tracked-source patch, generated NAPI lock,
frontend configuration and licenses are available beside this file. No upstream
source files are omitted from the archive. JustVerify's separate service/proxy
and integration build script are at https://github.com/dontrustjustverify/justverify.

Build on ARM64 Debian 13 with Node20.19.2, npm11.8.0, Rust1.84.1, make, C/C++, Git.
Use `npm ci`; do not regenerate the included dependency locks.

```sh
mkdir mempool-source
cd mempool-source
tar -xf ../mempool-3.3.1.tar.gz
patch -p1 < ../justverify.patch
cp ../gbt-package-lock.json rust/gbt/package-lock.json
cp ../frontend-config.json frontend/mempool-frontend-config.json
export CYPRESS_INSTALL_BINARY=0 NG_CLI_ANALYTICS=false
export MEMPOOL_COMMIT_HASH=9332d9db97bcc7beed079acc8f79aa21c9b12a3b
export DOCKER_COMMIT_HASH=$MEMPOOL_COMMIT_HASH
(cd rust/gbt && npm ci --no-audit --no-fund && npm run build-release && npm run to-backend)
(cd backend && npm ci --ignore-scripts --no-audit --no-fund && npm run build)
(cd frontend && npm ci --no-audit --no-fund && npm run generate-themes && npm run generate-config && NODE_OPTIONS=--max-old-space-size=4096 NG_BUILD_MAX_WORKERS=2 npm run ng -- build --configuration production && npm run copy-themes)
```

Backend output is `backend/dist`, with production `backend/node_modules` and the
compiled `backend/rust-gbt` native module. Frontend output is
`frontend/dist/mempool/browser`, plus `frontend/src/resources`. The three locales
are en-US, ko and ja. The complete JustVerify `scripts/build_mempool.sh` packages
these outputs and the pinned MIT mining-pool dataset into the image bundle.
The dataset and its license are also served at `/resources/pools-v2.json`,
`/resources/pools-tree.json` and `/resources/POOLS-LICENSE`.

Local changes bind the backend to loopback, build three locales, suppress fiat
values when external price feeds are disabled, and pin the native build tool.
The original application's AGPL and additional notices remain in force; see
LICENSE and COPYING.md. The modified application is not an official mempool release.
