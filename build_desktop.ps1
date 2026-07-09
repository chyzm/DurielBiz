$ErrorActionPreference = "Stop"
$pyInstallerCommand = Join-Path $PSScriptRoot "env\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyInstallerCommand)) {
  $pyInstallerCommand = "pyinstaller"
}

# Bundling .env embeds SECRET_KEY/LICENSE_MASTER_KEY_HASH into every copy of this build.
# That's fine for LICENSE_MASTER_KEY_HASH (a one-way hash, safe to ship) but means every
# client running this exact build shares the same SECRET_KEY — acceptable here since each
# install's data is fully isolated locally, but generate a fresh .env per build if that
# matters for your deployment.
$envDataArgs = @()
if (Test-Path (Join-Path $PSScriptRoot ".env")) {
  $envDataArgs = @("--add-data", ".env;.")
}

$commonArgs = @(
  "--noconfirm",
  "--clean",
  "--onefile",
  "--add-data", "accounts;accounts",
  "--add-data", "cloudsync;cloudsync",
  "--add-data", "inventory;inventory",
  "--add-data", "invoicing;invoicing",
  "--add-data", "licensing;licensing",
  "--add-data", "notifications;notifications",
  "--add-data", "pos_system;pos_system",
  "--add-data", "products;products",
  "--add-data", "purchases;purchases",
  "--add-data", "reports;reports",
  "--add-data", "sales;sales",
  "--add-data", "suppliers;suppliers",
  "--add-data", "templates;templates",
  "--add-data", "static;static",
  "--add-data", "manage.py;."
) + $envDataArgs + @(
  "--collect-data", "tzdata",
  "--hidden-import", "django.core.management.commands.runserver",
  "--hidden-import", "django.core.management.commands.migrate",
  "--hidden-import", "django.contrib.staticfiles.management.commands.runserver",
  "--hidden-import", "whitenoise.middleware",
  "desktop_launcher.py"
)

& $pyInstallerCommand "--name" "DurielBizPOS" "--windowed" @commonArgs
& $pyInstallerCommand "--name" "DurielBizPOSAdmin" "--console" @commonArgs

$serviceArgs = @(
  "--noconfirm",
  "--clean",
  "--onedir",
  "--console",
  "--add-data", "accounts;accounts",
  "--add-data", "cloudsync;cloudsync",
  "--add-data", "inventory;inventory",
  "--add-data", "invoicing;invoicing",
  "--add-data", "licensing;licensing",
  "--add-data", "notifications;notifications",
  "--add-data", "pos_system;pos_system",
  "--add-data", "products;products",
  "--add-data", "purchases;purchases",
  "--add-data", "reports;reports",
  "--add-data", "sales;sales",
  "--add-data", "suppliers;suppliers",
  "--add-data", "templates;templates",
  "--add-data", "static;static",
  "--add-data", "manage.py;."
) + $envDataArgs + @(
  "--collect-data", "tzdata",
  "--hidden-import", "django.core.management.commands.migrate",
  "--hidden-import", "win32timezone",
  "--hidden-import", "whitenoise.middleware",
  "desktop_sync_service.py"
)

& $pyInstallerCommand "--name" "DurielBizPOSSyncService" @serviceArgs
