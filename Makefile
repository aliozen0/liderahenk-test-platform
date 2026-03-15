# LiderAhenk Test Ortamı — Makefile
# Oturum 1-6: Çekirdek + Lider + Ajanlar + Sözleşme + Gözlemlenebilirlik + Orchestrator

include .env
export

COMPOSE_CORE    = -f compose/compose.core.yml
COMPOSE_LIDER   = -f compose/compose.lider.yml
COMPOSE_AGENTS  = -f compose/compose.agents.yml
COMPOSE_OBS     = -f compose/compose.obs.yml
COMPOSE_TRACING = -f compose/compose.tracing.yml
COMPOSE_CMD     = docker compose --env-file .env
PROJECT_NAME    = liderahenk-test
PLAYWRIGHT_IMAGE ?= node:20-bookworm

# Varsayılan ölçekleme sayısı
N ?= $(shell grep AHENK_COUNT .env | cut -d= -f2)

.PHONY: dev-core dev-lider dev dev-scale dev-obs dev-full build-lider build-agents stop stop-all clean clean-hard logs status test-contract test-contract-rest test-contract-ldap test-contract-xmpp token agents health test-integration test-scale run-scenario test-e2e

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
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) up -d --scale ahenk=$(N)
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
	python3 -m pip install --break-system-packages -r requirements-test.txt -q
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
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) -p $(PROJECT_NAME) up -d --scale ahenk=$(N)
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) -p $(PROJECT_NAME) ps

## Tam stack (core + lider + agent + obs + tracing)
dev-full:
	@echo "🚀 Tam stack başlatılıyor..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) up -d --scale ahenk=$(N)
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) ps

## Tüm servisleri durdur (obs + tracing dahil)
stop-all:
	@echo "🛑 Tüm servisler durduruluyor (obs + tracing dahil)..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) down

## JWT token al
token:
	@curl -s -X POST http://localhost:8082/api/auth/signin \
	  -H "Content-Type: application/json" \
	  -d '{"username":"$(LIDER_USER)","password":"$(LIDER_PASS)"}' | \
	  python3 -c "import sys,json; print(json.load(sys.stdin)['token'])"

## Ajan listesi (authenticated)
agents:
	@TOKEN=$$(make token -s) && \
	curl -s -H "Authorization: Bearer $$TOKEN" \
	  http://localhost:8082/api/computers | python3 -m json.tool 2>/dev/null || echo "Endpoint POST tabanlı"

## Servis sağlık durumu
health:
	@echo "=== liderapi ==="
	@curl -s -m 5 http://localhost:8082/actuator/health | python3 -m json.tool 2>/dev/null || echo "erişilemez"
	@echo "=== ejabberd ==="
	@curl -s -m 5 -X POST http://localhost:15280/api/registered_users \
	  -H "Content-Type: application/json" \
	  -d '{"host":"$(XMPP_DOMAIN)"}' 2>/dev/null | python3 -c "import sys,json; users=json.load(sys.stdin); print(f'{len(users)} kayıtlı kullanıcı')" 2>/dev/null || echo "erişilemez"
	@echo "=== LDAP ajan ==="
	@ldapsearch -x -H ldap://localhost:1389 \
	  -D "cn=$(LDAP_ADMIN_USERNAME),$(LDAP_BASE_DN)" -w $(LDAP_ADMIN_PASSWORD) \
	  -b "ou=Ahenkler,$(LDAP_BASE_DN)" "(objectClass=device)" 2>/dev/null | grep "numEntries" || echo "erişilemez"

## Entegrasyon testleri
test-integration:
	@echo "🧪 Entegrasyon testleri koşturuluyor..."
	python3 -m pip install --break-system-packages -r requirements-test.txt -q
	PYTHONPATH=. pytest tests/test_integration.py -v --timeout=60

## Ölçek testleri
test-scale:
	@echo "🧪 Ölçek testleri koşturuluyor (N=$(N))..."
	AHENK_COUNT=$(N) PYTHONPATH=. pytest tests/test_scale.py -v --timeout=120 -m scale

## Senaryo çalıştır (kullanım: make run-scenario S=registration_test.yml)
run-scenario:
	python3 -m pip install --break-system-packages -r requirements-test.txt -q
	PYTHONPATH=. python3 orchestrator/cli.py --scenario orchestrator/scenarios/$(S)

## Playwright ile E2E Testleri koştur (Faz 1-2)
test-e2e:
	@echo "🎭 E2E testleri koşturuluyor..."
	python3 -m pip install --break-system-packages -r requirements-test.txt -q
	python3 -m playwright install chromium
	PYTHONPATH=. python3 -m pytest tests/e2e/specs/ -v --timeout=120
