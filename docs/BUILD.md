# Build JustVerify for Raspberry Pi 5

Use an isolated ARM64 Debian 13 Linux machine with systemd, loop devices, root access for image assembly, and enough disk space for the base image, build caches, raw image and verification copies. macOS can drive a QEMU ARM builder but cannot run the Linux image assembly directly. Never pass a physical drive to these scripts.

1. Check out the release source. Install the Rust toolchain from `rust-toolchain.toml` and build with `cargo build --release --locked`. Run `cargo test --locked`; record skipped integration tests separately.
2. Fetch and verify the Raspberry Pi OS base named in `catalog/pi-base.json`. Fetch Bitcoin Core 31.1 with `scripts/fetch_core.py` and its trusted signer catalog; verify the signature and checksum. Build the exact electrs commit in `catalog/electrs.json` using `scripts/build_electrs.py`. Image assembly rejects mismatched Core/electrs hashes.
3. Install the mempool build tools in the isolated builder: Debian Node.js `20.19.2+dfsg-1+deb13u2`, npm, MariaDB `1:11.8.6-0+deb13u1`, a C/C++ toolchain and Git. Run `scripts/build_mempool.sh /absolute/new/mempool-build`. It pins the upstream release, npm 11.8.0, the NAPI build tool, npm/Cargo graphs, the three localized frontends and local mining-pool data. See `catalog/mempool.json`. The bundle contains its hashes, source, modifications and licenses.
4. Run the actual integration test as the unprivileged `justverify` test user. Use a fresh test directory and accessible copies of the selected binaries:

   ```sh
   /opt/justverify/venv/bin/python tests/mempool_live.py \
     --state /var/tmp/jv-mempool-test-release \
     --core /absolute/bitcoin-31.1/bin \
     --electrs /absolute/electrs \
     --bundle /absolute/mempool-build/bundle
   ```

5. Assemble the image from regular files in the isolated builder:

   ```sh
   sudo bash image/build-pi.sh \
     /absolute/base.img.xz /absolute/bitcoin-31.1 \
     target/release/justverify /absolute/electrs \
     0.1.0-beta1 /absolute/mempool-build/bundle
   sudo bash image/verify-pi.sh dist/justverify-0.1.0-beta1.img.xz
   ```

6. Run image boot/reboot tests on a disposable copy with enough expansion space, then validate the image on the target Pi 5 and physical wallet devices. Do not distribute a booted test clone containing test identities. Package the pristine image with its manifest, checksums, signature, corresponding component source and exact test report.

The short image filename is Pi5-only in this release. A successful build does not close the pending gates in [TESTING.md](TESTING.md). Byte-for-byte reproducibility of the whole OS image is not currently claimed; apt package inventories and component/source hashes are recorded with the release.

Generated integration results belong in `docs/evidence/` and are ignored by Git. The published [test report](https://github.com/dontrustjustverify/justverify/releases/download/v0.1.0-beta1/justverify-0.1.0-beta1-test-report.json) records the release validation; local development diaries are not part of the source distribution. Keep the tests when building or changing the node.
