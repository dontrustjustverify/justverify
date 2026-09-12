# Third-party notices

JustVerify 코드는 독립 작성한다. Umbrel 코드는 포함하지 않았으며 기능 비교 대상으로만 사용한다.

- Mining pool registry: mempool/mining-pools commit `f678a4a620537ad7997a475ad0f14bfab1de3c8b`, `pools-v2.json`을 `catalog/mining-pools.json`으로 변경 없이 포함. MIT, Copyright (c) 2019 btc.com. 전문 `licenses/mining-pools/LICENSE`; 해당 데이터와 라이선스를 이미지에도 포함한다. 태그·보상 주소는 추정용이며 신원 증명이 아니다.

- xterm.js 6.0.0: MIT, 전문 `web/static/XTERM_LICENSE`. 원본 npm tarball 및 SHA512 integrity는 `catalog/xterm.json`.
- Rust dependencies: Cargo.lock의326개 외부 패키지를 조사했다. 원문과 출처/해시는 `docs/licenses/rust/`, `docs/evidence/rust-license-inventory.json`.323개 패키지에서 원문을 수집했으며3개는 원문 또는 정확한 VCS 출처 미확보다. 모든 플랫폼을 포함한 상위 집합이다. ARM64 기본 feature의 실행·빌드 의존성262개에는 원문 누락이 없으며 `docs/evidence/rust-license-arm64.json`에 기록했다. 최종 의무/고지 검토는 아직 미완료다. 재현: `cargo metadata --locked --format-version 1 > .state/cargo-license-metadata.json`, `python3 scripts/rust_license_inventory.py .state/cargo-license-metadata.json`, `python3 scripts/fetch_rust_license_texts.py`.
- electrs 0.11.1: MIT, upstream https://github.com/romanz/electrs commit 35216c6d30148be8e6763d913d437330f431fc03. 개발 checkout `.cache/electrs-0.11.1`의 LICENSE. `docs/evidence/electrs-0.11.1-usage.md` 및 upgrading.md는 해당 upstream 문서 사본.
- Bitcoin Core: MIT, 공식 binary/source 배포. 릴리스별 manifest 및 서명자 evidence 참고.
- Debian/Raspberry Pi OS/Tor: 각 패키지별 라이선스 적용. OS 이미지 배포 전 `/usr/share/doc/*/copyright`와 소스 제공 의무 확인 및 배포 고지를 완성해야 한다.

현재 고지는 개발 중 목록이며 최종 릴리스 라이선스 검토 완료를 의미하지 않는다.

ARM64 의존성 구분 재현: `cargo metadata --locked --format-version 1 --filter-platform aarch64-unknown-linux-gnu > .state/cargo-license-arm64-metadata.json`, `python3 scripts/rust_license_target.py .state/cargo-license-arm64-metadata.json aarch64-unknown-linux-gnu docs/evidence/rust-license-arm64.json`. 수집한 원문은 upstream의 줄바꿈·공백을 그대로 보존했으며 해시로 대조한다.

## Bundled mempool explorer (0.1.0-beta1)

- Mempool v3.3.1, commit `9332d9db97bcc7beed079acc8f79aa21c9b12a3b`, https://github.com/mempool/mempool. Its own LICENSE and COPYING.md apply to the separately packaged application; JustVerify's MIT license does not relicense it. The native bundle includes upstream source, exact changes and build files under `source/`, exposed by the local explorer's “Source · AGPL” link. The backend loopback bind and three-locale build changes are disclosed in `justverify.patch`. The upstream branding remains attributed; no endorsement is claimed.
- npm dependencies keep their original license files inside the runtime bundle. Rust GBT source and Cargo lock are included with upstream source. Node.js and MariaDB retain their upstream/Debian licenses and installed copyright notices.
- The mempool explorer's pinned local mining-pools snapshot and MIT notice are in `image/mempool/`; its commit and SHA256 are in `catalog/mempool.json`.
- Umbrel app reference commit `01de454ee9a368245a2513afc8e84969bafb946a`, README reference `bfa79ed24031b0065dd2f810411d58b82af1b95e`. Examined for configuration, port 3006, memory budgeting and guide structure. No Umbrel source or artwork is included.
