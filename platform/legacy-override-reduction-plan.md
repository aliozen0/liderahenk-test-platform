# Legacy Override Reduction Plan

Bu belge, `services/liderapi/wiring/patches/overlay` ve
`services/liderui/wiring/patches/overlay` altinda kalan legacy override
yuzeyini platform vizyonuna uygun sekilde azaltmak icin calisma plani ve
mevcut durum ozeti olarak tutulur.

## Hedef

- Stock LiderAhenk davranisina en yakin sonucu platform katmaninda uretmek
- Full file override yerine `queue` tabanli ince upstream patch kullanmak
- UI view copy ve business-logic override sayisini sistematik olarak azaltmak
- Her iterasyonda hangi override kaldigi ve neden kaldigi net olarak izlenebilir olsun

## Bu Iterasyonda Tamamlananlar

1. `liderapi` tarafinda `AgentService.java` overlay kopyasi kaldirildi.
   - Yeni durum: `services/liderapi/wiring/patches/queue/010-agent-service-platform-seams.patch`
   - Sebep: bu dosya davranis olarak gerekliydi ama tam sinif kopyasi gerekmiyordu.
2. `liderui` tarafinda `src/router/index.js` overlay kopyasi kaldirildi.
   - Yeni durum: `services/liderui/wiring/patches/queue/010-router-feature-gates.patch`
   - Sebep: router davranisi platform guard ve feature gate ile queue patch olarak tasinabiliyor.
3. Kalan riskli yuzeyi izlemek icin `make audit-platform` komutu eklendi.

## Son Durum

### LiderAPI

1. `services/liderapi/wiring/patches/queue/020-ldap-service-v1-surface.patch`
2. `services/liderapi/wiring/patches/queue/021-ldap-service-provider-extraction.patch`
   - Durum: `LDAPServiceImpl` full override'i kaldirildi
   - Sonuc: LDAP admin bind ve presence mantigi provider/queue patch modeline tasindi

3. `services/liderapi/wiring/patches/queue/030-dashboard-service-metrics-provider.patch`
   - Durum: `DashboardService.java` overlay kopyasi kaldirildi
   - Neden basarili oldu: bilgisayar sayim mantigi `DashboardComputerMetricsProvider` seam'ine zaten ayrilmisti

4. `services/liderapi/wiring/patches/queue/040-plugin-task-service-feature-catalog.patch`
   - Durum: `PluginTaskService.java` overlay kopyasi kaldirildi
   - Neden basarili oldu: gorev filtreleme mantigi `FeatureCatalogProvider` seam'ine zaten ayrilmisti

5. `services/liderapi/wiring/patches/queue/050-plugin-service-feature-catalog.patch`
   - Durum: `PluginService.java` overlay kopyasi kaldirildi
   - Neden basarili oldu: plugin, task ve profile seed/filter mantigi `FeatureCatalogProvider` ve `V1CatalogSeedService` seam'lerine zaten ayrilmisti

Kalan `liderapi` overlay yuzeyi artik yalnizca bilinclı olarak korunan
siniflandirilmis dosyalardan olusur:

- `bootstrap_hook`
  - `tr/org/lider/Lider2Application.java`
- `wiring_patch`
  - `tr/org/lider/LiderCronJob.java`
- `compat_fix`
  - `tr/org/lider/dto/AgentDTO.java`
  - `tr/org/lider/entities/CommandExecutionImpl.java`
  - `tr/org/lider/entities/OperationLogImpl.java`
  - `tr/org/lider/entities/ProfileImpl.java`
  - `tr/org/lider/repositories/AgentInfoCriteriaBuilder.java`
  - `tr/org/lider/security/CustomPasswordEncoder.java`
  - `tr/org/lider/services/TaskService.java`
- `platform_extension`
  - `tr/org/lider/services/AgentInventorySyncService.java`
  - `tr/org/lider/services/AgentPresenceService.java`

Bu dosyalar "kalan riskli buyuk override" degil; platform sinirinda bilincli
olarak korunan bootstrap, compatibility veya additive extension yuzeyleridir.

### LiderUI

4. `services/liderui/wiring/patches/queue/020-computer-group-management-network-role.patch`
   - Durum: `ComputerGroupManagement.vue` full view copy'si kaldirildi
   - Neden basarili oldu: delta tek satirlik role genisletmesiydi, queue patch'e dogrudan indirilebildi

5. `services/liderui/wiring/patches/queue/030-security-management-network-only.patch`
   - Durum: `SecurityManagementPage.vue` full view copy'si kaldirildi
   - Neden basarili oldu: platform farki USB yuzeyini kapatip yalnizca `network-manager` gorevini birakmakti

6. `services/liderui/wiring/patches/queue/040-system-management-v1-surface.patch`
   - Durum: `SystemManagementPage.vue` full view copy'si kaldirildi
   - Neden basarili oldu: helper extraction sonrasi delta, queue patch ile tasinabilecek kadar kuculdu

7. `services/liderui/wiring/patches/queue/050-computer-management-v1-surface.patch`
   - Durum: `ComputerManagement.vue` full view copy'si kaldirildi
   - Neden basarili oldu: agent count, context-menu ve system-action mantigi helper modullere ayrildigi icin kalan delta queue patch'e tasinabildi

8. `services/liderui/wiring/patches/queue/060-role-management-feature-registry.patch`
   - Durum: `RoleManagement.js` overlay kopyasi kaldirildi
   - Neden basarili oldu: stock role facade platform guard modulune ince queue patch ile delege edilebildi

9. `services/liderui/extensions/src/services/FeatureFlags.js`
   - Durum: `FeatureFlags.js` overlay kopyasi kaldirildi
   - Neden basarili oldu: upstream dosyasi olmadigi icin bu yuzey additive extension source olarak tasinabildi

UI tarafinda overlay kopya kalmamistir.

## Adim Adim Yol Haritasi

### Faz A: Queue Patch'e Donusum

Amaç: davranis korunurken overlay kopya sayisini azaltmak.

Adimlar:
- queue patch'e cevrilebilecek her dosyayi tespit et
- upstream raw dosya ile diff al
- overlay kopyasini sil
- ayni degisikligi `queue/*.patch` altina tasi
- `prepare_component_source.sh` ile patch apply testi yap

Kabul:
- Ayni davranis korunmali
- overlay dosya sayisi azalmali

### Faz B: Presence ve Directory Truth Seami (Tamamlandi)

Amaç: `LDAPServiceImpl` icindeki platform mantigini dis servis katmanina cekmekti.

Tamamlananlar:
- `AgentPresenceService` etrafinda resolver seam acildi
- LDAP entry online hesaplamasi provider modeline tasindi
- `setParams()` icindeki feature-profile branch'i queue patch katmanina indirildi
- `LDAPServiceImpl` full overlay olmaktan cikarildi

Kabul:
- `LDAPServiceImpl` full overlay olmaktan cikti
- agent tree, dashboard ve agent list ayni presence truth'u kullanmali

### Faz C: UI View Copy Azaltimi

Amaç: view copy ile davraniş fork etmeyi bitirmek.

Adimlar:
- context-menu kararlarini `platform/menus`
- route/feature gating'i `platform/routes` ve `platform/guards`
- gorev destek matrisini `platform/feature-registry`
- stock `ComputerManagement` akisini bozmayacak ince wrapper modeline gec

Kabul:
- tam sayfa `.vue` kopyalari azaltilmali
- stock UI ile platform davranisi ayri katmanlarda izlenmeli

### Faz C.1: Shared Helper Extraction

Durum:
- `services/liderui/extensions/src/platform/computer/agentInfoActions.js`
- `services/liderui/extensions/src/platform/computer/pluginTaskCatalog.js`
- `services/liderui/extensions/src/platform/computer/agentCounts.js`
- `services/liderui/extensions/src/platform/menus/computerTree.js`

Bu helper'lar eklendi ve agir UI view copy'leri queue patch'e indirilecek kadar
kucultuldu. Bu tur sonunda UI tarafinda agir view copy kalmadi.

### Faz D: Audit ve Release Gate

Amaç: yeni legacy override birikimini engellemek.

Adimlar:
- `make audit-platform` her PR'da kosulsun
- `patch-inventory.csv` guncel tutulmak zorunda olsun
- `full_override` kategorisindeki dosyalar icin gerekce zorunlu olsun

Kabul:
- izinsiz yeni full override eklenememeli

## Adim 12 Sonucu

Bu iterasyon sonunda:

- agir UI view copy kalmadi
- service seviyesinde `liderapi` overlay kalmadi
- tum davranissal farklar `queue_patch`, `platform_extension`, `runtime_hook`
  veya `compat_fix` sinifina indirildi
- kalan overlay yuzeyi yalnizca bilinclı bootstrap ve compatibility katmani
  olarak siniflandirildi

Bu reduction dalinda artik "zorunlu olarak sokulecek buyuk override" kalmadi.
Sonraki odak, bu kalan bootstrap/compat yuzeyleri icin gerekirse ADR ve
upstream seam acma firsatlarini izlemek olacak; acil refactor borcu degiller.

## Adim 13 Sonucu

Kalan overlay dosyalari final siniflarina kilitlendi ve envantere su
target-state adlariyla islendi:

- `accepted_overlay_bootstrap`
- `accepted_overlay_wiring`
- `accepted_overlay_compat`
- `accepted_overlay_extension`

Referans:
- `platform/remaining-overlay-classification.md`

## Adim 14 Sonucu

Kapanis dogrulamasi tamamlandi.

Kanıtlar:

- `make audit-platform`
  - `remaining heavy overrides: 0`
- `prepare_component_source.sh liderui`
  - basarili
- `prepare_component_source.sh liderapi`
  - basarili
- `docker compose ... build liderapi`
  - basarili

Bu reduction serisinin final durumu:

- UI overlay kopyasi yok
- agir override yok
- `liderapi` service overlay'i yok
- kalan overlay yüzeyi yalnizca final siniflandirilmis bootstrap, compat,
  wiring ve additive extension dosyalarindan olusuyor

Bu seri burada kapanmistir.
