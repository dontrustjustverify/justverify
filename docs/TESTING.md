# Release validation — 0.1.0-beta2

Beta2 is a testing release. Component tests and image checks have different scopes; physical installation of this image remains pending.

| Check | Scope and result |
|---|---|
| Version and policy validation | PASS: 20 Rust checks on ARM64 Linux; Core 22–31 catalog compatibility checks |
| OP_RETURN, fees and mempool behavior | PASS on an actual Pi5 in isolated Core31.1 regtest: signed transactions, size boundaries, valid-block acceptance, persistence, expiry and memory-pressure eviction |
| Dashboard collector | PASS on Pi5 regtest: a delayed coinbase response does not block chain/header updates; reorg and Core pause/resume recover correctly |
| Miner labels | PASS on Pi5 regtest: tagged blocks, unknown/ambiguous tags, caching and reorg reassignment |
| Browser and sessions | PASS: desktop/mobile viewports, HTTP address copy, refresh, service restart, renewal, logout/password revocation and origin/cookie boundaries |
| SSH administration | PASS: real SSH/password sudo in an isolated ARM Linux account namespace; wrong passwords and unauthenticated sudo rejected; changed passwords preserved |
| Core/electrs/mempool on Pi5 | PASS: signed transaction broadcast, wallet/address reflection, two confirmations, equal height107 and tip; Core, indexer, SQL/backend recovery |
| Pristine beta2 image | PASS: full filesystem, source/binary hashes, ownership, enabled units, identity absence, ARM runtime and cross-host decompression checks |
| Beta2 SSH on booted image | PASS: actual SSH login and password-authenticated sudo on the generic ARM appliance VM |
| Generic ARM initial boot and reboot | Fresh retry: initial boot PASS including Tor, TUI and QR. Reboot preserved identities/data/services, but onion RPC exceeded90s: FAIL for that network check. |
| Same-image recovery | PASS twice, including actual reboot, authenticated onion RPC and unauthorized-access denial |

The first VM attempt also timed out during Tor bootstrap at50% after120s. These intermittent Tor timing failures remain open; the test deadlines were not extended. Successful retries do not establish reliable cold Tor startup.

The browser tests use a 390px viewport for mobile layout, not a physical wallet or camera. Session boundary tests do not represent seven elapsed days of testing. Short Pi observations do not establish long-run stability.

Pending release gates include physical beta2 installation and reboot, full public-network synchronization/indexing, mobile-wallet acceptance, long-duration operation, restore onto a newly created data UUID, OS update failure recovery and whole-image byte reproducibility. I2P is not packaged; pruning is incompatible with bundled electrs. These limitations are not removed by a successful component test.
