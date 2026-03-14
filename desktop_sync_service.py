import logging
import os
import socket
import sys
import traceback
from getpass import getuser

import servicemanager
import win32event
import win32service
import win32serviceutil

from desktop_launcher import execute_django_command, service_runtime_env, service_sync_project_files


SERVICE_NAME = "DurielBizPOSSyncService"
SERVICE_DISPLAY_NAME = "DurielBiz POS Sync Service"
SERVICE_DESCRIPTION = "Runs background automatic cloud sync for DurielBiz POS."
DEFAULT_SLEEP_SECONDS = 60


class DurielBizPOSSyncService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args):
        super().__init__(args)
        socket.setdefaulttimeout(30)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.project_root = service_sync_project_files()
        self.logger = self._build_logger()

    def _build_logger(self):
        logger = logging.getLogger(SERVICE_NAME)
        if logger.handlers:
            return logger
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(self.project_root / "sync_service.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        return logger

    def log(self, message, level=logging.INFO):
        self.logger.log(level, message)
        try:
            servicemanager.LogInfoMsg(f"{SERVICE_NAME}: {message}")
        except Exception:
            pass

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.log("Stop requested.")
        win32event.SetEvent(self.stop_event)

    def setup_django(self):
        os.environ.update(service_runtime_env(self.project_root))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pos_system.settings")
        execute_django_command(self.project_root, ["migrate", "--noinput"])
        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))
        import django

        django.setup()
        from reports.models import BusinessSettings
        from reports.services import run_scheduled_cloud_sync

        return BusinessSettings, run_scheduled_cloud_sync

    def run_loop(self):
        BusinessSettings, run_scheduled_cloud_sync = self.setup_django()
        self.log(f"Using runtime directory {self.project_root}")
        while True:
            settings_obj = BusinessSettings.get_solo()
            result = run_scheduled_cloud_sync(settings_obj=settings_obj)
            if result["ok"]:
                self.log(result["message"])
            elif "already running" in result["message"] or "not due yet" in result["message"]:
                self.log(result["message"], level=logging.DEBUG)
            else:
                self.log(result["message"], level=logging.WARNING)

            wait_result = win32event.WaitForSingleObject(self.stop_event, DEFAULT_SLEEP_SECONDS * 1000)
            if wait_result == win32event.WAIT_OBJECT_0:
                self.log("Service loop stopped.")
                break

    def SvcDoRun(self):
        self.log("Service started.")
        try:
            self.run_loop()
        except Exception:
            self.log(traceback.format_exc(), level=logging.ERROR)
            raise


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        print("Usage: DurielBizPOSSyncService.exe [options] install|update|remove|start|stop|restart|debug")
        print("Recommended install for shared shop data:")
        print(f'  DurielBizPOSSyncService.exe --username ".\\\\{getuser()}" --password YOUR_PASSWORD --startup auto install')
        raise SystemExit(0)
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(DurielBizPOSSyncService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(DurielBizPOSSyncService)
