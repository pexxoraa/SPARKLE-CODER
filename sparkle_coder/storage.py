"""Select and relocate device storage while retaining the original as a backup."""

from contextlib import ExitStack
import json
from pathlib import Path
import shutil
import tempfile
import uuid

from .workspace import write_json
from .locking import LockError, workspace_lock


def _ignore_runtime_locks(directory, names):
    return set(names) & {"workspace.lock", "workspace.guard"} if Path(directory).name == ".nemotron" else set()


def _copy_projects(data, settings_path, projects_root, app_root, projects):
    """Copy while owning each source lock; leave busy registrations for a retry."""
    moved = []
    recovered = 0
    committed = False
    try:
        with tempfile.TemporaryDirectory(prefix="sparkle-migration-", dir=settings_path.parent.parent) as staging, ExitStack() as locks:
            staging = Path(staging)
            for project in projects:
                old = Path(project["path"]).resolve()
                if not old.is_dir():
                    project.pop("migration_pending", None)
                    continue
                if app_root.is_relative_to(old) or projects_root.is_relative_to(old):
                    raise ValueError("Place the SPARKLE CODER app folder outside the old project before copying it.")
                try:
                    status = locks.enter_context(workspace_lock(old / ".nemotron"))
                except (LockError, OSError) as exc:
                    project["migration_pending"] = str(exc)
                    continue
                recovered += int(status["recovered"])
                destination = projects_root / old.name
                if destination.exists() or destination.is_symlink():
                    destination = projects_root / (old.name + "-" + uuid.uuid4().hex[:8])
                if destination.exists() or destination.is_symlink():
                    raise ValueError(f"A project already occupies {destination}. Existing files were kept.")
                copy = staging / uuid.uuid4().hex
                shutil.copytree(old, copy, symlinks=True, ignore=_ignore_runtime_locks)
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
                project.pop("migration_pending", None)
            missing = [p["id"] for p in data.get("projects", []) if not Path(p["path"]).is_dir()]
            pending = [p["id"] for p in data.get("projects", []) if p.get("migration_pending")]
            migration = data.setdefault("storage_migration", {})
            total = migration.get("copied", 0) + len(moved)
            message = f"{total} project folder(s) copied into PROJECTS. The original folders were kept as backups."
            if missing:
                message += (f" {len(missing)} saved project folder(s) could not be found. Their names and paths were kept. "
                            "Use Find folder to reconnect them, or keep working in another project.")
            if pending:
                message += (f" {len(pending)} project(s) are waiting to move and remain in their original folders. "
                            "Close the previous app, then choose Retry project move. You can use another project now.")
            migration.update(copied=total, recovered_locks=migration.get("recovered_locks", 0) + recovered,
                             missing_project_ids=missing, pending_project_ids=pending, message=message)
            # Publish settings before releasing source locks. Copies do not carry
            # the PID marker or OS guard into their new locations.
            write_json(settings_path, data)
            committed = True
        return {"copied": len(moved), "pending": len(pending), "recovered_locks": recovered, "message": message}
    except Exception:
        if not committed:
            for path in reversed(moved):
                shutil.rmtree(path)
        raise


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
    projects = [p for p in data.get("projects", []) if Path(p["path"]).resolve().is_relative_to(source)
                or Path(p["path"]).resolve().is_relative_to(managed_root)]
    data["projects_path"] = str(projects_root)
    data["storage_migration"] = {"from": str(source)}
    try:
        _copy_projects(data, bootstrap / "settings.json", projects_root, bootstrap.parent, projects)
    except Exception as exc:
        raise ValueError(f"Projects could not be moved. Your original files remain at {source}. {exc}") from None


def retry_migration(app):
    data = json.loads(json.dumps(app.data))
    pending = [p for p in data["projects"] if p.get("migration_pending")]
    if not pending:
        return {"copied": 0, "pending": 0, "message": "No projects are waiting to move."}
    result = _copy_projects(data, app.settings_path, app.projects_directory, app.bootstrap.parent, pending)
    app.data = data
    return result


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
    # Hold project locks while copying; stale PID files use the same recovery as runs.
    lock_dirs = set()
    for item in old.rglob("*"):
        if item.is_symlink():
            raise ValueError(f"Data folder contains a symlink: {item.relative_to(old)}. Choose storage before adding linked files.")
        if item.name == "workspace.lock" and item.parent.name == ".nemotron":
            lock_dirs.add(item.parent)
    data = json.loads(json.dumps(app.data))
    copies = []
    for project in data["projects"]:
        source = Path(project["path"])
        if not source.is_dir():
            continue  # Keep unavailable registrations pointing to their original folders.
        if source.is_relative_to(old):
            project["path"] = str(destination / source.relative_to(old))
        elif source.is_relative_to(projects_root):
            project["path"] = str(destination / "PROJECTS" / source.relative_to(projects_root))
        if project["path"] != str(source):
            project["previous_paths"] = list(dict.fromkeys(project.get("previous_paths", []) + [str(source)]))
            copies.append((source, Path(project["path"])))
            lock_dirs.add(source / ".nemotron")
    try:
        with ExitStack() as locks:
            for state_dir in sorted(lock_dirs):
                locks.enter_context(workspace_lock(state_dir))
            def ignore(directory, names):
                return (_ignore_runtime_locks(directory, names)
                        | set(names) & {"instance.json", "storage-location.json", "launcher.log"})
            shutil.copytree(old, destination, dirs_exist_ok=True, ignore=ignore)
            if not projects_root.is_relative_to(old) and projects_root.exists():
                for source, target in copies:
                    if source.is_relative_to(projects_root):
                        shutil.copytree(source, target, symlinks=True, ignore=_ignore_runtime_locks)
            if any(not target.is_dir() for _, target in copies):
                raise ValueError("A project folder became unavailable while copying. Reconnect its drive and try again.")
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
