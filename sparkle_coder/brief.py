"""User-owned project context, separate from model-authored memory."""

import json

from .workspace import WorkspaceError, sha256, write_json


def validate_brief(value):
    if not isinstance(value, dict) or set(value) != {"purpose", "requirements", "constraints"}:
        raise ValueError("A project brief needs a purpose, requirements, and constraints.")
    for field in ("purpose", "constraints"):
        if not isinstance(value[field], str) or len(value[field]) > 2000:
            raise ValueError("Keep the purpose and constraints under 2000 characters each.")
    requirements = value["requirements"]
    if (not isinstance(requirements, list) or len(requirements) > 20
            or any(not isinstance(item, str) or not item.strip() or len(item) > 300 for item in requirements)):
        raise ValueError("Use up to 20 requirements, with at most 300 characters on each line.")
    return {"purpose": value["purpose"].strip(), "constraints": value["constraints"].strip(),
            "requirements": list(dict.fromkeys(item.strip() for item in requirements))}


def read_brief(workspace):
    path = workspace.state_dir / "brief.json"
    if path.is_symlink():
        raise WorkspaceError("The project brief must not be a symlink.")
    if not path.exists():
        return {"brief": {"purpose": "", "requirements": [], "constraints": ""}, "revision": None}
    if path.stat().st_size > 32000 or path.stat().st_nlink > 1:
        raise WorkspaceError("The project brief is too large or is a hard-linked file.")
    raw = path.read_bytes()
    return {"brief": validate_brief(json.loads(raw)), "revision": sha256(raw)}


def save_brief(workspace, value, expected_revision):
    value = validate_brief(value)
    previous = read_brief(workspace)
    if previous["revision"] != expected_revision:
        raise ValueError("This brief changed in another window. Reopen it before saving your edits.")
    write_json(workspace.state_dir / "brief.json", value)
    return read_brief(workspace)


def task_requirements(brief):
    return [{"id": "req-" + sha256(text.encode())[:12], "text": text}
            for text in brief["requirements"]]
