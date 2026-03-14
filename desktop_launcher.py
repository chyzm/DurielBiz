import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from contextlib import ExitStack
from pathlib import Path


APP_NAME = "DurielBizPOS"
BROWSER_HOST = "127.0.0.1"
DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
PROJECT_ITEMS = [
    "accounts",
    "inventory",
    "notifications",
    "pos_system",
    "products",
    "purchases",
    "reports",
    "sales",
    "suppliers",
    "templates",
    "static",
    "manage.py",
]


def bind_host() -> str:
    return os.getenv("DURIELBIZ_BIND_HOST", DEFAULT_BIND_HOST)


def bind_port() -> int:
    try:
        return int(os.getenv("DURIELBIZ_PORT", str(DEFAULT_PORT)))
    except ValueError:
        return DEFAULT_PORT


def browser_url() -> str:
    return f"http://{BROWSER_HOST}:{bind_port()}/accounts/login/"


def bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def legacy_app_data_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / APP_NAME


def shared_app_data_dir() -> Path:
    program_data = os.getenv("PROGRAMDATA")
    if program_data:
        return Path(program_data) / APP_NAME
    return Path.home() / APP_NAME


def data_dir() -> Path:
    configured_path = os.getenv("DURIELBIZ_DATA_DIR")
    if configured_path:
        return Path(configured_path)
    return legacy_app_data_dir()


def runtime_dir() -> Path:
    configured_path = os.getenv("DURIELBIZ_RUNTIME_DIR")
    if configured_path:
        return Path(configured_path)
    return legacy_app_data_dir() / "runtime"


def migrate_runtime_data(target_root: Path) -> None:
    legacy_root = legacy_app_data_dir()
    if legacy_root == target_root or not legacy_root.exists() or target_root.exists():
        return
    project_items = [name for name in PROJECT_ITEMS if (legacy_root / name).exists()]
    if not project_items:
        return
    shutil.copytree(
        legacy_root,
        target_root,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("db.sqlite3", "launcher.log", "sync_service.log", "__pycache__", "*.pyc"),
    )


def migrate_legacy_database(target_root: Path) -> None:
    legacy_db = legacy_app_data_dir() / "db.sqlite3"
    target_db = target_root / "db.sqlite3"
    if target_db.exists() or not legacy_db.exists():
        return
    target_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy_db, target_db)


def sync_project_files(target_root: Path | None = None) -> Path:
    source_root = bundle_dir()
    runtime_root = target_root or runtime_dir()
    migrate_runtime_data(runtime_root)
    runtime_root.mkdir(parents=True, exist_ok=True)

    for item_name in PROJECT_ITEMS:
        source = source_root / item_name
        target = runtime_root / item_name
        if not source.exists():
            continue
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    migrate_legacy_database(data_dir())
    return runtime_root


def service_runtime_dir() -> Path:
    configured_path = os.getenv("DURIELBIZ_SERVICE_RUNTIME_DIR")
    if configured_path:
        return Path(configured_path)
    return shared_app_data_dir() / "sync-service-runtime"


def service_data_dir() -> Path:
    configured_path = os.getenv("DURIELBIZ_SERVICE_DATA_DIR")
    if configured_path:
        return Path(configured_path)
    return data_dir()


def service_sync_project_files() -> Path:
    runtime_root = service_runtime_dir()
    runtime_root.mkdir(parents=True, exist_ok=True)
    source_root = bundle_dir()
    for item_name in PROJECT_ITEMS:
        source = source_root / item_name
        target = runtime_root / item_name
        if not source.exists():
            continue
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    target_data_dir = service_data_dir()
    target_data_dir.mkdir(parents=True, exist_ok=True)
    migrate_legacy_database(target_data_dir)
    return runtime_root


def runtime_env(project_root: Path, *, data_root: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["DURIELBIZ_APP_DIR"] = str(project_root)
    env["DURIELBIZ_DESKTOP"] = "1"
    env["DURIELBIZ_DATA_DIR"] = str(data_root or data_dir())
    return env


def service_runtime_env(project_root: Path) -> dict[str, str]:
    env = runtime_env(project_root, data_root=service_data_dir())
    env["DURIELBIZ_SERVICE_MODE"] = "1"
    env["DURIELBIZ_RUNTIME_DIR"] = str(project_root)
    env["DURIELBIZ_SERVICE_RUNTIME_DIR"] = str(project_root)
    if getattr(sys, "frozen", False):
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def server_runtime_env(project_root: Path) -> dict[str, str]:
    env = runtime_env(project_root)
    env["DURIELBIZ_RUNTIME_DIR"] = str(project_root)
    if getattr(sys, "frozen", False):
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def is_server_running() -> bool:
    try:
        with socket.create_connection((BROWSER_HOST, bind_port()), timeout=1):
            return True
    except OSError:
        return False


def run_management_command(project_root: Path, command: list[str]) -> int:
    if "--serve" in command or "--migrate" in command:
        raise ValueError("Reserved launcher commands cannot be passed through run_management_command.")

    if getattr(sys, "frozen", False):
        process = subprocess.run(
            [sys.executable, "--manage", *command],
            cwd=project_root,
            env=runtime_env(project_root),
            check=False,
        )
    else:
        process = subprocess.run(
            [sys.executable, __file__, "--manage", *command],
            cwd=project_root,
            env=runtime_env(project_root),
            check=False,
        )
    return process.returncode


def wait_for_server(timeout_seconds: int = 25) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_server_running():
            return True
        time.sleep(1)
    return False


def server_command(project_root: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--serve"]
    return [sys.executable, __file__, "--serve"]


def autosync_command(project_root: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--manage", "run_autosync"]
    return [sys.executable, __file__, "--manage", "run_autosync"]


def launch_server(project_root: Path) -> subprocess.Popen:
    log_file = (project_root / "launcher.log").open("a", encoding="utf-8")
    return subprocess.Popen(
        server_command(project_root),
        cwd=project_root,
        env=server_runtime_env(project_root),
        stdout=log_file,
        stderr=log_file,
    )


def launch_autosync_worker(project_root: Path) -> subprocess.Popen:
    log_file = (project_root / "launcher.log").open("a", encoding="utf-8")
    return subprocess.Popen(
        autosync_command(project_root),
        cwd=project_root,
        env=server_runtime_env(project_root),
        stdout=log_file,
        stderr=log_file,
    )


def execute_django_command(project_root: Path, command_args: list[str]) -> int:
    os.chdir(project_root)
    sys.path.insert(0, str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pos_system.settings")

    from django.core.management import execute_from_command_line

    original_stdout = sys.stdout
    original_stderr = sys.stderr
    original_stdin = sys.stdin
    with ExitStack() as stack:
        if sys.stdout is None:
            sys.stdout = stack.enter_context((project_root / "launcher.log").open("a", encoding="utf-8"))
        if sys.stderr is None:
            sys.stderr = stack.enter_context((project_root / "launcher.log").open("a", encoding="utf-8"))
        if sys.stdin is None:
            sys.stdin = stack.enter_context(open(os.devnull, "r", encoding="utf-8"))
        try:
            execute_from_command_line(["manage.py", *command_args])
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            sys.stdin = original_stdin
    return 0


def serve_mode() -> int:
    project_root = Path(os.environ["DURIELBIZ_APP_DIR"])
    return execute_django_command(project_root, ["runserver", f"{bind_host()}:{bind_port()}", "--noreload"])


def manage_mode(arguments: list[str]) -> int:
    project_root = Path(os.environ.get("DURIELBIZ_APP_DIR") or sync_project_files())
    return execute_django_command(project_root, arguments)


def open_browser_once() -> None:
    webbrowser.open(browser_url(), new=1)


def main() -> int:
    if "--serve" in sys.argv:
        return serve_mode()

    if "--manage" in sys.argv:
        manage_index = sys.argv.index("--manage")
        return manage_mode(sys.argv[manage_index + 1 :])

    project_root = sync_project_files()

    if run_management_command(project_root, ["migrate", "--noinput"]) != 0:
        return 1

    if is_server_running():
        open_browser_once()
        return 0

    server = launch_server(project_root)
    autosync_worker = None
    if wait_for_server():
        autosync_worker = launch_autosync_worker(project_root)
        open_browser_once()
        try:
            return server.wait()
        finally:
            if autosync_worker and autosync_worker.poll() is None:
                autosync_worker.terminate()
                try:
                    autosync_worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    autosync_worker.kill()

    server.poll()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
