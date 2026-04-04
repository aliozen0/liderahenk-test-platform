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
- [Topology, Override ve Senaryo Kullanimi](#topology-override-ve-senaryo-kullanimi)
- [Servisler](#servisler)
- [Host Sistem Uyumlulugu](#host-sistem-uyumlulugu)
- [Kurulum Oncesi Kontrol Listesi](#kurulum-oncesi-kontrol-listesi)
- [GitHub'dan Sifirdan Kurulum](#githubdan-sifirdan-kurulum)
- [Dogrulama Akisi](#dogrulama-akisi)
- [Arayuzler](#arayuzler)
- [Sik Karsilasilan Sorunlar](#sik-karsilasilan-sorunlar)
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

## Topology, Override ve Senaryo Kullanimi

Bu repo artik yalnizca `N` kadar ajan kaldiran bir runtime degil; `dev-fidelity`
profilinde secilebilir topology, parametrik seed ve scenario pack mantigini da
biliyor.

`make dev-fidelity N=10` komutu varsayilan olarak su baslangic topolojisini
hedefler:

| Alan | Varsayilan |
|---|---:|
| Managed endpoint | 10 |
| Operator | 3 |
| Directory user | 12 |
| User group | 4 |
| Endpoint group | 3 |
| Policy pack | `baseline-standard` |
| Session pack | `login-basic` |

Bootstrap sirasinda bu bilgiler runtime env'e aktarilir:

- `TOPOLOGY_PROFILE`
- `OPERATOR_COUNT`
- `DIRECTORY_USER_COUNT`
- `USER_GROUP_COUNT`
- `ENDPOINT_GROUP_COUNT`
- `POLICY_PACK`
- `SESSION_PACK`

En sik kullanilan override ornekleri:

```bash
make dev-fidelity N=10
TOPOLOGY_PROFILE=dev-fidelity DIRECTORY_USER_COUNT=50 USER_GROUP_COUNT=6 make dev-fidelity N=10
SESSION_PACK=login-basic make test-runtime-operational PROFILE=dev-fidelity N=10
PLATFORM_SCENARIO_PACKS=ui-user-policy-roundtrip make test-runtime-operational PROFILE=dev-fidelity N=10
```

Operasyonel notlar:

- `SESSION_PACK=login-basic` varsayilan olarak `session-login-basic` scenario
  pack'ini aktive eder
- policy senaryolari bugun explicit olarak `PLATFORM_SCENARIO_PACKS` ile
  secilir
- release lane, `session-login-basic` ve `ui-user-policy-roundtrip` scenario
  pack'lerini kullanir; acceptance summary bu pack'leri raporlar
- runtime operational raporu artik secili topology ve aktif senaryo bilgisini
  de tasir
- `make test-release-gate` release path'te `session-login-basic` ve
  `ui-user-policy-roundtrip` scenario pack'lerini explicit export eder;
  aktif scenario yoksa acceptance summary yine `PARTIAL` kalir
- `create_user_via_ui` artik gercek UI-first acceptance lane icinde
  runtime-verified calisir
- `assign_user_to_group_via_ui` icindeki `existing_group_membership_update`
  artik gercek UI-first acceptance lane icinde runtime-verified calisir
- mutation support yesile ancak aktif `ui-user-policy-roundtrip` lane'i
  gercekten gectiginde cikar; endpoint/env var tek basina support sayilmaz
- `make test-acceptance-summary ... REQUIRE_PASS=1` sarı/kismi destek
  yuzeylerini release gate'te non-zero ile durdurur

Golden baseline capture icin kisa operator checklist:

- [docs/golden-baseline-capture-checklist.md](/home/huma/liderahenk-test/docs/golden-baseline-capture-checklist.md)

Daha net calisma modeli ve ornek komutlar icin:

- [docs/dev-fidelity-operability.md](/home/huma/liderahenk-test/docs/dev-fidelity-operability.md)
- [docs/platform-hedef-mimarisi.md](/home/huma/liderahenk-test/docs/platform-hedef-mimarisi.md)

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

## Host Sistem Uyumlulugu

Bu platform host tarafta asagidaki Linux ortamlari hedeflenerek yazilmistir:

| Host sistem | Durum | Not |
|---|---|---|
| Ubuntu 22.04+ | onerilen | README komutlari dogrudan uygulanabilir |
| WSL2 + Ubuntu | desteklenir | Docker Desktop ya da host Docker ile birlikte kullanilabilir |
| Pardus 23 | desteklenir | Docker kurulumu Debian yolu ile yapilmalidir |

Pardus notu:

- resmi Pardus 23 guncelleme notlari, Pardus 23'un `Debian 12.11` tabanini
  kullandigini belirtir
- Docker resmi dokumani, turev Debian dagitimlarinda Debian kurulum yolunun
  izlenmesini ve gerekiyorsa Debian kod adinin acik yazilmasini onerir
- bu nedenle Pardus 23 uzerinde Docker kurulumu icin `debian` repo yolu ve
  `bookworm` kod adi esas alinmalidir

Resmi referanslar:

- [Pardus 23 icin yeni guncellemeler](https://pardus.org.tr/pardus-23-icin-yeni-guncellemeler-yayimlandi/)
- [Docker Engine on Debian](https://docs.docker.com/engine/install/debian/)
- [Docker Linux post-install](https://docs.docker.com/engine/install/linux-postinstall/)

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
  `1389`, `3000`, `3001`, `3100`, `8082`, `9090`, `15280`, `16686`
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

Pardus'ta `VERSION_CODENAME` degeri Docker repo tarafinda birebir eslesmeyebilir.
Bu nedenle `bookworm` degerini acik yazmak daha guvenlidir.

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
Ama ilk bakista anlaman gereken ana alanlar sunlar:

- `AHENK_COUNT`: kac ajan baslatilacagini belirler
- `PLATFORM_RUNTIME_PROFILE`: varsayilan profil
- `LIDER_USER` ve `LIDER_PASS`: UI/API giris bilgisi
- `LDAP_ADMIN_PASSWORD`, `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`: yerel ortam
  sifreleri

Zayif bir makinede ilk deneme icin `.env` icindeki `AHENK_COUNT=10` degerini
`3` ya da `5` yapabilir veya komutta `N=3` verebilirsin.

### 6. Docker aglarini olustur

Bu repo, compose overlay'leri icin onceden dis Docker network'leri bekler.
Asagidaki komutlar bunlari olusturur:

```bash
make network-init
make network-check
```

Her sey dogruysa `OK ...` satirlari gorursun.

### 7. Ilk kez platformu calistir

Ilk deneme icin iki ana secenek var.

Hizli ve daha hafif profil:

```bash
make dev-fast N=3
```

Asil kabul ve daha gercekci profil:

```bash
make dev-fidelity N=10
```

Tracing dahil genis profil:

```bash
make dev-full N=10
```

Not:

- ilk calistirmada image build ve bagimlilik indirmeleri nedeniyle sure uzun
  olabilir
- daha once basarisiz bir kurulum denediysen sifirdan temizlemek icin once
  `make clean-hard` calistirabilirsin

### 8. Platformun ayaga kalktigini kontrol et

Asagidaki komutlar ilk kontrol icin yeterlidir:

```bash
make status
make health
make token
make agents
```

Beklenen genel sonuc:

- `make status` konteynerleri listeler
- `make health` temel servislerin cevap verdigini gosterir
- `make token` JWT token uretir
- `make agents` ajan listesini getirir

### 9. Tarayicidan giris yap

Platform ayaga kalkinca su adresleri ac:

- Lider UI: `http://localhost:3001`
- Lider API: `http://localhost:8082`
- LDAP: `ldap://localhost:1389`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Jaeger: `http://localhost:16686` yalnizca `make dev-full` ile

Varsayilan giris bilgileri:

- Lider UI / API: `.env` icindeki `LIDER_USER` ve `LIDER_PASS`
- Grafana: `admin / admin`

### 10. Kurulumu test et

Platform acildi diye her sey tamam sayilmaz. Kurulumu en az bir kez test etmek
iyi fikirdir.

Core runtime lane:

```bash
make test-runtime-core PROFILE=dev-fast N=3
```

Ana kabul lane:

```bash
make test-runtime-core PROFILE=dev-fidelity N=10
make test-runtime-operational PROFILE=dev-fidelity N=10
```

Olcek lane:

```bash
make test-runtime-scale N=10
```

### 11. Durdur ve temizle

Isin bitince ortami kapatmak icin:

```bash
make stop
```

Observability ve tracing dahil her seyi kapatmak icin:

```bash
make stop-all
```

Container, volume ve orphan temizligi icin:

```bash
make clean
```

En sert temizlik icin:

```bash
make clean-hard
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
- secili scenario pack'lerin runtime check sonucu
- observability hedefleri

### 3. Release Gate

`make test-release-gate PROFILE=dev-fidelity N=10`

Bu lane release scenario pack'lerini explicit olarak kullanir:

- `session-login-basic`
- `ui-user-policy-roundtrip`

Bu akisin amaci tek raporda su sirayi gostermektir:

- unit testler
- runtime core
- runtime operational
- acceptance summary
- canonical golden baseline validation
- registration evidence
- observability ve e2e smoke

Not:

- `platform/baselines/golden-install` hala `capture-pending` ise release gate
  golden baseline asamasinda durur
- bu durum fake green degildir; canonical stock baseline capture ayrica
  tamamlanmalidir

### 4. Runtime Scale

`make test-runtime-scale N=10`

Bu lane, VM kullanmadan coklu Ahenk agent senaryosunu dogrular.

### 5. API Health Check

`make test-api`

Bu lane, reverse engineering ile belgelenen 43 kritik API endpoint'ini 11
modul uzerinden test eder. Her endpoint icin dogru HTTP method, content-type
ve payload kullanilir.

Hizli kontrol:

```bash
make test-api-quick
```

Kapsamli kontrol:

```bash
make test-api
```

Beklenen sonuc: 42/43 basarili (%97). Kalan 1 endpoint (forgot-password)
mail sunucu konfigurasyonu gerektirir.

Detaylar: [docs/reverse-engineering/12-api-test-sonuclari.md](/home/huma/liderahenk-test/docs/reverse-engineering/12-api-test-sonuclari.md)

#### 5b. API Veri Dogrulama

`make test-api-data`

Bu lane, API'lerin 200 donmesinin otesinde verilerin gercek ve tutarli olup
olmadigini dogrular. 3 katmanli cross-validation yapar:

- API response vs MariaDB (c_agent, c_policy, c_operation_log)
- API response vs LDAP (pardusDevice, organization)
- API response vs ejabberd (registered_users, status)

Beklenen sonuc: 28/28 basarili (%100).

Kontrol edilen tutarlilik noktalari:

| Dogrulama | Kaynaklar |
|---|---|
| Agent sayisi | Dashboard ↔ Agent API ↔ DB (c_agent) ↔ LDAP (pardusDevice) |
| Policy sayisi | Policy API ↔ DB (c_policy) |
| Login loglari | Operation Logs API ↔ DB (c_operation_log, operation_type=5) |
| LDAP baglantisi | Settings API ↔ LDAP container |
| XMPP baglantisi | Settings API ↔ ejabberd container |

Tespit edilen upstream bulgular:

- `operation_type` DB'de INT enum (5=LOGIN), DTO'da String olarak beklenir
- `pageNumber` 1-indexed (Spring varsayilan 0-indexed degil)
- `/api/messaging/get-messaging-server-info` upstream'de `body(null)` doner
- `c_agent.is_deleted` vs `c_policy.deleted` — upstream tablo isimlendirme tutarsizligi

### 6. Destekleyici Testler

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
| Swagger UI | http://localhost:8082/swagger-ui/index.html | JWT token gerekli (asagiya bak) |
| OpenAPI JSON | http://localhost:8082/v3/api-docs | 237 endpoint, OpenAPI 3.1.0 |
| LDAP | ldap://localhost:1389 | yerel LDAP sorgulari icin |
| Grafana | http://localhost:3000 | varsayilan `admin / admin` |
| Prometheus | http://localhost:9090 | metrics ve target gorunumu |
| Jaeger | http://localhost:16686 | yalnizca `make dev-full` ile |

Swagger UI'a tarayicidan erismek icin JWT token gerekir. Token almak icin:

```bash
make token
```

Swagger UI'da sag ustteki `Authorize` butonuna tiklayip `Bearer <token>` olarak girilir.

## Sik Karsilasilan Sorunlar

### `Could not open requirements file: requirements.txt`

Bu repoda kullanilan dosya `requirements.txt` degil `requirements-test.txt`
dosyasidir.

Dogru komut:

```bash
pip install -r requirements-test.txt
```

### `error: invalid command 'bdist_wheel'`

Sanal ortamda `wheel` eksik olabilir.

```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements-test.txt
```

### `unknown flag: --env-file`

Bu hata genelde eski Docker/Compose kurulumu ya da repo icindeki eski bir
versiyon nedeniyle gorulur.

Kontrol et:

```bash
docker compose version
git pull
```

Repo icindeki guncel akista `docker compose` komutu kullanilir. Yine de sorun
devam ediyorsa Docker Compose v2 kurulumu eksik olabilir.

Pardus kullaniyorsan Docker repo taniminda `debian` yolu ve `bookworm` kod adini
kullandigindan emin ol.

### `permission denied while trying to connect to the Docker daemon socket`

Kullanicin `docker` grubunda olmayabilir:

```bash
sudo groupadd docker || true
sudo usermod -aG docker $USER
newgrp docker
```

### `WARNING: Error loading config file: ~/.docker/config.json: permission denied`

Bu genelde daha once `sudo docker ...` kullanildigi icin olur.

```bash
sudo chown "$USER":"$USER" "$HOME/.docker" -R
sudo chmod g+rwx "$HOME/.docker" -R
```

### Port cakismasi

Asagidaki portlardan biri baska uygulama tarafindan kullaniliyorsa platform
tam kalkmayabilir:

- `3000`
- `3001`
- `1389`
- `3100`
- `8082`
- `9090`
- `15280`
- `16686`

Hangi surecin portu tuttugunu gormek icin:

```bash
sudo ss -ltnp | grep -E '1389|3000|3001|3100|8082|9090|15280|16686'
```

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

Benzer isimli klasorler icin hizli rehber:

| Yol | Rol | Ne zaman buraya bakilir? |
|---|---|---|
| `tests/contracts/` | pytest contract testleri | `make test-contract` ve benzeri testler |
| `platform/contracts/` | canonical platform contract tanimlari | runtime readiness, topology, scenario-pack ve baseline contract'lari |
| `platform/scripts/` | canonical platform operasyon scriptleri | bootstrap, validate, baseline, release gate |
| `services/` | runtime servis build context'leri | `liderapi`, `liderui`, `ldap`, `mariadb` gibi servisler |
| `platform/services/` | platform-owned sidecar servisler | upstream urune ait olmayan destek/orchestrator servisleri |
| `orchestrator/legacy_scenarios/` | legacy/simple scenario runner girdileri | `make run-legacy-scenario S=...` kullanimlari |
| `platform/scenarios/` | canonical scenario-pack yuzeyi | acceptance, runtime operational ve release gate |
| `platform/` | deklaratif platform governance ve manifestler | contract, baseline, topology ve patch governance |
| `platform_runtime/` | calisan runtime verification kodu | readiness, evidence, summary ve diff mantigi |

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

### API Health Check

```bash
make test-api              # 43 endpoint, 11 modul (kapsamli)
make test-api-quick        # 10 cekirdek endpoint (hizli)
make test-api-data         # veri dogrulama (API vs DB vs LDAP)
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
make test-release-gate PROFILE=dev-fidelity N=10
make verify-candidate COMPONENT=liderui REF=<upstream-ref>
```

### Baseline ve evidence

```bash
make golden-baseline-status
BASELINE_ENV_FILE=platform/baselines/stock-capture.env.example make golden-baseline-preflight
make validate-golden-baseline
BASELINE_CAPTURE_CONFIRM=1 make capture-golden-baseline \
  BASELINE_ENV_FILE=platform/baselines/stock-capture.env.example \
  BASELINE_SOURCE_LABEL="stock-install-YYYY-MM-DD"
make diff-baseline
make validate-registration-evidence
```

Not:

- `make golden-baseline-status` sadece durum okur; `pending-capture` ise bunu
  açıkça yazar
- `make golden-baseline-preflight` stock env dosyasındaki zorunlu alanları ve
  temel TCP erişimini capture öncesi kontrol eder
- sadece env şablonunu kontrol etmek istersen `BASELINE_PREFLIGHT_ENV_ONLY=1`
  ile TCP kontrolünü kapatabilirsin
- `make test-release-gate PROFILE=dev-fidelity N=10` bugun canonical golden
  baseline capture tamamlanmadigi icin `validate-golden-baseline` asamasinda
  durabilir
- release gate raporu bunu saklamaz; blocker olarak gorunur
- bu alanin klasor yapisi ve dosya rolleri icin:
  [platform/baselines/README.md](/home/huma/liderahenk-test/platform/baselines/README.md)

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

## Reverse Engineering

LiderAhenk platformunun tum API yuzeyi tersine muhendislik ile belgelenmistir.
41 controller, 207+ endpoint ve 91+ veritabani tablosu kapsanmistir.

- Master index: [docs/reverse-engineering/_index.md](/home/huma/liderahenk-test/docs/reverse-engineering/_index.md)
- API test sonuclari: [docs/reverse-engineering/12-api-test-sonuclari.md](/home/huma/liderahenk-test/docs/reverse-engineering/12-api-test-sonuclari.md)

| Modul | Kapsam | Dosya |
|---|---|---|
| Auth & Login | 11 endpoint | [01-auth-login.md](/home/huma/liderahenk-test/docs/reverse-engineering/01-auth-login.md) |
| Agent/Computer | 20 endpoint | [02-agent-computer.md](/home/huma/liderahenk-test/docs/reverse-engineering/02-agent-computer.md) |
| Task Execution | 19 endpoint | [03-task-execution.md](/home/huma/liderahenk-test/docs/reverse-engineering/03-task-execution.md) |
| Policy & Profile | 15 endpoint | [04-policy-profile.md](/home/huma/liderahenk-test/docs/reverse-engineering/04-policy-profile.md) |
| User & Group | 33 endpoint | [05-user-group.md](/home/huma/liderahenk-test/docs/reverse-engineering/05-user-group.md) |
| Computer Groups | 16 endpoint | [06-computer-groups.md](/home/huma/liderahenk-test/docs/reverse-engineering/06-computer-groups.md) |
| Reports | 16 endpoint | [07-reports.md](/home/huma/liderahenk-test/docs/reverse-engineering/07-reports.md) |
| Settings & Config | 36 endpoint | [08-settings-config.md](/home/huma/liderahenk-test/docs/reverse-engineering/08-settings-config.md) |
| AD & Sudo | 32 endpoint | [09-ad-sudo.md](/home/huma/liderahenk-test/docs/reverse-engineering/09-ad-sudo.md) |
| Remote & Transfer | 17 endpoint | [10-remote-access.md](/home/huma/liderahenk-test/docs/reverse-engineering/10-remote-access.md) |
| Ek Controller'lar | 16 endpoint | [11-ek-controllerlar.md](/home/huma/liderahenk-test/docs/reverse-engineering/11-ek-controllerlar.md) |

## Katki ve Gelistirme Notlari

Bu repoda yeni degisiklik yaparken once su sirayla okunmali:

1. [docs/platform_vizyonu.md](/home/huma/liderahenk-test/docs/platform_vizyonu.md)
2. [docs/product-requirements.md](/home/huma/liderahenk-test/docs/product-requirements.md)
3. [docs/reverse-engineering/_index.md](/home/huma/liderahenk-test/docs/reverse-engineering/_index.md)
4. [Makefile](/home/huma/liderahenk-test/Makefile)
5. [platform/active-surface-map.md](/home/huma/liderahenk-test/platform/active-surface-map.md)

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
