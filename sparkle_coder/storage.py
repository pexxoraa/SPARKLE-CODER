"""Select and relocate device storage while retaining the original as a backup."""

import json
from pathlib import Path
import shutil

from .workspace import write_json


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
    try:
        shutil.copytree(old, destination, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("instance.json", "storage-location.json", "launcher.log"))
        write_json(destination / "settings.json", data)
        # This pointer is the commit: the old data remains intact if copying fails.
        write_json(app.bootstrap / "storage-location.json", {"path": str(destination)})
    except Exception as exc:
        raise ValueError(f"Storage was not switched. Your original data remains at {old}. "
                         f"A partial copy may exist at {destination}: {exc}") from None
    app.directory = destination
    app.settings_path = destination / "settings.json"
    app.data = data
    return {"path": str(destination), "previous_path": str(old),
            "message": "Data copied and storage switched. The original folder was kept as a backup."}
