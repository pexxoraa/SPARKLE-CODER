"""User-operated imports, copies and exports, separate from model file tools."""

import base64
import binascii
import io
import mimetypes
import os
from pathlib import Path
import re
import zipfile

from .workspace import IGNORED_DIRS, SECRET_NAMES, SECRET_SUFFIXES, Workspace, atomic_write, sha256


FILE_LIMIT = 20 * 1024 * 1024
EXPORT_LIMIT = 100 * 1024 * 1024
EXPORT_FILES = 3000


class UserFiles(Workspace):
    @staticmethod
    def protected(parts):
        # Built software is downloadable; dependencies, state and credentials stay excluded.
        ignored = IGNORED_DIRS - {"dist", "build", "target"}
        return any(p in ignored or p.lower() in SECRET_NAMES or p.lower().startswith(".env.")
                   or Path(p).suffix.lower() in SECRET_SUFFIXES for p in parts)

    def bytes(self, relative):
        path = self.path(relative)
        with path.open("rb") as stream:
            data = stream.read(FILE_LIMIT + 1)
        if len(data) > FILE_LIMIT:
            raise ValueError("File exceeds the 20 MiB transfer limit. Open its device folder to copy it directly.")
        return data

    def preview(self, relative):
        path = self.path(relative)
        with path.open("rb") as stream:
            data = stream.read(200001)
        binary = b"\x00" in data
        try:
            content = data[:200000].decode("utf-8")
        except UnicodeDecodeError:
            content, binary = "", True
        return {"path": relative, "content": "" if binary else content, "binary": binary,
                "bytes": path.stat().st_size, "truncated": len(data) > 200000,
                "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream"}

    def available(self, relative):
        path = self.path(relative)
        if not path.exists():
            return relative
        rel = Path(relative)
        for index in range(1, 10000):
            candidate = (rel.parent / f"{rel.stem} (copy {index}){rel.suffix}").as_posix()
            if not self.path(candidate).exists():
                return candidate
        raise ValueError("Too many files with this name. Choose another destination.")

    def import_file(self, relative, encoded):
        if not isinstance(encoded, str) or len(encoded) > ((FILE_LIMIT + 2) // 3) * 4:
            raise ValueError("Each imported file must be at most 20 MiB.")
        self.path(relative)  # Validate before decoding or writing anything.
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Invalid uploaded file data.") from None
        if len(data) > FILE_LIMIT:
            raise ValueError("Each imported file must be at most 20 MiB.")
        destination = self.available(relative)
        target = self.path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation preserves an existing file, even after a simultaneous user edit.
        with target.open("xb") as stream:
            stream.write(data)
        return {"path": destination, "bytes": len(data), "sha256": sha256(data),
                "renamed": destination != relative}

    def duplicate(self, source, destination):
        data = self.bytes(source)
        return self.import_file(destination, base64.b64encode(data).decode("ascii"))

    def manifest(self):
        files = self.files(limit=EXPORT_FILES + 1)
        if len(files) > EXPORT_FILES:
            raise ValueError("Project export supports up to 3000 files. Copy a larger project in your file manager.")
        total = 0
        for name in files:
            size = self.path(name).stat().st_size
            if size > FILE_LIMIT:
                raise ValueError(f"{name} exceeds the 20 MiB file limit. Use your file manager for this export.")
            total += size
        if total > EXPORT_LIMIT:
            raise ValueError("Project export exceeds 100 MiB. Use the device folder for larger exports.")
        return {"files": files, "count": len(files), "bytes": total,
                "excludes": "Credentials, dependency folders, Git internals and agent history are excluded."}

    def archive(self):
        manifest = self.manifest()
        output = io.BytesIO()
        total = 0
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in manifest["files"]:
                data = self.bytes(name)
                total += len(data)
                if total > EXPORT_LIMIT:
                    raise ValueError("Project grew beyond the export limit. Try again after changes finish.")
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (self.path(name).stat().st_mode & 0xFFFF) << 16
                archive.writestr(info, data)
        return output.getvalue()

    def export_folder(self, destination, name):
        if not isinstance(destination, str) or not Path(destination).expanduser().is_absolute():
            raise ValueError("Choose an absolute device-folder path.")
        parent = Path(destination).expanduser().resolve()
        if parent.is_relative_to(self.root):
            raise ValueError("Choose a folder outside the current project.")
        manifest = self.manifest()
        parent.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", name).strip("-") or "project"
        for index in range(10000):
            target = parent / (stem if index == 0 else f"{stem}-{index}")
            try:
                target.mkdir()
                break
            except FileExistsError:
                continue
        else:
            raise ValueError("Choose another export folder.")
        copied = []
        try:
            for name in manifest["files"]:
                data = self.bytes(name)
                if sum(size for _, size in copied) + len(data) > EXPORT_LIMIT:
                    raise ValueError("Project grew beyond the export limit.")
                path = target / name
                atomic_write(path, data, self.path(name).stat().st_mode & 0o777)
                copied.append((name, len(data)))
        except Exception as exc:
            raise ValueError(f"Export stopped after {len(copied)} files. Partial copy is in {target}: {exc}") from None
        return {"path": str(target), "files": len(copied), "bytes": sum(size for _, size in copied)}
