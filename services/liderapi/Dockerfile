FROM maven:3-eclipse-temurin-21 AS builder

ARG LIDERAPI_UPSTREAM_REF=

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY platform /workspace/platform
COPY services/liderapi /workspace/services/liderapi

RUN chmod +x /workspace/platform/scripts/*.sh
RUN REPO_ROOT=/workspace LIDERAPI_UPSTREAM_REF="${LIDERAPI_UPSTREAM_REF}" \
    /workspace/platform/scripts/prepare_component_source.sh liderapi /build

WORKDIR /build

RUN mvn clean package -DskipTests --no-transfer-progress

# Stage 2: Runtime
# Maven build produces ROOT.war (Spring Boot WAR), not JAR
FROM eclipse-temurin:21-jre-alpine

RUN apk add --no-cache curl

RUN addgroup -S lider && adduser -S lider -G lider

WORKDIR /app

# WAR dosyasını kopyala — Spring Boot WAR, java -jar ile çalıştırılabilir
COPY --from=builder /build/target/ROOT.war app.war
COPY services/liderapi/jmx_prometheus_javaagent.jar /opt/jmx_exporter.jar
COPY services/liderapi/jmx_config.yml /opt/jmx_config.yml
RUN mkdir -p /etc/lider
COPY services/liderapi/lider.properties /etc/lider/lider.properties

USER lider

EXPOSE 8080

ENTRYPOINT ["java", \
  "-javaagent:/opt/jmx_exporter.jar=9779:/opt/jmx_config.yml", \
  "-jar", "app.war"]
