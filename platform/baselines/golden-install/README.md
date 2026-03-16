# Golden Install Baseline

Bu klasor, stock LiderAhenk kurulumundan toplanan referans kanitlar icindir.

## Hedef

Patch'li repo davranisini referans almak yerine, "dogru calisan" stock kurulum davranisini resmi kabul noktasi yapmak.

## Beklenen Ciktılar

- `manifest.json`
- `ldap-tree.json`
- `config.json`
- `api-captures/`
- `ui-evidence/`

## Durum

Bu klasor simdilik iskelet olarak eklendi. Gercek baseline kanitlari ayrica stock kurulumdan toplanacak.

## Komutlar

- `make validate-golden-baseline`
- `make capture-golden-baseline BASELINE_ENV_FILE=platform/baselines/stock-capture.env.example BASELINE_SOURCE_LABEL="stock-install-YYYY-MM-DD"`
- `make diff-baseline`

Detayli akış:

- `docs/golden-baseline-capture.md`

## Not

Bu klasordeki `capture-pending` durumlu dosyalar bilinclı olarak gecersizdir.
Validator ancak tum zorunlu artifact'ler gercek capture ile dolduruldugunda yesil doner.
Manifest metadata'si diger artifact'leri fingerprint eder; `manifest.json` kendini hash'lemez.
Diff raporu `baseline-diff.json` ve `baseline-diff.md` olarak yazilir; `error` farklari release gate'i bloklar.
