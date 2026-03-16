# LiderAhenk Test Environment Makefile
# Sessions 1-6: core + lider + agents + contracts + observability + orchestrator

include .env
export

COMPOSE_CORE    = -f compose/compose.core.yml
COMPOSE_LIDER   = -f compose/compose.lider.yml
COMPOSE_AGENTS  = -f compose/compose.agents.yml
COMPOSE_PLATFORM = -f compose/compose.platform.yml
COMPOSE_OBS     = -f compose/compose.obs.yml
COMPOSE_TRACING = -f compose/compose.tracing.yml
COMPOSE_CMD     = docker compose --env-file .env
PROJECT_NAME    = liderahenk-test
EVIDENCE_PROJECT_NAME ?= liderahenk-test-evidence
PLAYWRIGHT_IMAGE ?= node:20-bookworm
NETWORK_CORE    = $(PROJECT_NAME)_liderahenk_core
NETWORK_AGENTS  = $(PROJECT_NAME)_liderahenk_agents
NETWORK_OBS     = $(PROJECT_NAME)_liderahenk_obs
NETWORK_EXTERNAL = $(PROJECT_NAME)_liderahenk_external
PLATFORM_RUNTIME_PROFILE ?= dev-fast
PROFILE ?= dev-fast
BASELINE_ROOT ?= platform/baselines/golden-install
BASELINE_ENV_FILE ?=
BASELINE_SOURCE_LABEL ?=

# Default agent scale
N ?= $(shell grep AHENK_COUNT .env | cut -d= -f2)

.PHONY: network-init network-check network-reset install-test-deps dev-core dev-lider dev-fast dev-fidelity dev dev-scale dev-obs dev-full build-lider build-agents build-platform build-obs stop stop-all clean clean-hard logs status test-contract test-contract-rest test-contract-ldap test-contract-xmpp token agents health quality-report test-integration test-scale test-runtime-core test-runtime-operational test-runtime-scale test-observability test-evidence test-evidence-isolated run-scenario test-e2e test-e2e-smoke test-e2e-management test-release-gate upstream-diff verify-candidate promote-candidate audit-platform test-acceptance validate-golden-baseline capture-golden-baseline test-registration-parity diff-baseline validate-registration-evidence

## Create external Docker networks required by compose overlays
network-init:
	@echo "Ensuring Docker networks exist..."
	@docker network inspect $(NETWORK_CORE) >/dev/null 2>&1 || docker network create --driver bridge --internal $(NETWORK_CORE)
	@docker network inspect $(NETWORK_AGENTS) >/dev/null 2>&1 || docker network create --driver bridge $(NETWORK_AGENTS)
	@docker network inspect $(NETWORK_OBS) >/dev/null 2>&1 || docker network create --driver bridge $(NETWORK_OBS)
	@docker network inspect $(NETWORK_EXTERNAL) >/dev/null 2>&1 || docker network create --driver bridge $(NETWORK_EXTERNAL)
	@echo "Docker networks ready."

## Verify required Docker networks exist
network-check:
	@echo "Checking Docker networks..."
	@docker network inspect $(NETWORK_CORE) >/dev/null 2>&1 && echo "OK $(NETWORK_CORE)" || (echo "MISSING $(NETWORK_CORE)" && exit 1)
	@docker network inspect $(NETWORK_AGENTS) >/dev/null 2>&1 && echo "OK $(NETWORK_AGENTS)" || (echo "MISSING $(NETWORK_AGENTS)" && exit 1)
	@docker network inspect $(NETWORK_OBS) >/dev/null 2>&1 && echo "OK $(NETWORK_OBS)" || (echo "MISSING $(NETWORK_OBS)" && exit 1)
	@docker network inspect $(NETWORK_EXTERNAL) >/dev/null 2>&1 && echo "OK $(NETWORK_EXTERNAL)" || (echo "MISSING $(NETWORK_EXTERNAL)" && exit 1)

## Recreate Docker networks when overlays drift
network-reset:
	@echo "Recreating Docker networks..."
	@docker network rm $(NETWORK_EXTERNAL) $(NETWORK_OBS) $(NETWORK_AGENTS) $(NETWORK_CORE) >/dev/null 2>&1 || true
	@$(MAKE) network-init

## Install local Python test dependencies
install-test-deps:
	@echo "Installing Python test dependencies..."
	python3 -m pip install --break-system-packages -r requirements-test.txt -q

## Start core services (mariadb, ldap, ejabberd)
dev-core:
	@echo "Starting core services..."
	@$(MAKE) network-init
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

## Build platform support images
build-platform:
	@echo "Building platform support images..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) -p $(PROJECT_NAME) build registration-orchestrator

## Build observability images
build-obs:
	@echo "Building observability images..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_OBS) -p $(PROJECT_NAME) build ejabberd-exporter platform-exporter

## Start core + Lider services
dev-lider:
	@echo "Starting core + Lider services..."
	@$(MAKE) network-init
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) up -d
	@echo "Waiting for healthchecks..."
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) ps

## Start the fast development profile
dev-fast:
	@echo "Starting dev-fast platform..."
	@$(MAKE) network-init
	AHENK_COUNT=$(N) PLATFORM_RUNTIME_PROFILE=dev-fast PYTHONPATH=. python3 platform/scripts/bootstrap_runtime.py --profile dev-fast --agents $(N) --project-name $(PROJECT_NAME)

## Start the higher-fidelity acceptance profile
dev-fidelity:
	@echo "Starting dev-fidelity platform..."
	@$(MAKE) network-init
	AHENK_COUNT=$(N) PLATFORM_RUNTIME_PROFILE=dev-fidelity PYTHONPATH=. python3 platform/scripts/bootstrap_runtime.py --profile dev-fidelity --agents $(N) --project-name $(PROJECT_NAME)

## Start all services (backward-compatible alias)
dev:
	@$(MAKE) dev-fast N=$(N)

## Start scaled agents (usage: make dev-scale N=20)
dev-scale:
	@echo "Starting full platform with ahenk x$(N)..."
	@$(MAKE) network-init
	AHENK_COUNT=$(N) PLATFORM_RUNTIME_PROFILE=$(PLATFORM_RUNTIME_PROFILE) $(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) -p $(PROJECT_NAME) up -d --scale ahenk=$(N)
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) -p $(PROJECT_NAME) ps

## Stop all services
stop:
	@echo "Stopping services..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down

## Remove containers + volumes
clean:
	@echo "Cleaning containers and volumes..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) -p $(PROJECT_NAME) down -v --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down -v --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down -v --remove-orphans

## Hard cleanup including images
clean-hard:
	@echo "Performing hard cleanup..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) -p $(PROJECT_NAME) down -v --rmi all --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) -p $(PROJECT_NAME) down -v --rmi all --remove-orphans 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) -p $(PROJECT_NAME) down -v --rmi all --remove-orphans

## Follow logs for a specific service (usage: make logs SVC=mariadb)
logs:
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) -p $(PROJECT_NAME) logs -f $(SVC)

## Docker compose status
status:
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) -p $(PROJECT_NAME) ps

## Contract tests - all adapters
test-contract:
	@echo "Running contract tests..."
	@$(MAKE) install-test-deps
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
	@$(MAKE) dev-fidelity N=$(N)

## Start full stack (core + lider + agent + obs + tracing)
dev-full:
	@echo "Starting full stack..."
	@$(MAKE) network-init
	AHENK_COUNT=$(N) PLATFORM_RUNTIME_PROFILE=dev-fidelity $(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) up -d --build --scale ahenk=$(N)
	@sleep 10
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) ps

## Stop all services including observability + tracing
stop-all:
	@echo "Stopping full stack..."
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) $(COMPOSE_OBS) $(COMPOSE_TRACING) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) $(COMPOSE_OBS) -p $(PROJECT_NAME) down 2>/dev/null || \
	$(COMPOSE_CMD) $(COMPOSE_CORE) $(COMPOSE_LIDER) $(COMPOSE_AGENTS) $(COMPOSE_PLATFORM) -p $(PROJECT_NAME) down

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
	@$(MAKE) install-test-deps
	PYTHONPATH=. pytest tests/test_integration.py -v --timeout=60

## Scale tests
test-scale:
	@echo "Running scale tests (N=$(N))..."
	AHENK_COUNT=$(N) PYTHONPATH=. pytest tests/test_scale.py -v --timeout=120 -m scale

## Observability acceptance tests
test-observability:
	@echo "Running observability acceptance tests..."
	@$(MAKE) install-test-deps
	PYTHONPATH=. pytest tests/test_observability.py -v --timeout=120

## Logs + metrics + traces evidence tests
test-evidence:
	@echo "Running evidence pipeline tests..."
	@$(MAKE) install-test-deps
	PYTHONPATH=. pytest tests/test_evidence_pipeline.py -v --timeout=120

## Disposable isolated evidence run
test-evidence-isolated:
	@EVIDENCE_PROJECT_NAME=$(EVIDENCE_PROJECT_NAME) ./scripts/run_evidence_stack.sh

## Generate a markdown/json quality report under artifacts/
quality-report:
	@echo "Generating quality report..."
	@$(MAKE) install-test-deps
	PYTHONPATH=. python3 scripts/generate_quality_report.py

## Validate docker/runtime readiness for the selected profile
test-runtime-core:
	@echo "Running runtime core checks ($(PROFILE))..."
	@if [ "$(PROFILE)" != "dev-fast" ] && [ "$(PROFILE)" != "dev-fidelity" ]; then echo "Unsupported runtime profile: $(PROFILE)"; exit 1; fi
	@$(MAKE) install-test-deps
	AHENK_COUNT=$(N) PYTHONPATH=. PLATFORM_RUNTIME_PROFILE=$(PROFILE) python3 platform/scripts/validate_runtime_core.py

## Validate operational runtime flows for the higher-fidelity profile
test-runtime-operational:
	@echo "Running runtime operational checks ($(PROFILE))..."
	@if [ "$(PROFILE)" != "dev-fidelity" ]; then echo "test-runtime-operational requires PROFILE=dev-fidelity"; exit 1; fi
	@$(MAKE) install-test-deps
	python3 -m playwright install chromium
	AHENK_COUNT=$(N) PYTHONPATH=. PLATFORM_RUNTIME_PROFILE=$(PROFILE) python3 platform/scripts/validate_runtime_operational.py

## Run scale acceptance using the runtime-first target name
test-runtime-scale:
	@echo "Running runtime scale acceptance (N=$(N))..."
	@$(MAKE) test-scale N=$(N)

## Validate the committed golden baseline registry
validate-golden-baseline:
	@echo "Validating golden baseline..."
	@$(MAKE) install-test-deps
	PYTHONPATH=. python3 platform/scripts/validate_golden_baseline.py $(BASELINE_ROOT)

## Capture a golden baseline from the active runtime
capture-golden-baseline:
	@echo "Capturing golden baseline..."
	@$(MAKE) install-test-deps
	PYTHONPATH=. python3 platform/scripts/capture_golden_baseline.py $(BASELINE_ROOT) $(if $(BASELINE_ENV_FILE),--env-file $(BASELINE_ENV_FILE),) $(if $(BASELINE_SOURCE_LABEL),--source-label "$(BASELINE_SOURCE_LABEL)",)

## Run exact registration parity checks
test-registration-parity:
	@echo "Running registration parity checks..."
	@$(MAKE) install-test-deps
	AHENK_COUNT=$(N) PYTHONPATH=. pytest tests/test_registration_parity.py -v --timeout=120

## Compare live runtime state with the golden baseline
diff-baseline:
	@echo "Diffing live runtime against golden baseline..."
	@$(MAKE) install-test-deps
	@$(MAKE) validate-golden-baseline BASELINE_ROOT=$(BASELINE_ROOT)
	PYTHONPATH=. python3 platform/scripts/diff_baseline.py $(BASELINE_ROOT)

## Validate platform registration evidence bundle
validate-registration-evidence:
	@echo "Validating registration evidence..."
	@$(MAKE) install-test-deps
	PYTHONPATH=. python3 platform/scripts/validate_registration_evidence.py

## Run scenario (usage: make run-scenario S=registration_test.yml)
run-scenario:
	@$(MAKE) install-test-deps
	PYTHONPATH=. python3 orchestrator/cli.py --scenario orchestrator/scenarios/$(S)

## Run Playwright E2E tests
test-e2e:
	@echo "Running E2E tests..."
	@$(MAKE) install-test-deps
	mkdir -p artifacts/e2e
	python3 -m playwright install chromium
	PYTHONPATH=. python3 -m pytest tests/e2e/specs/ -v -m "e2e" --timeout=180 --html=artifacts/e2e/all.html --self-contained-html --junitxml=artifacts/e2e/all.junit.xml

## Run only the smoke/login E2E profile
test-e2e-smoke:
	@echo "Running E2E smoke tests..."
	@$(MAKE) install-test-deps
	mkdir -p artifacts/e2e
	python3 -m playwright install chromium
	PYTHONPATH=. python3 -m pytest tests/e2e/specs/ -v -m "e2e and smoke" --timeout=120 --html=artifacts/e2e/smoke.html --self-contained-html --junitxml=artifacts/e2e/smoke.junit.xml

## Run hybrid management-oriented E2E flows
test-e2e-management:
	@echo "Running E2E management tests..."
	@$(MAKE) install-test-deps
	mkdir -p artifacts/e2e
	python3 -m playwright install chromium
	PYTHONPATH=. python3 -m pytest tests/e2e/specs/ -v -m "e2e and management" --timeout=180 --html=artifacts/e2e/management.html --self-contained-html --junitxml=artifacts/e2e/management.junit.xml

## Run a release-oriented quality gate
test-release-gate:
	@echo "Running release gate..."
	@$(MAKE) test-runtime-core PROFILE=$(PROFILE)
	@$(MAKE) test-runtime-operational PROFILE=$(PROFILE)
	@$(MAKE) validate-golden-baseline
	@$(MAKE) test-acceptance PROFILE=$(PROFILE)
	@$(MAKE) diff-baseline PROFILE=$(PROFILE)
	@$(MAKE) validate-registration-evidence
	@$(MAKE) test-observability
	@$(MAKE) test-evidence
	@$(MAKE) test-e2e-smoke
	@$(MAKE) quality-report

## Show manifest vs remote upstream state
upstream-diff:
	./platform/scripts/upstream_diff.sh $(COMPONENT)

## Verify a candidate upstream ref with build + acceptance
verify-candidate:
	./platform/scripts/verify_candidate.sh $(COMPONENT) $(REF)

## Promote a verified upstream ref into the manifest
promote-candidate:
	./platform/scripts/promote_candidate.sh $(COMPONENT) $(REF)

## Audit tracked patch surface against the inventory
audit-platform:
	chmod +x ./platform/scripts/audit_patch_surface.sh
	./platform/scripts/audit_patch_surface.sh

## Run the platform acceptance profile
test-acceptance:
	@echo "Running acceptance profile ($(PROFILE))..."
	@if [ "$(PROFILE)" != "dev-fast" ] && [ "$(PROFILE)" != "dev-fidelity" ]; then echo "Unsupported acceptance profile: $(PROFILE)"; exit 1; fi
	$(MAKE) test-contract
	$(MAKE) test-runtime-core PROFILE=$(PROFILE)
	$(MAKE) test-registration-parity
	$(MAKE) run-scenario S=policy_roundtrip.yml
