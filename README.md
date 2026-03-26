# LiderAhenk Test Platform

> LiderAhenk'i fork'lamadan, gercek sistem bilesenlerini disaridan saran,
> tek komutla ayaga kalkan, tekrar uretilebilir runtime-first laboratuvar
> platformu.

```bash
make dev-fidelity N=10
```

## Icindekiler

- [Proje Nedir?](#proje-nedir)
- [Temel Hedef](#temel-hedef)
- [Mimari](#mimari)
- [Calisma Profilleri](#calisma-profilleri)
- [Servisler](#servisler)
- [Hizli Baslangic](#hizli-baslangic)
- [Dogrulama Akisi](#dogrulama-akisi)
- [Arayuzler](#arayuzler)
- [Repo Haritasi](#repo-haritasi)
- [Make Hedefleri](#make-hedefleri)
- [Observability](#observability)
- [Katki ve Gelistirme Notlari](#katki-ve-gelistirme-notlari)

## Proje Nedir?

Bu repo, LiderAhenk'in ic mantigini degistiren yeni bir urun ya da kalici bir
fork degildir. Amac, gercek LiderAhenk kurulumunu disaridan saran bir platform
kurmaktir.

Platformun ana gorevi:

- LDAP, MariaDB, ejabberd/XMPP, `lider-core`, `liderapi`, `lider-ui` ve Ahenk
  ajanlarini birlikte ayaga kaldirmak
- bunu tek komutla ve tekrar uretilebilir sekilde yapmak
- VM zorunlulugu olmadan `N` adet ajanla calisabilmek
- sistemin gercekten kullanilabilir olup olmadigini runtime uzerinden
  dogrulamak
- Grafana, Prometheus ve Loki ile runtime davranisini gorunur kilmak

Resmi vizyon ve urun hedefleri:

- [docs/platform_vizyonu.md](/home/huma/liderahenk-test/docs/platform_vizyonu.md)
- [docs/product-requirements.md](/home/huma/liderahenk-test/docs/product-requirements.md)

## Temel Hedef

Basari olcutu yalnizca konteynerlerin `running` olmasi degildir. Hedef, su
zincirin gercekten calismasidir:

1. core servisler kalkar
2. Ahenk ajanlari baslar
3. registration zinciri tamamlanir
4. ajanlar UI ve API uzerinden gorunur
5. task ve policy akislarina girebilir
6. observability katmani runtime durumunu gosterebilir

Onemli model:

- insan kullanici ve istemci/ajan ayni sey degildir
- directory yapisinda farkli koklerde tutulurlar
- platform runtime truth'u yalnizca resmi yuzeylerden okur

Runtime truth kaynaklari:

- LDAP
- ejabberd/XMPP
- MariaDB `c_agent` ve `c_config`
- `liderapi` dashboard / computer tree / agent list yuzeyleri
- Grafana / Prometheus / Loki telemetry yuzeyi

## Mimari

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         external platform                           │
│  bootstrap | provisioning | runtime checks | evidence | adapters   │
└─────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         LiderAhenk runtime                          │
│  lider-ui | liderapi | lider-core | MariaDB | LDAP | ejabberd      │
└─────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          ahenk agent pool                           │
│                    ahenk-001 ... ahenk-N                            │
└─────────────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           observability                             │
│                 Grafana | Prometheus | Loki                         │
└─────────────────────────────────────────────────────────────────────┘
```

Mimari modeli:

- upstream clone
- patch queue
- extension source
- runtime hooks
- orchestration

Bu modelin amaci, upstream urunu iceriden yeniden yazmak degil; disaridan
uyarlamak ve calistirmaktir.

## Calisma Profilleri

| Profil | Amac | Komut |
|---|---|---|
| `dev-fast` | hizli gelistirme, smoke ve temel runtime kontrolu | `make dev-fast` |
| `dev-fidelity` | ana kabul profili, observability ve operasyonel kontrol | `make dev-fidelity` |
| `dev-full` | tracing dahil genisletilmis profil | `make dev-full` |

## Servisler

| Servis | Rol |
|---|---|
| `mariadb` | LiderAhenk domain verisi |
| `ldap` | kullanici ve ajan dizini |
| `ejabberd` | XMPP mesajlasma ve presence |
| `lider-core` | merkezi yonetim cekirdegi |
| `liderapi` | REST API ve dashboard/domain yuzeyleri |
| `lider-ui` | web arayuzu |
| `provisioner` | bootstrap ve seed islemleri |
| `ahenk` | olceklenebilir agent runtime |
| `registration-orchestrator` | domain owner olmadan registration gozlemi ve evidence |
| `platform-exporter` | platform telemetry |
| `ejabberd-exporter` | ejabberd telemetry |
| `prometheus` | metric toplama |
| `grafana` | dashboard ve runtime gorunurlugu |
| `loki` | log toplama |

## Hizli Baslangic

### 1. Repo'yu hazirla

```bash
git clone <repo-url> liderahenk-test
cd liderahenk-test
cp .env.example .env
```

Gereken temel araclar:

- Docker Engine
- Docker Compose v2
- Python 3.11+

### 2. Temiz bir ortamla basla

```bash
make clean-hard
make network-init
```

### 3. Platformu kaldir

Hizli profil:

```bash
make dev-fast N=10
```

Ana kabul profili:

```bash
make dev-fidelity N=10
```

Tracing dahil:

```bash
make dev-full N=10
```

### 4. Runtime'i dogrula

Core runtime lane:

```bash
make test-runtime-core PROFILE=dev-fidelity N=10
```

Operasyonel runtime lane:

```bash
make test-runtime-operational PROFILE=dev-fidelity N=10
```

Olcek lane:

```bash
make test-runtime-scale N=10
```

Yardimci komutlar:

```bash
make health
make token
make agents
make status
```

## Dogrulama Akisi

Bu repoda oncelikli dogrulama sirasi runtime-first'tur.

### 1. Runtime Core

`make test-runtime-core`

Bu lane sunlari kontrol eder:

- compose stack kalkti mi
- konteynerler running mi
- healthcheck'ler yesil mi
- `liderapi` auth alinabiliyor mu
- LDAP, MariaDB ve ejabberd temel operasyonlari calisiyor mu

### 2. Runtime Operational

`make test-runtime-operational`

Bu lane sunlari kontrol eder:

- registration parity
- UI'de agent gorunurlugu
- task dispatch
- policy roundtrip
- observability hedefleri

### 3. Runtime Scale

`make test-runtime-scale N=10`

Bu lane, VM kullanmadan coklu Ahenk agent senaryosunu dogrular.

### 4. Destekleyici Testler

Runtime lane'lerin altinda destekleyici katmanlar da vardir:

- `make test-contract`
- `make test-integration`
- `make test-observability`
- `make test-e2e-management`
- `make test-acceptance PROFILE=dev-fidelity`

## Arayuzler

| Arayuz | Adres | Not |
|---|---|---|
| Lider UI | http://localhost:3001 | giris: `.env` icindeki `LIDER_USER` / `LIDER_PASS` |
| Lider API | http://localhost:8082 | dis erisim ucu |
| Grafana | http://localhost:3000 | varsayilan `admin / admin` |
| Prometheus | http://localhost:9090 | metrics ve target gorunumu |
| Jaeger | http://localhost:16686 | yalnizca `make dev-full` ile |

## Repo Haritasi

Aktif runtime/build truth icin ilk bakilacak yuzeyler:

- [Makefile](/home/huma/liderahenk-test/Makefile)
- [platform/active-surface-map.md](/home/huma/liderahenk-test/platform/active-surface-map.md)
- [platform/upstream-manifest.yaml](/home/huma/liderahenk-test/platform/upstream-manifest.yaml)
- [platform/bootstrap/bootstrap-manifest.yaml](/home/huma/liderahenk-test/platform/bootstrap/bootstrap-manifest.yaml)

Temel klasorler:

```text
compose/            docker compose katmanlari
services/           calisan servis Dockerfile ve wiring yuzeyi
platform/           platform governance, contracts, manifests
platform_runtime/   runtime validation ve reporting kodu
adapters/           anti-corruption / adapter katmani
orchestrator/       senaryo ve akis motoru
observability/      prometheus, grafana, loki konfigurasyonu
tests/              runtime, parity, observability ve kalite testleri
docs/               vizyon, gereksinim ve teknik dokumanlar
```

Not:

- `compose.platform.yml` aktif runtime katmanidir
- `platform/services/registration-orchestrator/` aktif platform servisidir
- `services/liderapi/patches/` ve `services/liderui/patches/` tek basina
  build truth kabul edilmez; aktif yuzey icin `wiring/patches` ve
  `extensions` alanlarina bakilir

## Make Hedefleri

### Baslatma

```bash
make dev-fast N=10
make dev-fidelity N=10
make dev-full N=10
make dev-scale N=20
```

### Temizlik ve durum

```bash
make stop
make stop-all
make clean
make clean-hard
make status
make logs SVC=liderapi
```

### Runtime ve kabul

```bash
make test-runtime-core PROFILE=dev-fast
make test-runtime-core PROFILE=dev-fidelity
make test-runtime-operational PROFILE=dev-fidelity
make test-runtime-scale N=10
make test-registration-parity
make test-acceptance PROFILE=dev-fidelity
```

### Yardimci testler

```bash
make test-contract
make test-integration
make test-observability
make test-e2e-smoke
make test-e2e-management
```

### Governance ve kalite

```bash
make audit-platform
make quality-report
make test-release-gate PROFILE=dev-fidelity
make verify-candidate COMPONENT=liderui REF=<upstream-ref>
```

### Baseline ve evidence

```bash
make validate-golden-baseline
make capture-golden-baseline
make diff-baseline
make validate-registration-evidence
```

## Observability

Bu platformda observability opsiyonel bir eklenti degil, resmi runtime
yuzeyidir.

Saglanan temel gorunurluk:

- Prometheus scrape target'lari
- Grafana dashboard'lari
- Loki log akislari
- platform ve ejabberd exporter metrikleri

Runtime kabulunde beklenen:

- dashboard'lar acilabilir olmali
- target'lar `up` olmali
- log akisi gorunmeli
- runtime karar raporu telemetry ile desteklenebilmeli

## Katki ve Gelistirme Notlari

Bu repoda yeni degisiklik yaparken once su sirayla okunmali:

1. [docs/platform_vizyonu.md](/home/huma/liderahenk-test/docs/platform_vizyonu.md)
2. [docs/product-requirements.md](/home/huma/liderahenk-test/docs/product-requirements.md)
3. [Makefile](/home/huma/liderahenk-test/Makefile)
4. [platform/active-surface-map.md](/home/huma/liderahenk-test/platform/active-surface-map.md)

Calisma kurali:

- once runtime foundation bozulmuyor mu diye bak
- yeni degisiklikte minimum patch ilkesini koru
- domain truth'u dogrudan sahteleme
- insan kullanici ile agent kimligini ayni kabul etme
- aktif patch yuzeyi icin [platform/patch-inventory.csv](/home/huma/liderahenk-test/platform/patch-inventory.csv) kaydini kontrol et

## Lisans

Bu proje [LGPL-3.0](LICENSE) lisansi altindadir. LiderAhenk bilesenleri kendi
lisanslarina tabidir.
