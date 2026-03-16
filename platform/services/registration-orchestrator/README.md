# Registration Orchestrator

Bu servis urun mantigini patch'lemek icin degil, registration truth'u disaridan izlemek ve raporlamak icin vardir.

## Sorumluluklar

- LDAP, XMPP, `c_agent`, dashboard ve computer tree arasindaki tutarliligi gozlemlemek
- startup race condition semptomlarini kayda gecirmek
- platform acceptance ve golden parity icin kanit uretmek

## Bilincli Sinir

Bu servis stock LiderAhenk davranisini override etmez. Yalnizca:

- snapshot alir
- drift raporlar
- failure taxonomy uygular
- artifact yazar

## Artifact'ler

Servis asagidaki artifact'leri uretir:

- `artifacts/platform/run-manifest.json`
- `artifacts/platform/registration-verdict.json`
- `artifacts/platform/registration-events.jsonl`
- `artifacts/platform/failure-summary.json`

Bu artifact'ler `make validate-registration-evidence` ile sozlesmeye karsi dogrulanir.
Validator ayrica:

- `artifacts/platform/registration-evidence-report.json`
- `artifacts/platform/registration-evidence-report.md`

raporlarini yazar.

Gercek mutasyon gerekiyorsa bu bootstrap/provisioning katmaninda cozulmelidir.
