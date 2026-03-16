# Patch Allowlist

Bu belge, platform ile urun arasindaki siniri zorunlu olarak tanimlar.

## Serbest Olan Patch Tipleri

- `packaging_patch`
  - Docker build, pinned ref, upstream clone, queue apply
- `runtime_config_patch`
  - env injection, nginx reverse proxy, websocket proxy
- `platform_extension`
  - adapters, orchestrator, bootstrap, observability, acceptance tooling
- `queue_patch`
  - upstream dosya uzerine ince ve izlenebilir patch queue
- `runtime_hook`
  - yalnizca `ahenk` container-mode uyumlulugu icin
- `compat_fix`
  - entity/schema uyumlulugu, gecici migration yardimi
- `redirect_wrapper`
  - stock path'i platform extension view'e baglayan ince wrapper

## Yasak Olan Patch Tipleri

- upstream business logic icine yeni alan kurallari yazmak
- UI view kopyalayarak urun davranisini fork etmek
- dashboard, tree veya domain truth'u urun icinde "duzeltmek"
- `uid` alanini DN tasiyicisi gibi kullanmaya devam eden yeni kod
- stock davranis bozuk diye yeni full-class replacement eklemek
- overlay icinde yeni tam dosya kopyasi eklemek; once queue patch denenmeli

## Izinli Istisnalar

- upstream icinde yalnizca extension seam acmak icin ince wiring patch
- overlay yerine queue patch tercih edilir
- mevcut `full_override` siniflari kaldirilana kadar gecici durum olarak korunur
- `compat_fix` dosyalari ADR ile gerekcelendirilir
- kalan overlay yuzeyi yalnizca su kategorilerde kabul edilir:
  - `bootstrap_hook`
  - `compat_fix`
  - `platform_extension`
  - dar kapsamli `wiring_patch`

## Review Kurallari

1. Yeni patch once bu belgeye gore siniflandirilir.
2. `business_logic_override` sinifindaki yeni dosyalar reddedilir.
3. Yeni overlay dosyasi ancak yukaridaki izinli kategorilerden birine
   girdigi ve queue patch ile cozulmedigi durumda kabul edilir.
4. Her yeni upstream dokunusunda su soru sorulur:
   - bu degisiklik platform katmaninda cozulur mu
   - bu degisiklik runtime config ile cozulur mu
   - bu degisiklik yeni bir adapter veya contract ile cozulur mu

## Referanslar

- `platform/patch-policy.md`
- `platform/patch-inventory.csv`
- `platform/contracts/directory-model.yaml`
- `platform/contracts/registration-state-machine.yaml`
