"""Select and relocate device storage while retaining the original as a backup."""

import json
from pathlib import Path
import shutil
import tempfile
import uuid

from .workspace import write_json


def migrate_legacy(bootstrap, projects_root, candidates):
    """Copy an old managed installation; publish its settings only after success."""
    if (bootstrap / "settings.json").exists() or (bootstrap / "storage-location.json").exists():
        return
    source_bootstrap = next((path for path in candidates if any(
        (path / name).exists() for name in ("settings.json", "storage-location.json"))), None)
    if source_bootstrap is None:
        return
    source = resolve_storage(source_bootstrap)
    settings = source / "settings.json"
    if settings.is_symlink():
        raise ValueError("The old settings file is a link. Open the original folder and review it before moving data.")
    data = json.loads(settings.read_text("utf-8"))
    managed_root = Path(data.get("projects_path", source / "Projects")).resolve()
    bootstrap.mkdir(parents=True, exist_ok=True, mode=0o700)
    projects_root.mkdir(parents=True, exist_ok=True)
    moved = []
    try:
        with tempfile.TemporaryDirectory(prefix="sparkle-migration-", dir=bootstrap.parent) as staging:
            staging = Path(staging)
            for project in data.get("projects", []):
                old = Path(project["path"]).resolve()
                if not old.is_relative_to(source) and not old.is_relative_to(managed_root):
                    continue  # Explicitly registered external projects stay where the user put them.
                if not old.is_dir():
                    raise ValueError(f"The old project folder is missing: {old}")
                if bootstrap.parent.is_relative_to(old) or projects_root.is_relative_to(old):
                    raise ValueError("Place the SPARKLE CODER app folder outside the old project before copying it.")
                if (old / ".nemotron").is_symlink() or (old / ".nemotron" / "workspace.lock").exists():
                    raise ValueError("Close the previous app and finish its active task before moving projects.")
                name = old.name
                destination = projects_root / name
                if destination.exists() or destination.is_symlink():
                    destination = projects_root / (name + "-" + uuid.uuid4().hex[:8])
                if destination.exists() or destination.is_symlink():
                    raise ValueError(f"A project already occupies {destination}. Existing files were kept.")
                copy = staging / uuid.uuid4().hex
                shutil.copytree(old, copy, symlinks=True)
                for path in (copy / ".nemotron" / "sessions").glob("*/state.json"):
                    if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink():
                        raise ValueError("A saved task contains linked history. Its original files were kept.")
                    session = json.loads(path.read_text("utf-8"))
                    session["previous_workspaces"] = list(dict.fromkeys(session.get("previous_workspaces", []) + [str(old)]))
                    session["workspace_root"] = str(destination)
                    session["verification_fingerprint"] = None
                    write_json(path, session)
                copy.rename(destination)
                moved.append(destination)
                project["previous_paths"] = list(dict.fromkeys(project.get("previous_paths", []) + [str(old)]))
                project["path"] = str(destination)
            data["projects_path"] = str(projects_root)
            data["storage_migration"] = {"from": str(source), "message":
                "Your managed projects and saved tasks were copied into PROJECTS. The original folders were kept as backups."}
            write_json(bootstrap / "settings.json", data)
    except Exception as exc:
        for path in reversed(moved):
            shutil.rmtree(path)
        raise ValueError(f"Projects could not be moved. Your original files remain at {source}. {exc}") from None


def resolve_storage(bootstrap):
    bootstrap = Path(bootstrap).expanduser().resolve()
    pointer = bootstrap / "storage-location.json"
    if pointer.is_symlink():
        raise ValueError("Storage configuration must not be a symlink.")
    if not pointer.exists():
        return bootstrap
    data = json.loads(pointer.read_text("utf-8"))
    destination = Path(data["path"])
    if not destination.is_absolute() or not (destination / "settings.json").is_file():
        raise ValueError("The selected data folder is unavailable. Reconnect its drive and reopen the app.")
    return destination.resolve()


def relocate(app, path):
    if not isinstance(path, str) or not Path(path).expanduser().is_absolute():
        raise ValueError("Choose an absolute device folder for your data.")
    destination = Path(path).expanduser().resolve()
    old = app.directory
    if destination == old:
        return {"path": str(old), "unchanged": True}
    if destination.is_relative_to(old) or old.is_relative_to(destination):
        raise ValueError("Choose a separate folder, outside the current data folder.")
    projects_root = app.projects_directory.resolve()
    if destination.is_relative_to(projects_root) or projects_root.is_relative_to(destination):
        raise ValueError("Choose a separate folder, outside the current PROJECTS folder.")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Choose an empty folder. Existing data will not be overwritten.")
    # Active symlinks and lock files would make a moved history unsafe or incomplete.
    for item in old.rglob("*"):
        if item.is_symlink():
            raise ValueError(f"Data folder contains a symlink: {item.relative_to(old)}. Choose storage before adding linked files.")
        if item.name == "workspace.lock":
            raise ValueError("A project is locked. Finish its other run before relocating data.")
    data = json.loads(json.dumps(app.data))
    for project in data["projects"]:
        source = Path(project["path"])
        if source.is_relative_to(old):
            project["path"] = str(destination / source.relative_to(old))
        elif source.is_relative_to(projects_root):
            project["path"] = str(destination / "PROJECTS" / source.relative_to(projects_root))
        if project["path"] != str(source):
            project["previous_paths"] = list(dict.fromkeys(project.get("previous_paths", []) + [str(source)]))
    try:
        shutil.copytree(old, destination, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("instance.json", "storage-location.json", "launcher.log"))
        if not projects_root.is_relative_to(old) and projects_root.exists():
            for project in app.data["projects"]:
                source = Path(project["path"])
                if source.is_relative_to(projects_root):
                    target = destination / "PROJECTS" / source.relative_to(projects_root)
                    if (source / ".nemotron" / "workspace.lock").exists():
                        raise ValueError("A project is locked. Finish its other run before moving it.")
                    shutil.copytree(source, target, symlinks=True)
        data["projects_path"] = str(destination / "PROJECTS")
        write_json(destination / "settings.json", data)
        # This pointer is the commit: the old data remains intact if copying fails.
        write_json(app.bootstrap / "storage-location.json", {"path": str(destination)})
    except Exception as exc:
        raise ValueError(f"Storage was not switched. Your original data remains at {old}. "
                         f"A partial copy may exist at {destination}: {exc}") from None
    app.directory = destination
    app.settings_path = destination / "settings.json"
    app.data = data
    app.projects_directory = destination / "PROJECTS"
    return {"path": str(destination), "previous_path": str(old),
            "message": "Data copied and storage switched. The original folder was kept as a backup."}
