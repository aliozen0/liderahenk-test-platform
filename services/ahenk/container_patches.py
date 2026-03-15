from hooks import plugins, presence, registration, runtime, system

_APPLIED = False


def apply():
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True

    context = runtime.build_context()
    runtime.install_compat_modules()

    from slixmpp import ClientXMPP

    import base.agreement.confirm as confirm_mod
    import base.default_config.default_config as default_config_mod
    import base.execution.execution_manager as execution_mod
    import base.messaging.anonymous_messenger as anonymous_mod
    import base.messaging.messenger as messenger_mod
    import base.messaging.messaging as messaging_mod
    import base.registration.registration as registration_mod
    import base.system.system as system_mod
    import base.util.apt_helper as apt_helper_mod
    import base.util.util as util_mod
    from base.scope import Scope

    system.apply(
        confirm_mod,
        anonymous_mod,
        messaging_mod,
        execution_mod,
        registration_mod,
        util_mod,
        default_config_mod,
        system_mod,
        apt_helper_mod,
        context,
    )
    plugins.apply(execution_mod, messenger_mod)
    registration.apply(anonymous_mod, registration_mod, util_mod, system_mod, Scope, ClientXMPP, context)
    presence.apply(messenger_mod)

    runtime.log(f"runtime patches active for {context['agent_id']}")
