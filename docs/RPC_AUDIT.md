# Core31.1 RPC 검증 (진행 중)

실행 바이너리 Core31.1, RPC help151개를 실제 조회했다. help PASS는 실행 의미론 PASS가 아니다. 변경 RPC는 별도 regtest 지갑/데이터에서만 시험했다. 제품은 임의 Core RPC를 공개하지 않으며 아래 HTTPS PASS는 개별 권한/할당 지갑 경계를 통과한 성공 호출이다.

원본 결과: [help](evidence/core-31.1-rpc-help.json), [signed regtest](evidence/signed-chain-audit.json), [TLS gateway](evidence/rpc-gateway-audit.json). gateway 테스트는 노출한 READ_METHODS 및 WatchOnly READ/TRANSACTION_METHODS 전체가 실제 성공한 것을 집합 비교로 강제한다. 오류/권한 거부도 별도 HTTP 상태로 기록하며 성공으로 세지 않는다. 기기 재부팅 및 실제 모바일 앱의 호출 순서는 별도 게이트다.

| RPC | help | 실제 실행 결과 | 근거 / 미실행 사유 |
|---|---|---|---|
| `abandontransaction` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `abortprivatebroadcast` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `abortrescan` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `addnode` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `analyzepsbt` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `backupwallet` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `bumpfee` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `clearbanned` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `combinepsbt` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `combinerawtransaction` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `converttopsbt` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `createmultisig` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `createpsbt` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `createrawtransaction` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `createwallet` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `createwalletdescriptor` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `decodepsbt` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `decoderawtransaction` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `decodescript` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `deriveaddresses` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `descriptorprocesspsbt` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `disconnectnode` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `dumptxoutset` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `encryptwallet` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `enumeratesigners` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `estimatesmartfee` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `finalizepsbt` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `fundrawtransaction` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `getaddednodeinfo` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getaddressesbylabel` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getaddressinfo` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getaddrmaninfo` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getbalance` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getbalances` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getbestblockhash` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `getblock` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getblockchaininfo` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getblockcount` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getblockfilter` | PASS | PASS direct isolated Core | signed-chain-index-restart-audit.json |
| `getblockfrompeer` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getblockhash` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getblockheader` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getblockstats` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getblocktemplate` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getchainstates` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getchaintips` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getchaintxstats` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getconnectioncount` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getdeploymentinfo` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getdescriptoractivity` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getdescriptorinfo` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getdifficulty` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `gethdkeys` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getindexinfo` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `getmemoryinfo` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getmempoolancestors` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getmempoolcluster` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getmempooldescendants` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getmempoolentry` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getmempoolinfo` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getmininginfo` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getnettotals` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `getnetworkhashps` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getnetworkinfo` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getnewaddress` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `getnodeaddresses` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getpeerinfo` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `getprioritisedtransactions` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getprivatebroadcastinfo` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getrawchangeaddress` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getrawmempool` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getrawtransaction` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getreceivedbyaddress` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getreceivedbylabel` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `getrpcinfo` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `gettransaction` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `gettxout` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `gettxoutproof` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `gettxoutsetinfo` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `gettxspendingprevout` | PASS | PASS direct isolated Core | signed-chain-index-restart-audit.json |
| `getwalletinfo` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `getzmqnotifications` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `help` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `importdescriptors` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `importmempool` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `importprunedfunds` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `joinpsbts` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `keypoolrefill` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `listaddressgroupings` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `listbanned` | PASS | PASS registered regtest | backend-profile-audit.log / linux_resource_policy.py; actual120s ban then removal |
| `listdescriptors` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `listlabels` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `listlockunspent` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `listreceivedbyaddress` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `listreceivedbylabel` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `listsinceblock` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `listtransactions` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `listunspent` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `listwalletdir` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `listwallets` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `loadtxoutset` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `loadwallet` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `lockunspent` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `logging` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `migratewallet` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `ping` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `preciousblock` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `prioritisetransaction` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `pruneblockchain` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `psbtbumpfee` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `removeprunedfunds` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `rescanblockchain` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `restorewallet` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `savemempool` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `scanblocks` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `scantxoutset` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `send` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `sendall` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `sendmany` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `sendrawtransaction` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `sendtoaddress` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `setban` | PASS | PASS registered regtest | backend-profile-audit.log / linux_resource_policy.py; actual120s ban then removal |
| `setlabel` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `setnetworkactive` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `setwalletflag` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `signmessage` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `signmessagewithprivkey` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `signrawtransactionwithkey` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `signrawtransactionwithwallet` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `simulaterawtransaction` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `stop` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `submitblock` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `submitheader` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `submitpackage` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `testmempoolaccept` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `unloadwallet` | PASS | PASS direct isolated Core | signed-chain-audit.json / rpc-gateway-audit.json |
| `uptime` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `utxoupdatepsbt` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `validateaddress` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `verifychain` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `verifymessage` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `verifytxoutproof` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `waitforblock` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `waitforblockheight` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `waitfornewblock` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `walletcreatefundedpsbt` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |
| `walletdisplayaddress` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `walletlock` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `walletpassphrase` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `walletpassphrasechange` | PASS | NOT RUN semantics | help lookup only; no semantic claim |
| `walletprocesspsbt` | PASS | PASS HTTPS gateway | rpc-gateway-audit.json |


Extended index/confirmed transaction audit: `signed-chain-index-restart-audit.json` adds real confirmed gettxspendingprevout through txospenderindex, getrawtransaction through txindex, getblockfilter, and all three getindexinfo indexes synced at104 before/after restart. The signed tx has3 confirmations. The earlier37-method real TLS gateway coverage remains unchanged; unexercised Core RPC methods remain explicitly listed. Public testnet4 confirmation now includes electrs get_history height and get_merkle proof checked against the actual Core header, with independent block/tx status agreement in public-testnet4-audit.json.
