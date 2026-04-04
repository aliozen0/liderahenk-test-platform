# Golden Install Baseline

Bu klasor, canonical stock LiderAhenk baseline artifact'lerini tutar.

## Bu Klasor Ne Icin Var

- stock kurulumdan alinan referans kanitlari saklamak
- release gate ve diff surecinin tek referans kaynagi olmak
- patch'li dev runtime ile stock davranisi ayirmak

## Bugunku Durum

Repo ile birlikte gelen icerik bilincli olarak `capture-pending` durumundadir.
Yani:

- bu klasor su an tam bir baseline degildir
- yalnizca iskelet ve placeholder artifact tasir
- stock capture alindiginda gercek data ile guncellenir

## Beklenen Dosyalar

| Yol | Rol |
|---|---|
| `manifest.json` | Capture durumu, source bilgisi ve fingerprint metadata |
| `ldap-tree.json` | Canonical LDAP tree evidence |
| `config.json` | Canonical runtime config evidence |
| `api-captures/dashboard.json` | Dashboard API capture |
| `api-captures/agent-list.json` | Agent list API capture |
| `api-captures/computer-tree.json` | Computer tree API capture |
| `ui-evidence/dashboard.png` | Dashboard ekran kaniti |
| `ui-evidence/computer-management.png` | Computer management ekran kaniti |

## Onemli Kurallar

- Bu klasoru patch'li dev runtime'dan doldurmayin.
- Canonical baseline yalnizca gercek stock LiderAhenk kurulumundan capture edilir.
- `manifest.json` kendi kendini fingerprint etmez; diger artifact'leri hash'ler.
- `capture-pending` durumundaki placeholder dosyalar bilincli olarak release gate'i durdurur.

## Referans Belgeler

- [platform/baselines/README.md](/home/huma/liderahenk-test/platform/baselines/README.md)
- [docs/golden-baseline-capture.md](/home/huma/liderahenk-test/docs/golden-baseline-capture.md)
- [docs/golden-baseline-capture-checklist.md](/home/huma/liderahenk-test/docs/golden-baseline-capture-checklist.md)
