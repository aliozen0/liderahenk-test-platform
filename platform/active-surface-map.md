# Active Surface Map

Bu belge, repoda hangi yuzeylerin aktif build/runtime truth oldugunu ve
hangilerinin legacy veya artifact oldugunu netlestirir.

## Amaç

Bu repo tek bir platformdur. Ayrı make projeleri veya ayrı urunler yoktur.
`Makefile` tek giris kapisidir. Karisma, zaman icinde biriken patch ve
yardimci dosya yuzeylerinden gelir.

Bu haritanin amaci:

- yeni gelen biri icin aktif yuzeyi gostermek
- legacy/stale alanlari build-truth sanma riskini kaldirmak
- runtime-first vizyona uygun okuma sirasi vermek

## Tek Giris Kapisi

- `Makefile`

Bu dosya:

- compose katmanlarini
- upstream source preparation zincirini
- runtime dogrulama komutlarini
- acceptance, observability ve governance komutlarini

tek facade uzerinden toplar.

## Aktif Runtime / Build Truth

### Orkestrasyon ve Profil Truth'u

- `compose/`
- `platform/upstream-manifest.yaml`
- `platform/bootstrap/bootstrap-manifest.yaml`
- `platform/contracts/`

### Runtime Kod Yuzeyi

- `platform_runtime/`
- `adapters/`
- `orchestrator/`
- `platform/services/registration-orchestrator/`

### Upstream Uyumlama Yuzeyi

- `services/liderapi/wiring/patches/`
- `services/liderapi/extensions/`
- `services/liderui/wiring/patches/`
- `services/liderui/extensions/`
- `services/ahenk/hooks/`

### Calisan Servisler

- `services/liderapi/`
- `services/liderui/`
- `services/lidercore/`
- `services/ahenk/`
- `services/provisioner/`
- `services/mariadb/`
- `services/ldap/`
- `services/ejabberd/`
- `services/platform-exporter/`
- `services/ejabberd-exporter/`
- `observability/`

## Runtime Truth Kaynaklari

Platform yalnizca su resmi runtime truth yuzeylerinden okuma yapar:

- LDAP
- ejabberd/XMPP
- MariaDB `c_agent` ve `c_config`
- `liderapi` dashboard / agent-list / computer-tree / task-policy yuzeyleri
- Grafana / Prometheus / Loki runtime telemetry yuzeyi

## Legacy / Stale / Build-Truth Disi Alanlar

Asagidaki alanlar repoda bulunabilir ama aktif build truth degildir:

- `services/liderapi/patches/`
- `services/liderui/patches/`
- `artifacts/`
- `tests/ui/node_modules/`
- `__pycache__/`
- `.pytest_cache/`

Bu alanlar:

- tarihsel referans
- lokal artifact
- vendor cache
- gecici test ciktisi

olarak okunmalidir.

## Patch Governance Truth'u

Aktif patch yuzeyi icin resmi envanter:

- `platform/patch-inventory.csv`
- `platform/remaining-overlay-classification.md`

Bu iki dosyada olmayan bir patch yuzeyi aktif kabul edilmemelidir.

## Okuma Sirasi

Repo ilk kez incelenecekse su sirayla okunmalidir:

1. `docs/platform_vizyonu.md`
2. `docs/product-requirements.md`
3. `Makefile`
4. `platform/upstream-manifest.yaml`
5. `platform/bootstrap/bootstrap-manifest.yaml`
6. `compose/`
7. `platform/contracts/`
8. `adapters/`
9. `platform_runtime/`
10. `orchestrator/`
11. `platform/patch-inventory.csv`

## Kural

Bir dosya veya klasor icin “bu aktif mi?” sorusu cikarsa varsayilan cevap
hayir degildir; once su uc yere bakilir:

- `Makefile`
- `platform/upstream-manifest.yaml`
- `platform/patch-inventory.csv`

Bu yuzeylerden birine baglanmiyorsa, aktif runtime/build truth olma ihtimali
dusuktur ve legacy/stale olarak degerlendirilmelidir.
