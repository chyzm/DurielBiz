$ErrorActionPreference = "Stop"
$pyInstallerCommand = Join-Path $PSScriptRoot "env\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyInstallerCommand)) {
  $pyInstallerCommand = "pyinstaller"
}

# Bundling .env embeds SECRET_KEY into every copy of this build. Generate a fresh
# .env per build if each deployment needs an isolated secret key.
$envDataArgs = @()
if (Test-Path (Join-Path $PSScriptRoot ".env")) {
  $envDataArgs = @("--add-data", ".env;.")
}

$commonArgs = @(
  "--noconfirm",
  "--clean",
  "--onefile",
  "--add-data", "accounts;accounts",
  "--add-data", "inventory;inventory",
  "--add-data", "notifications;notifications",
  "--add-data", "pos_system;pos_system",
  "--add-data", "products;products",
  "--add-data", "purchases;purchases",
  "--add-data", "reports;reports",
  "--add-data", "sales;sales",
  "--add-data", "suppliers;suppliers",
  "--add-data", "syncing;syncing",
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
