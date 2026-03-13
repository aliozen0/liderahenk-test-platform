# ============================================
# LiderCore — .deb Paket Konteynerizasyon
# ============================================
FROM debian:bookworm-slim

# Temel araçları kur
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl gnupg2 ca-certificates wget apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

# Adoptium (Temurin) repo ekle — openjdk-8 bookworm'da mevcut değil
RUN mkdir -p /etc/apt/keyrings \
    && wget -qO- https://packages.adoptium.net/artifactory/api/gpg/key/public \
       | gpg --dearmor -o /etc/apt/keyrings/adoptium.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/adoptium.gpg] \
       https://packages.adoptium.net/artifactory/deb bookworm main" \
       > /etc/apt/sources.list.d/adoptium.list

# Pardus LiderAhenk paket deposunu ekle
RUN curl -fsSL https://repo.liderahenk.org.tr/liderahenk-archive-keyring.asc \
    | gpg --dearmor -o /usr/share/keyrings/liderahenk.gpg

RUN echo "deb [signed-by=/usr/share/keyrings/liderahenk.gpg] \
    https://repo.liderahenk.org.tr/liderahenk stable main" \
    > /etc/apt/sources.list.d/liderahenk.list

# Tüm bağımlılıkları kur: Java 8, equivs, nmap, ssh
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       temurin-8-jre equivs nmap ssh \
    && rm -rf /var/lib/apt/lists/*

# openjdk-8-jre sahte paket oluştur (lider-server bağımlılığını karşılar)
RUN mkdir -p /tmp/equivs && cd /tmp/equivs \
    && printf 'Section: misc\nPriority: optional\nStandards-Version: 3.9.2\nPackage: openjdk-8-jre\nVersion: 8.0\nProvides: java-runtime, java8-runtime\nDescription: Virtual package for openjdk-8-jre (provided by temurin-8-jre)\n' > openjdk-8-jre.ctl \
    && equivs-build openjdk-8-jre.ctl \
    && dpkg -i openjdk-8-jre_8.0_all.deb \
    && rm -rf /tmp/equivs

# lider-server kur — postinst scripti systemd+dbus çağırır,
# konteyner ortamında çalışmaz. Çözüm:
# 1. Paketi indir
# 2. dpkg --unpack ile aç (postinst çalıştırılmaz)
# 3. postinst sil
# 4. dpkg --configure ile yapılandır
RUN apt-get update \
    && cd /tmp \
    && apt-get download lider-server \
    && dpkg --unpack lider-server_*.deb \
    && rm -f /var/lib/dpkg/info/lider-server.postinst \
    && dpkg --configure lider-server \
    && rm -f /tmp/lider-server_*.deb \
    && rm -rf /var/lib/apt/lists/*

# Karaf dizin kontrolü
RUN ls -la /opt/lider*/bin/ 2>/dev/null || echo "Lider kurulum dizini kontrol ediliyor..." \
    && dpkg -L lider-server | grep -E "bin|karaf" | head -10

# JMX Prometheus Exporter
COPY jmx_prometheus_javaagent.jar /opt/jmx_exporter.jar
COPY jmx_config.yml /opt/jmx_config.yml

# Entrypoint
COPY entrypoint-core.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8181 9779

ENTRYPOINT ["/entrypoint.sh"]
