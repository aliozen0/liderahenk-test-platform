# LiderAhenk Test Environment Makefile
# Sessions 1-6: core + lider + agents + contracts + observability + orchestrator

include .env
export

COMPOSE_CORE    = -f compose/compose.core.yml
COMPOSE_LIDER   = -f compose/compose.lider.yml
COMPOSE_AGENTS  = -f compose/compose.agents.yml
COMPOSE_OBS     = -f compose/compose.obs.yml
COMPOSE_TRACING = -f compose/compose.tracing.yml
COMPOSE_CMD     = docker compose --env-file .env
PROJECT_NAME    = liderahenk-test
EVIDENCE_PROJECT_NAME ?= liderahenk-test-evidence
PLAYWRIGHT_IMAGE ?= node:20-bookworm

# Default agent scale
N ?= $(shell grep AHENK_COUNT .env | cut -d= -f2)

.PHONY: dev-core dev-lider dev dev-scale dev-obs dev-full build-lider build-agents build-obs stop stop-all clean clean-hard logs status test-contract test-contract-rest test-contract-ldap test-contract-xmpp token agents health test-integration test-scale test-observability test-evidence test-evidence-isolated run-scenario test-e2e upstream-diff verify-candidate promote-candidate test-acceptance

## Start core services (mariadb, ldap, ejabberd)
dev-core:
	@echo "Starting core services..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) up -d
	@echo "Waiting for healthchecks..."
	@sleep 5
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) ps

## Build Lider images
build-lider:
	@echo "Building Lider images..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) build

## Build agent images
build-agents:
	@echo "Building agent images..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) build

## Build observability images
build-obs:
	@echo "Building observability images..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) -p $(PROJECT_NAME) build ejabberd-exporter platform-exporter

## Start core + Lider services
dev-lider:
	@echo "Starting core + Lider services..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) up -d
	@echo "Waiting for healthchecks..."
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) ps

## Start all services (core + lider + agent)
dev:
	@echo "Starting full platform..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) up -d --scale ahenk=$(N)
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) ps

## Start scaled agents (usage: make dev-scale N=20)
dev-scale:
	@echo "Starting full platform with ahenk x$(N)..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) up -d --scale ahenk=$(N)
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) ps

## Stop all services
stop:
	@echo "Stopping services..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down

## Remove containers + volumes
clean:
	@echo "Cleaning containers and volumes..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) down -v --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down -v --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down -v --remove-orphans

## Hard cleanup including images
clean-hard:
	@echo "Performing hard cleanup..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) down -v --rmi all --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down -v --rmi all --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down -v --rmi all --remove-orphans

## Follow logs for a specific service (usage: make logs SVC=mariadb)
logs:
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) logs -f $(SVC)

## Docker compose status
status:
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) ps

## Contract tests - all adapters
test-contract:
	@echo "Running contract tests..."
	python3 -m pip install --break-system-packages -r requirements-test.txt -q
	PYTHONPATH=. pytest contracts/ -v --timeout=30 --tb=short

## REST contract tests only
test-contract-rest:
	PYTHONPATH=. pytest contracts/test_rest_contract.py -v --timeout=30

## LDAP contract tests only
test-contract-ldap:
	PYTHONPATH=. pytest contracts/test_ldap_contract.py -v --timeout=30

## XMPP contract tests only
test-contract-xmpp:
	PYTHONPATH=. pytest contracts/test_xmpp_contract.py -v --timeout=30

## Start observability stack (core + lider + agent + obs)
dev-obs:
	@echo "Starting observability stack..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) -p $(PROJECT_NAME) up -d --build --scale ahenk=$(N)
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) -p $(PROJECT_NAME) ps

## Start full stack (core + lider + agent + obs + tracing)
dev-full:
	@echo "Starting full stack..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) up -d --build --scale ahenk=$(N)
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) ps

## Stop all services including observability + tracing
stop-all:
	@echo "Stopping full stack..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) -p $(PROJECT_NAME) down

## Get JWT token
token:
	@curl -s -X POST http://localhost:8082/api/auth/signin \
	  -H "Content-Type: application/json" \
	  -d '{"username":"$(LIDER_USER)","password":"$(LIDER_PASS)"}' | \
	  python3 -c "import sys,json; print(json.load(sys.stdin)['token'])"

## Agent list (authenticated)
agents:
	@TOKEN=$$(make token -s) && \
	curl -s -H "Authorization: Bearer $$TOKEN" \
	  http://localhost:8082/api/computers | python3 -m json.tool 2>/dev/null || echo "Endpoint is POST-based"

## Service health summary
health:
	@echo "=== liderapi ==="
	@curl -s -m 5 http://localhost:8082/actuator/health | python3 -m json.tool 2>/dev/null || echo "unreachable"
	@echo "=== ejabberd ==="
	@curl -s -m 5 -X POST http://localhost:15280/api/registered_users \
	  -H "Content-Type: application/json" \
	  -d '{"host":"$(XMPP_DOMAIN)"}' 2>/dev/null | python3 -c "import sys,json; users=json.load(sys.stdin); print(f'{len(users)} registered users')" 2>/dev/null || echo "unreachable"
	@echo "=== LDAP agents ==="
	@ldapsearch -x -H ldap://localhost:1389 \
	  -D "cn=$(LDAP_ADMIN_USERNAME),$(LDAP_BASE_DN)" -w $(LDAP_ADMIN_PASSWORD) \
	  -b "ou=Ahenkler,$(LDAP_BASE_DN)" "(objectClass=device)" 2>/dev/null | grep "numEntries" || echo "unreachable"

## Integration tests
test-integration:
	@echo "Running integration tests..."
	python3 -m pip install --break-system-packages -r requirements-test.txt -q
	PYTHONPATH=. pytest tests/test_integration.py -v --timeout=60

## Scale tests
test-scale:
	@echo "Running scale tests (N=$(N))..."
	AHENK_COUNT=$(N) PYTHONPATH=. pytest tests/test_scale.py -v --timeout=120 -m scale

## Observability acceptance tests
test-observability:
	@echo "Running observability acceptance tests..."
	python3 -m pip install --break-system-packages -r requirements-test.txt -q
	PYTHONPATH=. pytest tests/test_observability.py -v --timeout=120

## Logs + metrics + traces evidence tests
test-evidence:
	@echo "Running evidence pipeline tests..."
	python3 -m pip install --break-system-packages -r requirements-test.txt -q
	PYTHONPATH=. pytest tests/test_evidence_pipeline.py -v --timeout=120

## Disposable isolated evidence run
test-evidence-isolated:
	@EVIDENCE_PROJECT_NAME=$(EVIDENCE_PROJECT_NAME) ./scripts/run_evidence_stack.sh

## Run scenario (usage: make run-scenario S=registration_test.yml)
run-scenario:
	python3 -m pip install --break-system-packages -r requirements-test.txt -q
	PYTHONPATH=. python3 orchestrator/cli.py --scenario orchestrator/scenarios/$(S)

## Run Playwright E2E tests
test-e2e:
	@echo "Running E2E tests..."
	python3 -m pip install --break-system-packages -r requirements-test.txt -q
	python3 -m playwright install chromium
	PYTHONPATH=. python3 -m pytest tests/e2e/specs/ -v --timeout=120

## Show manifest vs remote upstream state
upstream-diff:
	./platform/scripts/upstream_diff.sh $(COMPONENT)

## Verify a candidate upstream ref with build + acceptance
verify-candidate:
	./platform/scripts/verify_candidate.sh $(COMPONENT) $(REF)

## Promote a verified upstream ref into the manifest
promote-candidate:
	./platform/scripts/promote_candidate.sh $(COMPONENT) $(REF)

## Run the platform acceptance profile
test-acceptance:
	@echo "Running acceptance profile ($(PROFILE))..."
	$(MAKE) test-contract
	$(MAKE) run-scenario S=policy_roundtrip.yml
