"""Stable check identities and an auditable history of agent-authored corrections."""

import hashlib


def check_key(command, cwd="."):
    return hashlib.sha256((cwd + "\0" + command).encode()).hexdigest()[:20]


def identify_checks(state):
    # Deterministic IDs let existing 0.4 sessions use the new correction tools.
    for index, check in enumerate(state.get("checks", [])):
        check.setdefault("key", check_key(check["command"], check.get("cwd", ".")))
        check.setdefault("id", "check-" + hashlib.sha256(
            f"{index}:{check['key']}:{check.get('at', '')}".encode()).hexdigest()[:12])
        check.setdefault("source", "user" if check.get("required") else "agent")


def replacements(state):
    return {key: revision for revision in state.get("check_revisions", [])
            for key in revision["old_keys"]}


def active_checks(state):
    identify_checks(state)
    retired = replacements(state)
    required = set(state.get("required_checks", []))
    latest = {}
    for check in state.get("checks", []):
        if check["key"] not in retired or check.get("required") or check["command"] in required:
            latest[check["key"]] = check
    return list(latest.values())


def effective_check(state, check_id):
    identify_checks(state)
    original = next((c for c in state.get("checks", []) if c["id"] == check_id), None)
    if original is None:
        return None
    key = original["key"]
    if original.get("required") or original["command"] in state.get("required_checks", []):
        return next((c for c in reversed(state["checks"]) if c["key"] == key), None)
    retired = replacements(state)
    visited = set()
    while key in retired:
        if key in visited:
            return None
        visited.add(key)
        key = retired[key]["new_key"]
    return next((c for c in reversed(state["checks"]) if c["key"] == key), None)


def proof_summary(state):
    current = state.get("verification_fingerprint")
    checks = active_checks(state)
    def status(check):
        if not check:
            return "not_checked"
        if not check.get("ok"):
            return "needs_fix"
        return "passed" if (current and check.get("fingerprint") == current
                            and check.get("environment_revision", 0) == state.get("environment_revision", 0)) else "needs_recheck"
    def combined(values):
        return ("needs_fix" if "needs_fix" in values else "not_checked" if not values or "not_checked" in values
                else "needs_recheck" if "needs_recheck" in values else "passed")
    features = []
    for item in state.get("delivery", {}).get("features", []):
        evidence = [effective_check(state, identity) for identity in item["check_ids"]]
        values = [status(check) for check in evidence]
        features.append({**item, "status": combined(values)})
    requirements = []
    for requirement in state.get("requirements", []):
        linked = [feature for feature in features if requirement["id"] in feature.get("requirement_ids", [])]
        requirements.append({**requirement, "status": combined([feature["status"] for feature in linked]),
                             "check_ids": list(dict.fromkeys(identity for feature in linked for identity in feature["check_ids"]))})
    return {"features": features, "requirements": requirements,
            "requirements_passed": sum(item["status"] == "passed" for item in requirements),
            "passed": sum(status(c) == "passed" for c in checks),
            "failed": sum(status(c) == "needs_fix" for c in checks), "total": len(checks),
            "needs_recheck": sum(status(c) == "needs_recheck" for c in checks),
            "note": "Check results come from actual runs. The agent links checks to features; those links still need review."}
