# LiderAhenk Test Ortamı — Makefile
# Oturum 1 + 2: Çekirdek Altyapı + Lider Servisleri

COMPOSE_CORE   = -f compose/compose.core.yml
COMPOSE_LIDER  = -f compose/compose.lider.yml
COMPOSE_AGENTS = -f compose/compose.agents.yml
COMPOSE_CMD    = docker compose --env-file .env
PROJECT_NAME   = liderahenk-test

.PHONY: dev-core dev-lider dev build-lider stop clean clean-hard logs status

## Çekirdek servisleri başlat (mariadb, ldap, ejabberd)
dev-core:
	@echo "🚀 Çekirdek servisler başlatılıyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) up -d
	@echo "⏳ Healthcheck bekleniyor..."
	@sleep 5
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) ps

## Lider imajlarını build et
build-lider:
	@echo "🔨 Lider imajları build ediliyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) build

## Çekirdek + Lider servislerini başlat
dev-lider:
	@echo "🚀 Çekirdek + Lider servisleri başlatılıyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) up -d
	@echo "⏳ Healthcheck bekleniyor..."
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) ps

## Tüm servisler (çekirdek + lider + agent)
dev:
	@echo "🚀 Tüm servisler başlatılıyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) up -d
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) ps

## Tüm servisleri durdur
stop:
	@echo "🛑 Servisler durduruluyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down

## Konteyner + volume temizle
clean:
	@echo "🧹 Konteynerler ve volume'lar temizleniyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down -v --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down -v --remove-orphans

## Image dahil tam temizle
clean-hard:
	@echo "💥 Tam temizlik (image dahil)..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down -v --rmi all --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down -v --rmi all --remove-orphans

## Belirli servis logu (kullanım: make logs SVC=mariadb)
logs:
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) logs -f $(SVC)

## Docker compose durum kontrolü
status:
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) ps
