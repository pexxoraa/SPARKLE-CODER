"""Bounded setup inspection. Never executes a command or imports project code."""

from collections import Counter
import json
from pathlib import PurePosixPath
import platform
import shutil
import sys
from urllib.parse import urlsplit

from .checks import discover_checks, package_manager
from .state import now


MANIFESTS = {"package.json", "pyproject.toml", "requirements.txt", "setup.cfg", "pytest.ini",
             "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts", "CMakeLists.txt"}
LANGUAGES = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript",
             ".tsx": "TypeScript", ".rs": "Rust", ".go": "Go", ".java": "Java", ".kt": "Kotlin",
             ".cs": "C#", ".c": "C", ".cpp": "C++", ".html": "HTML", ".css": "CSS",
             ".swift": "Swift", ".dart": "Dart", ".rb": "Ruby", ".php": "PHP"}


def inspect_setup(workspace, config, connection_tested=False):
    files = workspace.files(limit=10001)
    names = set(files[:10000])
    manifests = [name for name in files[:10000] if len(PurePosixPath(name).parts) <= 4
                 and (PurePosixPath(name).name in MANIFESTS or name.endswith((".csproj", ".sln")))]
    languages = Counter(LANGUAGES[PurePosixPath(name).suffix] for name in names
                        if PurePosixPath(name).suffix in LANGUAGES)
    items = []
    def add(identity, title, status, detail, next_step=""):
        items.append({"id": identity, "title": title, "status": status,
                      "detail": detail, "next_step": next_step})

    hosted = urlsplit(config.base_url).hostname == "integrate.api.nvidia.com"
    if hosted and not config.api_key:
        add("connection", "Nemotron connection", "attention", "The NVIDIA API key has not been added.",
            "Open Connect Nemotron, paste your API key, then choose Test connection.")
    elif connection_tested:
        add("connection", "Nemotron connection", "found", "The selected model was listed by this endpoint during this app session.",
            "A listed model still needs to respond successfully when you start a task.")
    else:
        add("connection", "Nemotron connection", "info", "Connection settings are present; a live connection has not been checked here.",
            "Use Test connection in Connect Nemotron.")
    needed = {}
    def need(command, title, source):
        needed.setdefault((command, title), []).append(source)

    for manifest in manifests[:80]:
        path = PurePosixPath(manifest)
        name = path.name
        if name == "package.json":
            data = {}
            try:
                data = json.loads(workspace.read(manifest)[0])
                if not isinstance(data, dict):
                    raise ValueError("Expected an object")
            except (OSError, ValueError, UnicodeError):
                add("manifest:" + manifest, "Project settings need a repair", "attention",
                    manifest + " could not be read as a JSON object.",
                    "Ask SPARKLE CODER to inspect this file before installing dependencies.")
            manager = package_manager(data, names, str(path.parent))
            if manager != "bun":
                need("node", "Node.js", manifest)
            need(manager, manager + " package manager", manifest)
        elif name in ("pyproject.toml", "requirements.txt", "setup.cfg", "pytest.ini"):
            need("__python__", "Python used by SPARKLE CODER", manifest)
        elif name == "Cargo.toml":
            need("cargo", "Rust toolchain", manifest)
        elif name == "go.mod":
            need("go", "Go toolchain", manifest)
        elif name in ("pom.xml", "build.gradle", "build.gradle.kts"):
            need("java", "Java runtime", manifest)
            need("javac", "Java compiler", manifest)
        elif name == "CMakeLists.txt":
            need("cmake", "CMake", manifest)
        elif manifest.endswith((".csproj", ".sln")):
            need("dotnet", ".NET tools", manifest)
    if config.execution == "docker":
        found = shutil.which("docker")
        add("docker", "Docker command", "found" if found else "attention",
            "Docker was found on this computer." if found else "Docker was not found on this computer's PATH.",
            "The Docker service, image, and tools inside the container still need a command check.")
        if needed:
            add("container-tools", "Tools inside Docker", "info",
                ", ".join(title for _, title in needed),
                "Host tools do not prove container readiness. Ask the agent to check the selected image.")
    else:
        for (command, title), sources in needed.items():
            found = sys.executable if command == "__python__" else shutil.which(command)
            detail = ("Found: " + found if found else "Not found on the PATH used by SPARKLE CODER.")
            if command == "__python__":
                detail += " · " + platform.python_version()
            add("tool:" + command, title, "found" if found else "attention", detail,
                ("Used by " + ", ".join(sources[:3]) + ". Versions and dependencies still need checking.") if found
                else "Install or enable " + title + ", then reopen SPARKLE CODER and check setup again.")
    git = shutil.which("git")
    add("git", "Git (optional)", "found" if git else "info",
        "Git is available for version control." if git else "Git was not found. File-based projects can still be used.")
    add("dependencies", "Project dependencies", "info",
        "Installed packages, compiler compatibility, and project behavior have not been tested by this scan.",
        "Start a Build task to check the environment and run the project's real tests.")
    discovered = discover_checks(workspace, config.execution, files=files)
    entry_names = {"README.md", "START_HERE.md", "index.html", "main.py", "app.py", "manage.py", "main.go", "main.rs"}
    entry_points = [name for name in files[:10000] if PurePosixPath(name).name in entry_names][:16]
    return {"at": now(), "execution": config.execution, "os": platform.system(), "items": items,
            "attention": sum(item["status"] == "attention" for item in items),
            "overview": {"file_count": len(names), "scan_truncated": len(files) > 10000 or len(manifests) > 80,
                         "languages": dict(languages.most_common(10)), "manifests": manifests[:80],
                         "entry_points": entry_points}, "checks": discovered["checks"],
            "note": "This scan reads filenames and settings and locates tools. It does not run, install, or verify software."}
