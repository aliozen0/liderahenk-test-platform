# LiderAhenk Test Platform

> LiderAhenk'i fork'lamadan, gercek sistem bilesenlerini disaridan saran,
> tek komutla ayaga kalkan, tekrar uretilebilir runtime-first laboratuvar
> platformu.

```bash
make dev-fidelity N=10
```

## Icindekiler

- [Proje Nedir?](#proje-nedir)
- [Mimari](#mimari)
- [Calisma Profilleri](#calisma-profilleri)
- [Servisler](#servisler)
- [Kurulum Oncesi Kontrol Listesi](#kurulum-oncesi-kontrol-listesi)
- [GitHub'dan Sifirdan Kurulum](#githubdan-sifirdan-kurulum)
- [Dogrulama Akisi](#dogrulama-akisi)
- [Arayuzler](#arayuzler)
- [Make Hedefleri](#make-hedefleri)
- [Sik Karsilasilan Sorunlar](#sik-karsilasilan-sorunlar)
- [Repo Haritasi](#repo-haritasi)
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
- `dev-fidelity` profilinde Grafana, Prometheus ve Loki ile runtime davranisini
  gorunur kilmak

Basari olcutu yalnizca konteynerlerin `running` olmasi degildir. Hedef, su
zincirin gercekten calismasidir:

1. core servisler kalkar
2. Ahenk ajanlari baslar
3. registration zinciri tamamlanir
4. ajanlar UI ve API uzerinden gorunur
5. task ve policy akislarina girebilir
6. observability katmani runtime durumunu gosterebilir

Resmi vizyon: [docs/platform_vizyonu.md](/home/huma/liderahenk-test/docs/platform_vizyonu.md)

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

Model: upstream clone → patch queue → extension source → runtime hooks → orchestration.
Amac, upstream urunu iceriden yeniden yazmak degil; disaridan uyarlamak ve
calistirmaktir.

## Calisma Profilleri

| Profil | Amac | Compose Stack | Komut |
|---|---|---|---|
| `dev-fast` | hizli gelistirme, smoke ve temel runtime kontrolu | core + lider + agents + platform | `make dev-fast` |
| `dev-fidelity` | ana kabul profili, observability ve operasyonel kontrol | core + lider + agents + platform + obs | `make dev-fidelity` |

`dev-fidelity` profilinde topology, parametrik seed ve scenario pack mantigini
da kullanabilirsin. Varsayilan topoloji:

| Alan | Varsayilan |
|---|---:|
| Managed endpoint | 10 |
| Operator | 3 |
| Directory user | 12 |
| User group | 4 |
| Endpoint group | 3 |
| Policy pack | `baseline-standard` |
| Session pack | `login-basic` |

Override ornekleri:

```bash
make dev-fidelity N=10
DIRECTORY_USER_COUNT=50 USER_GROUP_COUNT=6 make dev-fidelity N=10
PLATFORM_SCENARIO_PACKS=ui-user-policy-roundtrip make test-runtime-operational PROFILE=dev-fidelity N=10
```

## Servisler

| Servis | Rol | Profil |
|---|---|---|
| `mariadb` | LiderAhenk domain verisi | her iki profil |
| `ldap` | kullanici ve ajan dizini | her iki profil |
| `ldap-init` | LDAP sema ve kok dugum bootstrap | her iki profil |
| `ejabberd` | XMPP mesajlasma ve presence | her iki profil |
| `db-migrate` | MariaDB sema migrasyonu | her iki profil |
| `lider-core` | merkezi yonetim cekirdegi | her iki profil |
| `liderapi` | REST API ve dashboard/domain yuzeyleri | her iki profil |
| `lider-ui` | web arayuzu | her iki profil |
| `provisioner` | bootstrap ve seed islemleri | her iki profil |
| `ahenk` | olceklenebilir agent runtime | her iki profil |
| `registration-orchestrator` | registration gozlemi ve evidence | her iki profil |
| `prometheus` | metric toplama | yalnizca `dev-fidelity` |
| `grafana` | dashboard ve runtime gorunurlugu | yalnizca `dev-fidelity` |
| `loki` | log toplama | yalnizca `dev-fidelity` |
| `grafana-alloy` | log ve metric toplama agent'i | yalnizca `dev-fidelity` |
| `otel-collector` | OpenTelemetry collector | yalnizca `dev-fidelity` |
| `platform-exporter` | platform telemetry | yalnizca `dev-fidelity` |
| `ejabberd-exporter` | ejabberd telemetry | yalnizca `dev-fidelity` |
| `cadvisor` | konteyner kaynak metrikleri | yalnizca `dev-fidelity` |
| `mysqld-exporter` | MariaDB metrikleri | yalnizca `dev-fidelity` |

## Host Sistem Uyumlulugu

| Host sistem | Durum | Not |
|---|---|---|
| Ubuntu 22.04+ | onerilen | README komutlari dogrudan uygulanabilir |
| WSL2 + Ubuntu | desteklenir | Docker Desktop ya da host Docker ile birlikte kullanilabilir |
| Pardus 23 | desteklenir | Docker kurulumu Debian yolu ile yapilmalidir |

Pardus 23, Debian 12 tabanlidir. Docker kurulumu icin `debian` repo yolu ve
`bookworm` kod adi kullanilmalidir.

## Kurulum Oncesi Kontrol Listesi

- isletim sistemi: Ubuntu 22.04+, Pardus 23 ya da WSL2 icindeki Ubuntu
- Docker komutu: `docker`
- Compose komutu: `docker compose`
- Python ortami: `venv`
- shell: bash

Baslamadan once sunlarin hazir oldugundan emin ol:

- internet baglantin var
- Docker daemon calisiyor
- su portlar baska uygulamalar tarafindan kullanilmiyor:
  `1389`, `3001`, `8082`, `15280` (temel), `3000`, `3100`, `9090` (observability)
- ilk kurulumda image build ve package indirmeleri zaman alabilir

Kendi makinenin hazir olup olmadigini su komutlarla hizlica kontrol edebilirsin:

```bash
docker version
docker compose version
python3 --version
git --version
make --version
```

## GitHub'dan Sifirdan Kurulum

Bu bolum, repo daha yeni klonlanmisken izlenecek net kurulumu anlatir.

### 1. Temel sistem araclarini kur

Ubuntu, Pardus ya da WSL/Ubuntu icinde su paketleri kur:

```bash
sudo apt update
sudo apt install -y git make curl ca-certificates python3 python3-venv python3-pip
```

Sonra surumleri kontrol et:

```bash
python3 --version
git --version
make --version
```

Not:

- CI ortami `Python 3.11` kullanir
- yerelde en sorunsuz secenek `Python 3.11` olsa da, repo scriptleri modern
  `Python 3.x` ortamlariyla calisacak sekilde yazilmistir

### 2. Docker Engine ve Compose v2 kur

Eger `docker version` ve `docker compose version` zaten calisiyorsa bu adimi
atlayabilirsin.

Bu repo host makinede `docker compose` komutunu bekler. `docker-compose`
degil, Compose v2 plugin gereklidir.

#### 2A. Ubuntu 22.04+ ya da WSL2/Ubuntu

Ubuntu icin resmi Docker apt repo kurulumu:

```bash
sudo apt remove -y docker.io docker-compose docker-compose-v2 podman-docker containerd runc
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

#### 2B. Pardus 23

Pardus 23, Debian 12 tabanli oldugu icin Docker kurulumu Debian yolu ile
yapilmalidir. En guvenli yol, Docker'in Debian dokumanindaki repo kurulumunu
Pardus 23 icin `bookworm` kod adi ile uygulamaktir:

```bash
for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do sudo apt remove -y $pkg; done
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: bookworm
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Docker kurulduktan sonra servisi ve komutlari dogrula:

```bash
sudo systemctl status docker --no-pager
docker compose version
```

`docker` komutunu `sudo` kullanmadan calistirmak icin:

```bash
sudo groupadd docker || true
sudo usermod -aG docker $USER
newgrp docker
docker run hello-world
```

`newgrp docker` bazen yeterli olmayabilir. O durumda terminali kapatip yeniden
acman ya da oturumu kapatip tekrar girmen gerekir.

### 3. Repoyu GitHub'dan klonla

```bash
git clone https://github.com/aliozen0/liderahenk-test-platform.git
cd liderahenk-test-platform
```

Istersen klasor adini degistirebilirsin. Repo kodu klasor adina bagli degildir.

### 4. Python sanal ortami olustur

Repo icindeki Python yardimci scriptleri ve testler icin sanal ortam kullanmak
en temiz yoldur:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements-test.txt
```

Onemli:

- bu repoda varsayilan bagimlilik dosyasi `requirements.txt` degil,
  `requirements-test.txt` dosyasidir
- `bdist_wheel` hatasi aliyorsan once `pip install wheel` ya da
  `python -m pip install --upgrade pip setuptools wheel` calistir

### 5. Ortam dosyasini olustur

```bash
cp .env.example .env
```

Yerel deneme icin cogu durumda `.env` dosyasini oldugu gibi kullanabilirsin.
Ana alanlar:

- `AHENK_COUNT`: kac ajan baslatilacagini belirler
- `PLATFORM_RUNTIME_PROFILE`: varsayilan profil
- `LIDER_USER` ve `LIDER_PASS`: UI/API giris bilgisi
- `LDAP_ADMIN_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`: yerel ortam
  sifreleri

Zayif bir makinede ilk deneme icin `N=3` verebilirsin.

### 6. Docker aglarini olustur

```bash
make network-init
make network-check
```

Her sey dogruysa `OK ...` satirlari gorursun.

### 7. Ilk kez platformu calistir

Hizli profil:

```bash
make dev-fast N=3
```

Asil kabul profili:

```bash
make dev-fidelity N=10
```

Not:

- ilk calistirmada image build nedeniyle sure uzun olabilir
- sifirdan temizlemek icin `make clean-hard` calistirabilirsin

### 8. Platformun ayaga kalktigini kontrol et

```bash
make status
make health
make token
```

### 9. Tarayicidan giris yap

- Lider UI: `http://localhost:3001`
- Lider API: `http://localhost:8082`
- Grafana: `http://localhost:3000` (yalnizca `dev-fidelity`)
- Prometheus: `http://localhost:9090` (yalnizca `dev-fidelity`)

Varsayilan giris: `.env` icindeki `LIDER_USER` / `LIDER_PASS`, Grafana: `admin / admin`

### 10. Kurulumu test et

```bash
make test-runtime-core PROFILE=dev-fast N=3
make test-runtime-core PROFILE=dev-fidelity N=10
make test-runtime-operational PROFILE=dev-fidelity N=10
```

### 11. Durdur ve temizle

```bash
make stop          # servisleri durdur
make stop-all      # observability dahil her seyi durdur
make clean         # container + volume temizligi
make clean-hard    # image dahil tam temizlik
```

## Dogrulama Akisi

Bu repoda oncelikli dogrulama sirasi runtime-first'tur.

| Lane | Komut | Kontrol Ettigi |
|---|---|---|
| Runtime Core | `make test-runtime-core` | compose stack, healthcheck, auth, LDAP/DB/XMPP |
| Runtime Operational | `make test-runtime-operational` | registration, UI gorunurluk, task, policy, scenario |
| Release Gate | `make test-release-gate` | unit + runtime + acceptance + baseline + evidence + e2e |
| Scale | `make test-scale N=10` | coklu agent parity |
| API Health | `make test-api` | 43 endpoint, 11 modul |
| API Data | `make test-api-data` | API vs DB vs LDAP cross-validation |
| API Quick | `make test-api-quick` | 10 cekirdek endpoint |

Destekleyici testler: `test-contract`, `test-unit-gate`, `test-observability`,
`test-e2e`, `test-e2e-smoke`, `test-e2e-management`, `test-acceptance`

## Arayuzler

| Arayuz | Adres | Not |
|---|---|---|
| Lider UI | http://localhost:3001 | giris: `.env` icindeki `LIDER_USER` / `LIDER_PASS` |
| Lider API | http://localhost:8082 | dis erisim ucu |
| Swagger UI | http://localhost:8082/swagger-ui/index.html | JWT token gerekli |
| Swagger Proxy | http://localhost:9999/swagger-proxy.html | `make swagger` ile baslatilir |
| OpenAPI JSON | http://localhost:8082/v3/api-docs | 237 endpoint, OpenAPI 3.1.0 |
| LDAP | ldap://localhost:1389 | yerel LDAP sorgulari icin |
| Grafana | http://localhost:3000 | `admin / admin`, yalnizca `dev-fidelity` |
| Prometheus | http://localhost:9090 | yalnizca `dev-fidelity` |

Swagger UI icin JWT token: `make token` → `Authorize` → `Bearer <token>`

## Make Hedefleri

### Baslatma

```bash
make dev-fast N=10
make dev-fidelity N=10
```

### Temizlik ve durum

```bash
make stop                  # servisleri durdur
make stop-all              # observability dahil durdur
make clean                 # container + volume temizligi
make clean-hard            # image dahil tam temizlik
make status                # konteyner durumu
make logs SVC=liderapi     # servis loglari
make health                # servis saglik kontrolu
make token                 # JWT token uret
```

### Test

```bash
make test-runtime-core PROFILE=dev-fast
make test-runtime-core PROFILE=dev-fidelity
make test-runtime-operational PROFILE=dev-fidelity
make test-scale N=10
make test-registration-parity
make test-acceptance PROFILE=dev-fidelity
make test-contract
make test-unit-gate
make test-observability
make test-e2e
make test-e2e-smoke
make test-e2e-management
make test-api
make test-api-quick
make test-api-data
```

### Governance ve kalite

```bash
make audit-platform
make quality-report
make test-release-gate PROFILE=dev-fidelity N=10
make verify-candidate COMPONENT=liderui REF=<upstream-ref>
```

### Baseline ve evidence

```bash
make golden-baseline-status
make validate-golden-baseline
make golden-baseline-preflight BASELINE_ENV_FILE=<env-file>
make capture-golden-baseline BASELINE_CAPTURE_CONFIRM=1
make diff-baseline
make validate-registration-evidence
```

Detaylar: [platform/baselines/README.md](/home/huma/liderahenk-test/platform/baselines/README.md)

## Sik Karsilasilan Sorunlar

### `Could not open requirements file: requirements.txt`

Bu repoda `requirements-test.txt` kullanilir: `pip install -r requirements-test.txt`

### `error: invalid command 'bdist_wheel'`

```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements-test.txt
```

### `unknown flag: --env-file`

Docker Compose v2 kurulumunu kontrol et: `docker compose version`

### `permission denied ... Docker daemon socket`

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Port cakismasi

Temel portlar: `1389` (LDAP), `3001` (UI), `8082` (API), `15280` (ejabberd)

Observability portlari (yalnizca `dev-fidelity`): `3000` (Grafana), `3100` (Loki), `9090` (Prometheus)

```bash
sudo ss -ltnp | grep -E '1389|3000|3001|3100|8082|9090|15280'
```



## Repo Haritasi

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
tools/              swagger proxy ve yardimci araclar
```

Onemli dosyalar:

- [Makefile](/home/huma/liderahenk-test/Makefile)
- [platform/active-surface-map.md](/home/huma/liderahenk-test/platform/active-surface-map.md)
- [platform/upstream-manifest.yaml](/home/huma/liderahenk-test/platform/upstream-manifest.yaml)
- [platform/bootstrap/bootstrap-manifest.yaml](/home/huma/liderahenk-test/platform/bootstrap/bootstrap-manifest.yaml)

## Katki ve Gelistirme Notlari

Bu repoda yeni degisiklik yaparken once su sirayla okunmali:

1. [docs/platform_vizyonu.md](/home/huma/liderahenk-test/docs/platform_vizyonu.md)
2. [Makefile](/home/huma/liderahenk-test/Makefile)
3. [platform/active-surface-map.md](/home/huma/liderahenk-test/platform/active-surface-map.md)

Calisma kurali:

- once runtime foundation bozulmuyor mu diye bak
- yeni degisiklikte minimum patch ilkesini koru
- domain truth'u dogrudan sahteleme
- insan kullanici ile agent kimligini ayni kabul etme
- API degisikligi yapmadan once reverse engineering dokumanlarina bak
- aktif patch yuzeyi icin [platform/patch-inventory.csv](/home/huma/liderahenk-test/platform/patch-inventory.csv) kaydini kontrol et

## Lisans

Bu proje [LGPL-3.0](LICENSE) lisansi altindadir. LiderAhenk bilesenleri kendi
lisanslarina tabidir.
