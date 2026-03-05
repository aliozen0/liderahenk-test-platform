# LiderAhenk Test Ortamı — Makefile
# Oturum 1-5: Çekirdek + Lider + Ajanlar + Sözleşme + Gözlemlenebilirlik

COMPOSE_CORE    = -f compose/compose.core.yml
COMPOSE_LIDER   = -f compose/compose.lider.yml
COMPOSE_AGENTS  = -f compose/compose.agents.yml
COMPOSE_OBS     = -f compose/compose.obs.yml
COMPOSE_TRACING = -f compose/compose.tracing.yml
COMPOSE_CMD     = docker compose --env-file .env
PROJECT_NAME    = liderahenk-test

# Varsayılan ölçekleme sayısı
N ?= $(shell grep AHENK_COUNT .env | cut -d= -f2)

.PHONY: dev-core dev-lider dev dev-scale dev-obs dev-full build-lider build-agents stop stop-all clean clean-hard logs status test-contract test-contract-rest test-contract-ldap test-contract-xmpp

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

## Agent imajlarını build et
build-agents:
	@echo "🔨 Agent imajları build ediliyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) build

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

## Ölçekli ajan başlat (kullanım: make dev-scale N=20)
dev-scale:
	@echo "🚀 Tüm servisler başlatılıyor (ahenk ×$(N))..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) up -d --scale ahenk=$(N)
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) ps

## Tüm servisleri durdur
stop:
	@echo "🛑 Servisler durduruluyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down

## Konteyner + volume temizle
clean:
	@echo "🧹 Konteynerler ve volume'lar temizleniyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) down -v --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down -v --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down -v --remove-orphans

## Image dahil tam temizle
clean-hard:
	@echo "💥 Tam temizlik (image dahil)..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) down -v --rmi all --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down -v --rmi all --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down -v --rmi all --remove-orphans

## Belirli servis logu (kullanım: make logs SVC=mariadb)
logs:
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) logs -f $(SVC)

## Docker compose durum kontrolü
status:
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) ps

## Sözleşme testleri — tüm adapter'lar
test-contract:
	@echo "🧪 Sözleşme testleri koşturuluyor..."
	pip install --break-system-packages -r requirements-test.txt -q
	PYTHONPATH=. pytest contracts/ -v --timeout=30 --tb=short

## Sadece REST sözleşme testleri
test-contract-rest:
	PYTHONPATH=. pytest contracts/test_rest_contract.py -v --timeout=30

## Sadece LDAP sözleşme testleri
test-contract-ldap:
	PYTHONPATH=. pytest contracts/test_ldap_contract.py -v --timeout=30

## Sadece XMPP sözleşme testleri
test-contract-xmpp:
	PYTHONPATH=. pytest contracts/test_xmpp_contract.py -v --timeout=30

## Gözlemlenebilirlik stack'i ile başlat (core + lider + agent + obs)
dev-obs:
	@echo "📊 Gözlemlenebilirlik stack'i başlatılıyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) -p $(PROJECT_NAME) up -d
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) -p $(PROJECT_NAME) ps

## Tam stack (core + lider + agent + obs + tracing)
dev-full:
	@echo "🚀 Tam stack başlatılıyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) up -d
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) ps

## Tüm servisleri durdur (obs + tracing dahil)
stop-all:
	@echo "🛑 Tüm servisler durduruluyor (obs + tracing dahil)..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) down
