# Remaining Overlay Classification

Bu belge, reduction programi sonrasinda bilinclı olarak korunan overlay
yuzeyini ve bunlarin neden kaldigini final durumda listeler.

## Kapsam

Bu listede yer alan dosyalar artik "gecici buyuk override" degil;
platform sinirinda kabul edilmis su kategorilerden birine aittir:

- `accepted_overlay_bootstrap`
- `accepted_overlay_wiring`
- `accepted_overlay_compat`
- `accepted_overlay_extension`

## LiderAPI

### accepted_overlay_bootstrap

- `tr/org/lider/Lider2Application.java`
  - Uygulama boot sirasinda platform seam'i acmak icin tutulur.

### accepted_overlay_wiring

- `tr/org/lider/LiderCronJob.java`
  - Cron gürültüsünü ve platform delegasyonunu kontrollu sekilde tutar.

### accepted_overlay_compat

- `tr/org/lider/dto/AgentDTO.java`
  - Agent status alan uyumlulugu.
- `tr/org/lider/entities/CommandExecutionImpl.java`
  - `dn` kolon uyumlulugu.
- `tr/org/lider/entities/OperationLogImpl.java`
  - blob kolon uyumlulugu.
- `tr/org/lider/entities/ProfileImpl.java`
  - blob kolon uyumlulugu.
- `tr/org/lider/repositories/AgentInfoCriteriaBuilder.java`
  - agent filtre query uyumlulugu.
- `tr/org/lider/security/CustomPasswordEncoder.java`
  - parola hash uyumlulugu.
- `tr/org/lider/services/TaskService.java`
  - eksik/partial node request validation guard.

### accepted_overlay_extension

- `tr/org/lider/services/AgentInventorySyncService.java`
  - additive inventory sync servisi.
- `tr/org/lider/services/AgentPresenceService.java`
  - additive presence provider servisi.

## Kural

Bu listedeki dosyalar yeni refactor hedefi olarak degil, final siniflandirilmis
platform yuzeyi olarak ele alinir. Gelecekte bunlar ancak:

1. upstream tarafinda esdeger bir seam acilirsa
2. ayni davranis queue patch ile daha net tasinabiliyorsa
3. compat ihtiyaci ortadan kalkarsa

yeniden degerlendirilir.
