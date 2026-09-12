#!/usr/bin/env python3
import json,pathlib
R=pathlib.Path(__file__).resolve().parents[1];path=R/'catalog/releases.json';manifest=json.loads(path.read_text())
core={r['version']:r for r in json.loads((R/'docs/evidence/core-matrix-summary.json').read_text())};electrs={r['core']:r for r in json.loads((R/'docs/evidence/electrs-matrix-summary.json').read_text())}
for r in manifest['releases']:
    v=r['version'];r['arm64_binary_sha256']=core.get(v,{}).get('binary_sha256');r['verification']=core.get(v,{}).get('status','NOT RUN');r['electrs']={'version':'0.11.1','status':electrs.get(v,{}).get('status','NOT RUN'),'scope':'ARM Linux regtest indexing/history/broadcast/confirmation/restart'}
    r['support_status']='EOL upstream (major <=28)' if int(v.split('.')[0])<=28 else 'review supported maintenance window at release'
    r['configuration_schema']=f'policy-{v}.json' if (R/'catalog'/f'policy-{v}.json').exists() else 'NOT RUN'
    helpfile=R/'docs/evidence/core-matrix'/v/'help.txt';r['networks']=['main','test','signet','regtest']
    if helpfile.exists() and '  -testnet4' in helpfile.read_text():r['networks'].insert(2,'testnet4')
    ev=R/'docs/evidence'/f'core-{v}-aarch64-linux-gnu-download.json'
    if ev.exists():r['arm64_artifact']=json.loads(ev.read_text())
    if v in ['30.0','30.1']:
        r['availability']='UPSTREAM_WITHDRAWN';r['reason']='Official binaries withdrawn due to wallet migration data deletion bug';r['notice']='https://bitcoincore.org/en/2026/01/05/wallet-migration-bug/'
    else:r['availability']='OFFICIAL_BINARY_VERIFIED' if r['verification']=='PASS' else 'UNVERIFIED'
manifest['default_version']='31.1';path.write_text(json.dumps(manifest,indent=2)+'\n')
lines=['# 버전 호환성','', '지원 주장 범위: 아래 결과는 Debian ARM64 VM의 실제 regtest 시험이다. Pi 하드웨어·mainnet 대규모 데이터·x86_64·모바일 지갑을 검증한 것은 아니다. 데이터 재사용은 모든 교차 버전에서 기본 거부하고 별도 경로를 사용한다.','', '| Core | 공식 바이너리/기동/RPC | electrs 0.11.1 | 정책 의미/설정 적용 |','|---|---|---|---|']
for r in manifest['releases']:lines.append(f"| {r['version']} | {r['availability']} / {r['verification']} | {r['electrs']['status']} | NOT RUN |")
lines+=['','증거: `docs/evidence/core-matrix-summary.json`, `electrs-matrix-summary.json`, 각 버전의 `core-matrix/*/result.json`. 모든 SHA256/서명자는 catalog/releases.json에 연결된다.','', '30.0/30.1은 공식 철회 공지와 실패 원인을 유지한다. 목록에서 숨기지 않고 설치 불가 이유를 표시한다.','', '기본 patch 목록은 major별 최대 patch, 확장 목록은 전체 안정 릴리스다. 선택/서비스 전환 UI 및 정책 적용은 구현 중이다.']
(R/'docs/VERSION_COMPATIBILITY.md').write_text('\n'.join(lines)+'\n')
