# ============================================
# LiderAPI — Multi-Stage Maven Build
# ============================================
# Stage 1: Build
FROM maven:3-eclipse-temurin-21 AS builder

WORKDIR /build
ARG LIDER_GIT_URL=https://github.com/Pardus-LiderAhenk/liderapi.git

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN git clone ${LIDER_GIT_URL} .

# SSHA desteği ekleyen patch'ler — OpenLDAP bind uyumluluğu için
COPY patches/CustomPasswordEncoder.java src/main/java/tr/org/lider/security/CustomPasswordEncoder.java
COPY patches/Lider2Application.java src/main/java/tr/org/lider/Lider2Application.java
COPY patches/LDAPServiceImpl.java src/main/java/tr/org/lider/ldap/LDAPServiceImpl.java

# agent-info/list NPE + CoercionException fix'leri
COPY patches/AgentDTO.java src/main/java/tr/org/lider/dto/AgentDTO.java
COPY patches/AgentService.java src/main/java/tr/org/lider/services/AgentService.java
COPY patches/AgentInfoCriteriaBuilder.java src/main/java/tr/org/lider/repositories/AgentInfoCriteriaBuilder.java

RUN mvn clean package -DskipTests --no-transfer-progress

# Stage 2: Runtime
# Maven build produces ROOT.war (Spring Boot WAR), not JAR
FROM eclipse-temurin:21-jre-alpine

RUN apk add --no-cache curl

RUN addgroup -S lider && adduser -S lider -G lider

WORKDIR /app

# WAR dosyasını kopyala — Spring Boot WAR, java -jar ile çalıştırılabilir
COPY --from=builder /build/target/ROOT.war app.war
COPY jmx_prometheus_javaagent.jar /opt/jmx_exporter.jar
COPY jmx_config.yml /opt/jmx_config.yml
RUN mkdir -p /etc/lider
COPY lider.properties /etc/lider/lider.properties

USER lider

EXPOSE 8080

ENTRYPOINT ["java", \
  "-javaagent:/opt/jmx_exporter.jar=9779:/opt/jmx_config.yml", \
  "-jar", "app.war"]
