import json
import os
import shlex

NETWORK_POLICY_PATH = "/var/db/network-policy.json"


def load_network_policy():
    default = {"blocked": {"input": [], "output": []}}
    try:
        with open(NETWORK_POLICY_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        payload = default

    blocked = payload.setdefault("blocked", {})
    for direction in ("input", "output"):
        blocked.setdefault(direction, [])
    return payload


def save_network_policy(policy):
    os.makedirs(os.path.dirname(NETWORK_POLICY_PATH), exist_ok=True)
    with open(NETWORK_POLICY_PATH, "w", encoding="utf-8") as handle:
        json.dump(policy, handle, indent=2, sort_keys=True)


def handle_iptables_command(command):
    parts = shlex.split(str(command))
    if parts and parts[0] == "sudo":
        parts = parts[1:]
    if not parts:
        return None

    if parts[0] == "iptables-save":
        return 0, "", ""

    if parts[0] != "iptables":
        return None

    if "-L" in parts:
        return 0, render_iptables_list(), ""

    action = None
    direction = None
    for idx, part in enumerate(parts):
        if part in ("-A", "-D") and idx + 1 < len(parts):
            action = part
            direction = parts[idx + 1].strip().lower()
            break

    port = extract_port_from_iptables(parts)
    if action and direction in {"input", "output"} and port:
        policy = load_network_policy()
        blocked = set(policy["blocked"][direction])
        if action == "-A":
            blocked.add(port)
        else:
            blocked.discard(port)
        policy["blocked"][direction] = sorted(blocked, key=lambda item: int(item))
        save_network_policy(policy)
        return 0, "", ""

    return 0, "", ""


def extract_port_from_iptables(parts):
    for idx, part in enumerate(parts):
        if part == "--dport" and idx + 1 < len(parts):
            return parts[idx + 1]
        if part.startswith("--dport="):
            return part.split("=", 1)[1]
    return None


def render_iptables_list():
    policy = load_network_policy()
    lines = ["Chain INPUT"]
    for port in sorted(set(policy["blocked"]["input"])):
        lines.append(f"DROP       tcp  --  anywhere             anywhere             tcp dpt:{port}")
    lines.append("Chain OUTPUT")
    for port in sorted(set(policy["blocked"]["output"])):
        lines.append(f"DROP       tcp  --  anywhere             anywhere             tcp dpt:{port}")
    return "\n".join(lines) + "\n"
