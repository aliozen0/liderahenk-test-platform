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
| LDAP | ldap://localhost:1389 | yerel LDAP sorgulari icin |
| Grafana | http://localhost:3000 | varsayilan `admin / admin` |
| Prometheus | http://localhost:9090 | metrics ve target gorunumu |
| Jaeger | http://localhost:16686 | yalnizca `make dev-full` ile |

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
