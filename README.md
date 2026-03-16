# 🛡️ LiderAhenk Test Platform

> **Pardus LiderAhenk** için konteyner tabanlı, tam otomatik test ortamı.  
> Tek komutla ayağa kalkar. Gerçek servisleri çalıştırır. Her şeyi test eder.

```bash
make dev-fidelity   # Kanonik kabul profili
```

---

## İçindekiler

- [Nedir Bu Proje?](#nedir-bu-proje)
- [Mimari](#mimari)
- [Servisler](#servisler)
- [Gereksinimler](#gereksinimler)
- [Hızlı Başlangıç](#hızlı-başlangıç)
- [Dizin Yapısı](#dizin-yapısı)
- [Makefile Komutları](#makefile-komutları)
- [Test Katmanları](#test-katmanları)
- [Gözlemlenebilirlik](#gözlemlenebilirlik)
- [Senaryo Motoru](#senaryo-motoru)
- [ACL Adapter Katmanı](#acl-adapter-katmanı)
- [Güvenlik](#güvenlik)
- [Bilinen Kısıtlamalar ve Çözümler](#bilinen-kısıtlamalar-ve-çözümler)
- [Katkı](#katkı)

---

## Nedir Bu Proje?

[Pardus LiderAhenk](https://github.com/Pardus-LiderAhenk), Pardus Linux sistemlerini merkezi olarak yönetmek için kullanılan açık kaynaklı bir platform. Lider sunucusu + Ahenk ajanları üzerinden çalışır.

Bu proje, LiderAhenk'i **gerçek bir sunucuya kurmak zorunda kalmadan** test edebilmek için tasarlanmış bir konteyner ortamıdır.

### Ne Sağlar?

| Sorun | Çözüm |
|---|---|
| LiderAhenk test etmek için gerçek Pardus sunucusu gerekiyor | `make dev-fast` ile her şey dizüstü bilgisayarda çalışır |
| Yeni sürüm çıktı, bir şeyler bozuldu mu? | `make test-contract` 5 dakikada yanıt verir |
| 100 ajan aynı anda bağlanabilir mi? | `make test-scale N=100` bunu ölçer |
| Ağ kesilince mesaj kayboluyor mu? | Toxiproxy kaos testleri bunu kanıtlar (Oturum 8) |
| Bu imajda CVE var mı? | CI pipeline her push'ta Trivy ile tarar (Oturum 7) |

---

## Mimari

```
┌─────────────────────────────────────────────────────────────────┐
│                    liderahenk_external                          │
│                  ┌──────────┐  ┌──────────┐                    │
│                  │ Lider UI │  │ liderapi │                    │
│                  │  :3001   │  │  :8082   │                    │
│                  └────┬─────┘  └────┬─────┘                    │
└───────────────────────┼─────────────┼────────────────────────── ┘
                        │             │
┌───────────────────────┼─────────────┼────────────────────────── ┐
│              liderahenk_core (internal — dışa kapalı)           │
│         ┌─────────────┐  ┌──────────┐  ┌─────────┐             │
│         │  lider-core │  │ MariaDB  │  │  LDAP   │             │
│         │   (Karaf)   │  │  :3306   │  │  :1389  │             │
│         └──────┬──────┘  └──────────┘  └─────────┘             │
└────────────────┼────────────────────────────────────────────────┘
                 │ XMPP (5222)
┌────────────────┼────────────────────────────────────────────────┐
│              liderahenk_agents                                  │
│         ┌─────┴──────┐   ┌─────────────────────────────┐       │
│         │  ejabberd  │   │  ahenk-001 ... ahenk-N      │       │
│         │  :5222     │   │  (XMPP bağlantılı, ölçekli) │       │
│         └────────────┘   └─────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
                 │
┌────────────────┼────────────────────────────────────────────────┐
│              liderahenk_obs                                     │
│   ┌────────────┐  ┌─────────┐  ┌──────┐  ┌────────────────┐   │
│   │ Prometheus │  │ Grafana │  │ Loki │  │ cAdvisor/OTel  │   │
│   │   :9090    │  │  :3000  │  │:3100 │  │                │   │
│   └────────────┘  └─────────┘  └──────┘  └────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 4 Katmanlı Tasarım

| Katman | Sorumluluk |
|---|---|
| **L1 — Platform** | Docker ağları, bootstrap, registration orchestration, healthcheck'ler |
| **L2 — Core** | Lider sunucusu, LDAP, ejabberd, MariaDB |
| **L3 — Agents** | Provisioner + ölçeklenebilir Ahenk ajanları |
| **L4 — Observability** | Metrik, log, trace toplama ve görselleştirme |

### Çalışma Profilleri

| Profil | Hedef | Komut |
|---|---|---|
| `dev-fast` | Hızlı geliştirme ve smoke testi | `make dev-fast` |
| `dev-fidelity` | Stock kurulum paritesine en yakın kabul profili | `make dev-fidelity` |

---

## Servisler

| Servis | İmaj | Port | Açıklama |
|---|---|---|---|
| **mariadb** | `mariadb:10.11` | iç ağ | liderapi veritabanı |
| **ldap** | `bitnamilegacy/openldap:latest` | `127.0.0.1:1389` | Kullanıcı + ajan dizini |
| **ejabberd** | `ejabberd/ecs:24.02` | `127.0.0.1:15280` | XMPP mesajlaşma (API) |
| **lider-core** | sıfırdan build | iç ağ | Karaf/OSGi yönetim sunucusu |
| **liderapi** | sıfırdan build | `127.0.0.1:8082` | REST API (JWT auth) |
| **lider-ui** | sıfırdan build | `127.0.0.1:3001` | Vue.js web arayüzü |
| **provisioner** | sıfırdan build | — | LDAP + XMPP toplu kayıt |
| **ahenk** | sıfırdan build | — | Ölçeklenebilir Ahenk ajanı |
| **prometheus** | `prom/prometheus` | `127.0.0.1:9090` | Metrik toplama |
| **grafana** | `grafana/grafana` | `127.0.0.1:3000` | Dashboard |
| **loki** | `grafana/loki` | `127.0.0.1:3100` | Log toplama |
| **cadvisor** | `gcr.io/cadvisor` | iç ağ | Konteyner metrikleri |

> ⚠️ **Ejabberd versiyon kilidi:** `EJABBERD_VERSION=24.02` sabit tutulmalı.  
> 24.12 → 25.03 güncellemesi Mnesia bozulması ve SASL auth hatasına yol açıyor ([issue #4366](https://github.com/processone/ejabberd/issues/4366)).

---

## Gereksinimler

| Araç | Min. Versiyon |
|---|---|
| Docker Engine | 25.0+ |
| Docker Compose | v2.24+ |
| Python | 3.11+ |
| Java JDK | 21 (Temurin) |
| Maven | 3.9+ |
| Node.js | 16.x |
| Yarn | 1.22+ |
| Disk | ~10 GB (imajlar dahil) |
| RAM | 8 GB+ önerilen |

---

## Hızlı Başlangıç

### 1 — Klonla

```bash
git clone https://github.com/<kullanici>/liderahenk-test-platform.git
cd liderahenk-test-platform
```

### 2 — Ortam değişkenlerini ayarla

```bash
cp .env.example .env
# .env dosyasını düzenle — tüm DEGISTIR değerlerini doldur
```

Kritik değişkenler:

```bash
LDAP_ADMIN_PASSWORD=güçlü-şifre
MYSQL_ROOT_PASSWORD=güçlü-şifre
XMPP_ADMIN_PASS=güçlü-şifre
LIDER_PASS=lider-admin-şifresi   # JWT auth için
```

### 3 — Docker ağlarını oluştur (ilk kurulumda)

```bash
make network-init
```

### 4 — Sistemi başlat

```bash
# Temel sistem (Lider + 10 Ahenk)
make dev-fast

# Gözlemlenebilirlik ile (stock kurulum paritesine daha yakın)
make dev-fidelity

# Tüm profiller (tracing dahil)
make dev-full
```

### 5 — Doğrula

```bash
make health          # Servis sağlığı
make token           # JWT token al
make agents          # Ajan listesi
make test-contract   # 28 sözleşme testi
make test-integration # 9 entegrasyon testi
```

### 6 — Arayüzler

| Arayüz | Adres | Kimlik |
|---|---|---|
| Lider UI | http://localhost:3001 | lider-admin / .env'deki LIDER_PASS |
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Jaeger | http://localhost:16686 | — |

---

## Dizin Yapısı

```
liderahenk-test/
├── compose/
│   ├── compose.core.yml        # L1+L2: ağlar, mariadb, ldap, ejabberd
│   ├── compose.lider.yml       # L2: lider-core, liderapi, lider-ui
│   ├── compose.agents.yml      # L3: provisioner, ahenk (ölçekli)
│   ├── compose.obs.yml         # L4: prometheus, grafana, loki, cadvisor
│   ├── compose.tracing.yml     # L4: jaeger, otel-collector
│   └── compose.chaos.yml       # Kaos: toxiproxy (Oturum 8)
│
├── services/
│   ├── liderapi/               # Maven multi-stage Dockerfile
│   │   ├── Dockerfile
│   │   └── lider.properties    # Spring Boot config (jwt.secret, DB, LDAP)
│   ├── liderui/                # Vue.js + Nginx Dockerfile
│   │   ├── Dockerfile
│   │   └── nginx.conf          # API proxy + SPA routing
│   ├── lidercore/              # .deb paket konteynerizasyon
│   │   ├── Dockerfile
│   │   └── entrypoint-core.sh  # systemd bypass, Karaf foreground
│   ├── ahenk/                  # Python multi-stage Dockerfile
│   │   ├── Dockerfile
│   │   └── entrypoint.sh       # jitter/backoff, dinamik ahenk.conf
│   ├── provisioner/            # LDAP + XMPP toplu kayıt
│   │   ├── Dockerfile
│   │   └── provision.py        # idempotent, bitnamilegacy port 1389
│   ├── ejabberd/
│   │   ├── ejabberd.yml        # vhost, mod_http_api, mod_register
│   │   └── entrypoint-ejabberd.sh  # lider_sunucu auto-register
│   ├── ldap/
│   │   ├── schema/liderahenk.ldif  # pardusAccount, pardusLider objectClass
│   │   └── seed/admin-user.ldif
│   └── mariadb/
│       └── init.sql            # config_params seed data
│
├── adapters/                   # ACL Anti-Corruption Layer
│   ├── lider_api_adapter.py    # JWT auth + REST (tersine mühendislik)
│   ├── xmpp_message_adapter.py # ejabberd HTTP API
│   ├── ldap_schema_adapter.py  # bitnamilegacy port 1389
│   └── reverse_engineering/
│       └── openapi_draft.yaml  # bytecode analizinden üretilen API şeması
│
├── contracts/                  # Sözleşme testleri (28 test)
│   ├── conftest.py
│   ├── test_rest_contract.py
│   ├── test_ldap_contract.py
│   └── test_xmpp_contract.py
│
├── orchestrator/               # Test senaryo motoru
│   ├── main.py                 # ScenarioRunner
│   ├── cli.py                  # CLI arayüzü
│   └── scenarios/
│       ├── basic_task.yml
│       ├── registration_test.yml
│       └── scale_test.yml
│
├── tests/                      # Entegrasyon + ölçek testleri
│   ├── test_integration.py     # 9 pytest testi
│   ├── test_scale.py           # @pytest.mark.scale
│   └── test_session*.sh        # Oturum doğrulama betikleri
│
├── observability/
│   ├── prometheus/
│   │   ├── prometheus.yml      # 5 scrape target
│   │   └── alerts.yml          # 5 SLO alert kuralı
│   ├── grafana/
│   │   ├── provisioning/       # datasource + dashboard auto-provision
│   │   └── dashboards/
│   │       └── liderahenk-slo.json  # 4 panelli SLO dashboard
│   ├── loki/
│   │   └── loki-config.yml     # 72h retention
│   └── otel/
│       └── otel-config.yml     # OTLP → Jaeger
│
├── .env.example                # Tüm ortam değişkenleri
├── .gitignore
├── Makefile                    # Tüm komutlar
├── requirements-test.txt
└── README.md
```

---

## Makefile Komutları

```bash
# ── Başlatma ──────────────────────────────────────────────────
make network-init        # İlk kurulumda Docker ağlarını oluştur
make dev-fast            # Hızlı geliştirme profili
make dev-fidelity        # Gözlemlenebilirlik ile kabul profili
make dev-full            # + Jaeger + OTel Collector
make dev-scale N=50      # 50 Ahenk ajanı ile başlat

# ── Durdurma / Temizleme ──────────────────────────────────────
make stop                # Konteynerleri durdur
make clean               # Konteyner + volume temizle
make clean-hard          # İmaj + Mnesia kalıntıları dahil tam temizle

# ── Build ─────────────────────────────────────────────────────
make build-lider         # Lider servislerini yeniden build et
make build               # Tüm servisleri build et

# ── Hızlı Erişim ──────────────────────────────────────────────
make health              # Tüm servis durumu
make token               # JWT token al (otomatik)
make agents              # Authenticated ajan listesi
make status              # docker compose ps

# ── Testler ───────────────────────────────────────────────────
make test-contract       # 28 sözleşme testi (pytest)
make test-integration    # 9 entegrasyon testi (pytest)
make test-scale N=50     # Ölçek testi (50 ajan)

# ── Senaryo Motoru ────────────────────────────────────────────
make run-scenario S=basic_task.yml
make run-scenario S=registration_test.yml
make run-scenario S=scale_test.yml

# ── Log ───────────────────────────────────────────────────────
make logs SVC=liderapi
make logs SVC=lider-core
make logs SVC=ejabberd
```

---

## Test Katmanları

Bu proje 4 katmanlı test stratejisi uygular:

```
┌─────────────────────────────────────┐
│  Kaos Testleri (Oturum 8)           │  ← Toxiproxy, ağ arızaları
├─────────────────────────────────────┤
│  Ölçek Testleri                     │  ← make test-scale N=100
├─────────────────────────────────────┤
│  Entegrasyon Testleri (9 test)      │  ← make test-integration
├─────────────────────────────────────┤
│  Sözleşme Testleri (28 test)        │  ← make test-contract
└─────────────────────────────────────┘
```

### Sözleşme Testleri (28 test)

```bash
make test-contract
# ✅ 10 REST contract testi (liderapi endpoint'leri)
# ✅  9 LDAP contract testi (bitnamilegacy, port 1389)
# ✅  9 XMPP contract testi (ejabberd HTTP API)
```

Sözleşme testleri **davranışı** test eder, iş mantığını değil. LiderAhenk güncellendiğinde ilk burada bozulma tespit edilir.

### Entegrasyon Testleri (9 test)

```bash
make test-integration
# ✅ registration_test senaryosu
# ✅ basic_task senaryosu
# ✅ Ajan bağlantı oranı >= %90
# ✅ LDAP ajan sayısı doğrulama
# ✅ Authenticated API çağrısı
# ✅ API idempotency
```

### Ölçek Testleri

```bash
# 50 ajan ile test
make clean-hard
AHENK_COUNT=50 make dev-fast
make test-scale N=50
```

---

## Gözlemlenebilirlik

### SLO Alert Kuralları

| Alert | Koşul | Seviye |
|---|---|---|
| `AgentRegistrationFailed` | Kayıt oranı < %95 | Critical |
| `XMPPConnectionDrop` | Bağlı ajan < %90 | Critical |
| `LiderApiHighErrorRate` | HTTP 5xx > %5 | Warning |
| `TaskDeliveryLatencyHigh` | p95 > 5sn | Warning |

### Grafana Dashboard — 4 Panel

```
http://localhost:3000 → Dashboards → LiderAhenk SLO Dashboard
```

- **Bağlı Ahenk Ajan Sayısı** — ejabberd metriği, anlık
- **liderapi İstek/sn ve Hata Oranı** — HTTP traffic
- **lider-core JVM Heap** — Karaf bellek kullanımı
- **Görev Gecikmesi p95** — uçtan uca gecikme

---

## Senaryo Motoru

YAML tabanlı test senaryoları. Token yönetimi otomatik — manuel curl gerekmez.

```bash
# Mevcut senaryoları listele
python3 orchestrator/cli.py --list

# Senaryo koştur
make run-scenario S=basic_task.yml
```

Yeni senaryo eklemek:

```yaml
# orchestrator/scenarios/my_scenario.yml
name: my_test
description: "Açıklama"
setup:
  min_agents: 5
steps:
  - name: send_task
    action: send_task
    params:
      task_type: ECHO
      target: all
assertions:
  - type: no_errors
```

---

## ACL Adapter Katmanı

Lider servisleri için Anti-Corruption Layer. Dış sistemlerin detaylarını test kodundan izole eder.

```
tests/                          adapters/
  test_integration.py  ──────→  lider_api_adapter.py   ──→ liderapi:8082
  test_contract.py     ──────→  xmpp_message_adapter.py ──→ ejabberd:15280
                       ──────→  ldap_schema_adapter.py  ──→ ldap:1389
```

LiderAhenk API değiştiğinde **sadece adapter güncellenir**, test kodu dokunulmaz.

> ⚠️ **Not:** Resmi OpenAPI belgesi mevcut değil. API şeması bytecode analizi ve HTTP trafik yakalama ile tersine mühendislik uygulanarak `adapters/reverse_engineering/openapi_draft.yaml` dosyasına belgelenmiştir.

---

## Güvenlik

### LiderAhenk CVE Geçmişi

Bu projenin güvenlik testleri teorik değil — gereklidir:

| CVE | Etki | Sürüm |
|---|---|---|
| CVE-2021-3825 | Yetkisiz API ile LDAP kimlik bilgisi sızıntısı | ≤ 2.1.15 |
| CVE-2026-26023 | Uzaktan Kod İçerme (RCI) | 3.0.0 – 3.3.1 |

### Uygulanan Önlemler

- `bitnamilegacy/openldap` — non-root kullanıcı (osixia terk edildi, CVE dolu)
- Ahenk konteynerleri `USER ahenk` ile çalışır (root değil)
- MariaDB dışa port açmaz
- `liderahenk_core` ağı `internal: true` (internet erişimi yok)
- ejabberd `mod_register` sadece iç ağa kısıtlı
- JWT secret: 640-bit Base64, HS512 (minimum 512 bit)

### Planlanan (Oturum 7-8)

- [ ] Trivy CVE tarama (CI pipeline)
- [ ] Hadolint Dockerfile lint
- [ ] pip-audit Python bağımlılık tarama
- [ ] Syft SBOM üretimi
- [ ] cosign imaj imzalama
- [ ] `read_only: true` filesystem
- [ ] `cap_drop: [ALL]`

---

## Bilinen Kısıtlamalar ve Çözümler

### 1. Resmi Docker İmajı Yok

Pardus-LiderAhenk GitHub repolarında Dockerfile mevcut değil. Bu proje tüm Lider servislerini sıfırdan build eder:

- `liderapi` → Maven multi-stage (WAR çıktısı, JAR değil)
- `liderui` → Vue.js + Nginx (node-sass → dart-sass)
- `lidercore` → debian:bookworm + .deb + systemd bypass

### 2. bitnami/openldap Docker Hub'dan Kaldırıldı

`bitnamilegacy/openldap:latest` kullanılır. Port **1389** (non-root default) — 389 değil.

### 3. OpenAPI Belgesi Yok

Lider API şeması `adapters/reverse_engineering/openapi_draft.yaml` dosyasında bytecode analizinden üretilmiştir.

### 4. Ejabberd Versiyon Kilidi

```bash
EJABBERD_VERSION=24.02  # .env'de sabit — latest kullanma!
```

### 5. ilk Kurulumda Ağlar Yok

```bash
make network-init  # Bir kez çalıştır
```

---

## Katkı

### Yeni Oturum Eklerken

1. `compose/` altına yeni profil ekle
2. `services/` altına Dockerfile yaz
3. Adapter varsa `adapters/` altına ekle
4. `contracts/` altına sözleşme testi yaz
5. `tests/test_sessionX.sh` ile doğrula
6. Makefile'a hedef ekle

### Test Çalıştırma Sırası

```bash
make test-contract      # Önce sözleşme
make test-integration   # Sonra entegrasyon
make test-scale N=20    # Son olarak ölçek
```

---

## Lisans

Bu proje [LGPL-3.0](LICENSE) lisansı altında dağıtılmaktadır.  
LiderAhenk bileşenleri kendi lisanslarına tabidir.

---

<div align="center">

**Pardus LiderAhenk Test Platform**  
`make dev-fidelity` → kabul profili hazır.

</div>
