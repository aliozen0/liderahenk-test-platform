"""
Backward compatibility proxy — original monolith has been decomposed into
``platform_runtime.readiness`` sub-package.  All public symbols are
re-exported here so that existing callers continue to work without changes.
"""
from platform_runtime.readiness import *  # noqa: F401,F403

# Re-export private symbols that tests or scripts may reference directly
from platform_runtime.readiness import (  # noqa: F401
    _utc_now,
    _profile_name,
    _topology_summary,
    _registration_parity_check,
    _run_pytest_check,
    _scenario_runner_registry,
    _scenario_operational_checks,
    _collect_membership_snapshot,
    _run_membership_snapshot_contract_check,
    _run_session_effect_contract_check,
    _summarize_user_group_tree,
    _iter_tree_children,
    _node_membership_count,
)
from platform_runtime.readiness.checks import (  # noqa: F401
    build_check as _build_check,
    summarize_checks as _summarize_checks,
)
from platform_runtime.readiness.containers import (  # noqa: F401
    compose_ps as _compose_ps,
    compose_stack as _compose_stack,
    containers_by_service as _containers_by_service,
    normalize_state as _normalize_state,
    service_state_report as _service_state_report,
)
from platform_runtime.readiness.connectivity import (  # noqa: F401
    http_get as _http_get,
    http_post as _http_post,
    port_open as _port_open,
    prom_query as _prom_query,
    core_connectivity_checks as _core_connectivity_checks,
    observability_checks as _observability_checks,
)
from platform_runtime.readiness.mutation_support import (  # noqa: F401
    MUTATION_STEP_CAPABILITIES,
    SESSION_STEP_CAPABILITIES,
    mutation_step_support as _mutation_step_support,
    session_step_support as _session_step_support,
    session_support_summary as _session_support_summary,
    support_summary as _support_summary,
)
from platform_runtime.readiness.policy_roundtrip import (  # noqa: F401
    find_group_entry as _find_group_entry,
    create_computer_group_with_reconciliation as _create_computer_group_with_reconciliation,
    cleanup_roundtrip_artifacts as _cleanup_roundtrip_artifacts,
    policy_roundtrip_failure_details as _policy_roundtrip_failure_details,
    run_policy_roundtrip_check as _run_policy_roundtrip_check,
)
from platform_runtime.readiness.service_logs import (  # noqa: F401
    tail_service_logs as _tail_service_logs,
    search_service_logs as _search_service_logs,
)

# Keep module-level constants accessible
DEFAULT_PLATFORM_ARTIFACTS_DIR = None  # imported via star
FALLBACK_PLATFORM_ARTIFACTS_DIR = None  # imported via star
from platform_runtime.readiness import (  # noqa: F401,E402
    DEFAULT_PLATFORM_ARTIFACTS_DIR,
    FALLBACK_PLATFORM_ARTIFACTS_DIR,
)
