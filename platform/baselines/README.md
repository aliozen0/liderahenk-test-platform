# Baselines

Bu klasor, stock LiderAhenk davranisini referans alan baseline altyapisini toplar.

Amac:

- patch'li gelistirme ortamini kendi kendine referans yapmamak
- canonical stock kurulumdan resmi capture almak
- aday runtime'i bu referansla karsilastirmak

## Klasor Yapisi

| Yol | Rol |
|---|---|
| `platform/baselines/golden-install/` | Canonical baseline artifact klasoru |
| `platform/baselines/stock-capture.env.example` | Stock ortamdan capture almak icin ornek env dosyasi |

## `golden-install` Icerigi

| Dosya / Klasor | Anlam |
|---|---|
| `manifest.json` | Baseline capture durumu ve fingerprint metadata |
| `ldap-tree.json` | Canonical LDAP tree evidence |
| `config.json` | Canonical runtime config evidence |
| `api-captures/` | Dashboard, agent list ve computer tree API capture'lari |
| `ui-evidence/` | Dashboard ve computer management ekran goruntuleri |

Not:

- Repo ile gelen `golden-install` klasoru bilincli olarak `capture-pending` durumundadir.
- Bu klasor patch'li dev runtime'dan doldurulmaz.
- Canonical baseline yalnizca gercek stock LiderAhenk kurulumundan capture edilir.

## Standart Akis

1. Durumu gor:

```bash
make golden-baseline-status
```

2. Stock env dosyasini hazirla:

- `platform/baselines/stock-capture.env.example`

3. Capture oncesi preflight kos:

```bash
BASELINE_ENV_FILE=platform/baselines/stock-capture.env.example make golden-baseline-preflight
```

4. Canonical capture al:

```bash
BASELINE_CAPTURE_CONFIRM=1 make capture-golden-baseline \
  BASELINE_ENV_FILE=platform/baselines/stock-capture.env.example \
  BASELINE_SOURCE_LABEL="stock-install-YYYY-MM-DD"
```

5. Capture'i dogrula:

```bash
make validate-golden-baseline
```

6. Aday runtime ile karsilastir:

```bash
make diff-baseline
```

## Operator Belgeleri

- [docs/golden-baseline-capture.md](/home/huma/liderahenk-test/docs/golden-baseline-capture.md)
- [docs/golden-baseline-capture-checklist.md](/home/huma/liderahenk-test/docs/golden-baseline-capture-checklist.md)
- [platform/baselines/golden-install/README.md](/home/huma/liderahenk-test/platform/baselines/golden-install/README.md)
