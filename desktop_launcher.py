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


def app_data_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_NAME
    return Path.home() / APP_NAME


def sync_project_files() -> Path:
    source_root = bundle_dir()
    target_root = app_data_dir()
    target_root.mkdir(parents=True, exist_ok=True)

    for item_name in PROJECT_ITEMS:
        source = source_root / item_name
        target = target_root / item_name
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

    return target_root


def is_server_running() -> bool:
    try:
        with socket.create_connection((BROWSER_HOST, bind_port()), timeout=1):
            return True
    except OSError:
        return False


def runtime_env(project_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["DURIELBIZ_APP_DIR"] = str(project_root)
    env["DURIELBIZ_DESKTOP"] = "1"
    return env


def server_runtime_env(project_root: Path) -> dict[str, str]:
    env = runtime_env(project_root)
    if getattr(sys, "frozen", False):
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


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


def launch_server(project_root: Path) -> subprocess.Popen:
    log_file = (project_root / "launcher.log").open("a", encoding="utf-8")
    return subprocess.Popen(
        server_command(project_root),
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
    if wait_for_server():
        open_browser_once()
        return server.wait()

    server.poll()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
