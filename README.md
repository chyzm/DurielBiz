# DurielBiz POS

Built by `DurielTech`, an IT company delivering operational software for healthcare, retail, mobility, and business automation.

Desktop-first point of sale system built with Django. The project is designed to run locally for a shop on `127.0.0.1:9000`, while keeping the codebase modular enough for later sync, remote reporting, and multi-branch expansion.

## Current scope

- Public DurielTech landing page at `/`
- Offline-first Django deployment with SQLite by default
- Role-restricted workflow for admin, cashier, manager, and inventory officer
- Product, category, supplier, inventory, purchase, and sales modules
- POS terminal with dual checkout lanes
- Loyalty customers with saved redeem preferences
- Activity logging for admin review
- Branded receipt modal with business settings
- Paginated list and table views across operational screens
- Branch management with default-branch transaction tagging
- Token-protected sync export endpoint for remote dashboards
- Optional automatic scheduled sync from local POS to cloud dashboard
- Optional Windows background sync service for scheduled sync that survives app/browser restarts
- 80mm thermal receipt print styling
- Toast-based expiry notifications
- Admin-only sales history by date
- Desktop packaging entrypoint with PyInstaller support
- 14-day desktop trial with single-master-key, machine-locked activation

## Email and passwords

- Cloud password reset is available at `/accounts/password-reset/`
- Authenticated users can change their password at `/accounts/password-change/`
- SMTP/admin email settings are loaded from `.env`
- `.env.example` documents the supported email variables
- Encrypted `.env` values are supported with `ENC(...)` plus `DURIELBIZ_ENV_KEY`
- Generate an encryption key with:
  - `python manage.py encrypt_env_value --generate-key`
- Encrypt a secret for `.env` with:
  - `python manage.py encrypt_env_value --value "your-secret" --key "your-fernet-key"`

## Implemented modules

### Accounts

- Custom `User` model with role field
- Login/logout flow
- Admin center and user management pages
- Activity log for logins and tracked business actions

### Products

- Product CRUD
- Category CRUD
- Barcode field support
- Cost price, selling price, quantity, expiry date, supplier linkage
- Low-stock and expiry-aware usage in reports and notifications

### Suppliers

- Supplier CRUD
- Supplier linkage from products and purchases

### Inventory

- Inventory overview
- Manual stock adjustment form
- Inventory log entries for stock changes caused by purchases and sales

### Purchases

- Purchase receive form
- Purchase history list
- Stock increment service on goods receipt

### Sales / POS

- Product search and barcode-style lookup
- Dual checkout lanes: `Checkout A` and `Checkout B`
- Cart persistence per lane in browser `sessionStorage`
- Admin-only cart item removal and cart clear actions
- Paid amount auto-syncs when quantities or redeemed points change
- Receipt opens as an in-page modal, not a new tab

### Loyalty

- Customer records created or matched by phone number
- Automatic point accrual after completed sales
- Point redemption during checkout
- Per-customer saved redeem preference via `preferred_redeem_points`
- Admin customer list, detail, and edit screens

### Reports

- Dashboard cards and summary metrics
- Revenue and profit aggregates
- Low stock and expiring product visibility
- Business settings for receipt branding, branch defaults, sync configuration, and loyalty rules

### Branches and Sync

- Branch CRUD for multi-branch deployments
- Default branch assignment on sales, purchases, and inventory logs
- Sync export endpoint at `/sync/export/` for cloud dashboard ingestion
- Token-based access for external sync clients, with admin override from an authenticated session

### Notifications

- Expiring product endpoint
- Frontend toast notification at bottom-right
- Auto-dismiss behavior instead of browser `alert()`

## Role access matrix

### Admin

- Full access to dashboard, POS, products, categories, suppliers, inventory, purchases, reports, business settings, customers, sales history, activity logs, and user management

### Cashier

- Dashboard
- POS terminal

### Inventory Officer

- Products
- Categories
- Suppliers
- Purchases
- Inventory

### Manager

- Dashboard only

Role enforcement is implemented server-side. Sidebar navigation also hides modules the current role should not access.

## Loyalty rules

### Global settings

Configured in Business Settings:

- `loyalty_points_per_1000`
- `loyalty_cash_value_per_point`
- Business name, phone, address, and receipt footer

### Customer-level setting

Each loyalty customer now has:

- `preferred_redeem_points`

This value is saved per customer and used to prefill the POS redeem field when the cashier enters that customer’s phone number. The POS caps the prefilled value to the customer’s currently available points, so it does not over-redeem.

### Sale behavior

- Customer is matched or created by phone number
- Redeemed points reduce sale total using `loyalty_cash_value_per_point`
- Awarded points are calculated from the final completed sale total
- Customer balance is reduced by redeemed points, then increased by newly awarded points

## Admin activity log

The system records:

- User logins
- Completed sales
- Customer loyalty edits
- Other tracked business actions wired through the shared logging helper

Admin can review logs from the activity log page.

## POS behavior

### Dual checkout lanes

- Two independent lanes run on one browser session
- Each lane stores its own cart, customer data, payment method, note, and loyalty state
- Completing one lane resets only that lane

### Cart permissions

- Only admin can remove an item from cart directly
- Only admin can clear the whole cart
- Cashiers can still increase quantities

### Receipt flow

- Sale completes on the POS page
- Receipt opens in a modal
- Print uses the same modal content
- Receipt branding uses Business Settings

## Main routes

- `/` DurielTech landing page
- `/dashboard/` local POS dashboard
- `/accounts/login/`
- `/accounts/activity-log/`
- `/products/`
- `/products/categories/`
- `/suppliers/`
- `/inventory/`
- `/purchases/`
- `/purchases/receive/`
- `/sales/pos/`
- `/sales/history/`
- `/sales/customers/`
- `/branches/`
- `/reports/settings/business/`
- `/sync/export/`
- `/notifications/expiring-products/`

## Project structure

```text
DurielBiz/
├── accounts/
├── inventory/
├── notifications/
├── pos_system/
├── products/
├── purchases/
├── reports/
├── sales/
├── suppliers/
├── templates/
├── build_desktop.ps1
├── desktop_launcher.py
├── manage.py
└── requirements.txt
```

## Local development setup

### 1. Create and activate a virtual environment

```powershell
python -m venv env
.\env\Scripts\activate
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Run migrations

```powershell
python manage.py makemigrations
python manage.py migrate
```

### 4. Create an admin user

```powershell
python manage.py createsuperuser
```

### 5. Start the server

```powershell
python manage.py runserver
```

Open `http://127.0.0.1:9000/`.

## Business setup checklist

After first login:

1. Create users and assign roles
2. Open Business Settings and set:
   - business name
   - address
   - phone
   - receipt footer
   - loyalty point rules
3. Add suppliers
4. Add categories
5. Add products
6. Receive opening stock through Purchases

## Sales readiness checklist

Use this checklist before selling or deploying to a client:

1. Confirm `LICENSE_MASTER_KEY_HASH` is set in `.env` before building, if this client's build should enforce the trial/license
2. Build fresh desktop binaries with `build_desktop.ps1`
3. Rebuild the installer with `build_installer.ps1`
4. Test the installer on a clean Windows machine
5. Create a sample admin user and verify login
6. Set Business Settings:
   - business name
   - phone
   - address
   - receipt footer
   - default branch
   - VAT rate, if applicable
7. Test a full flow:
   - create product
   - add stock
   - make sale, review the order, then confirm & print
   - view dashboard
8. If remote monitoring is included:
   - create cloud account
   - copy sync token and ingest URL
   - enable cloud sync locally
   - run `Sync Now`
   - verify cloud dashboard receives data
9. Once the client is ready to pay, open their activation screen and enter your saved activation key (see [Licensing](#licensing-trial--activation))
10. Deliver the client handoff items:
    - installer
    - admin login
    - confirmation the app is activated (or that the trial is running)
    - backup path
    - support contact

## Client handoff

Provide these to the buyer at delivery:

- Installer: `dist\installer\DurielBizPOS-Setup.exe`
- Admin tool: `dist\DurielBizPOSAdmin.exe`
- Local data path: `%LOCALAPPDATA%\DurielBizPOS\db.sqlite3`
- Local runtime log: `%LOCALAPPDATA%\DurielBizPOS\runtime\launcher.log`
- Activation done on-site if the client has already paid (see [Licensing](#licensing-trial--activation)) — otherwise they get a 14-day trial automatically
- Support contact:
  - `07031016787`
  - `info@durieltech.com.ng`

## About & support page

The app includes an authenticated support page at:

- `/accounts/about-support/`

It shows:

- DurielTech branding
- current product version
- support phone and email
- deployment modes
- release and handoff notes

## Desktop packaging

The project includes a launcher for desktop-style use.

### Build executable

```powershell
pip install pyinstaller
powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1
```

### Output

- Windowed app is generated in `dist\DurielBizPOS.exe`
- Console admin tool is generated in `dist\DurielBizPOSAdmin.exe`
- Windows sync service bundle is generated in `dist\DurielBizPOSSyncService\`
- `desktop_launcher.py` copies the packaged Django project into the packaged runtime directory
- The launcher runs migrations automatically, starts Django locally, and opens the POS only after the server is reachable

This is the current desktop strategy:

- backend runs locally
- UI opens in the system browser
- suitable for packaging as a lightweight Windows desktop install

## Licensing (trial & activation)

The desktop build includes a 14-day trial and a single-master-key activation system, implemented in the `licensing` app. It only ever applies to the packaged desktop app — the cloud dashboard and local development (`manage.py runserver`) are never gated.

### How it works

- **Trial**: the first time the app runs on a machine, it silently starts a 14-day trial. The countdown is stored in two places — a signed file in the app's data directory and a signed value in the Windows registry (`HKEY_CURRENT_USER\Software\DurielTech\DurielBizPOS`). Whichever of the two records the *earlier* start date wins, so deleting or editing just one of them does not reset or extend the trial.
- **One activation key, known only to you**: there is a single master activation key. You type the same key into any client's activation screen when they've paid. The app never stores or ships the plaintext key — only a SHA-256 hash of it (`LICENSE_MASTER_KEY_HASH` in `.env`), so the key itself can't be recovered from a shipped build.
- **Machine lock happens at the moment of activation**: when the correct key is entered, the app records *that machine's* current hardware fingerprint (from its Windows `MachineGuid`) as the activated fingerprint. Every subsequent request re-derives the current machine's fingerprint and compares it to what was recorded — so if someone copies an already-activated install (files and/or data folder) to a different PC, that copy's fingerprint won't match and it will not show as licensed there.
- **Lockout**: once the trial runs out and the machine isn't activated, every page redirects to `/licensing/activate/`, which shows the machine's ID (for your support records) and a field for the activation key. Nothing else in the app is reachable until it's activated.
- **Enforcement switch**: the whole system is inert unless both are true: `DURIELBIZ_DESKTOP=1` (set automatically by `desktop_launcher.py`) and `LICENSE_MASTER_KEY_HASH` is set in `.env`. Leave `LICENSE_MASTER_KEY_HASH` blank to ship a build with no trial/licensing enforcement at all.

### Vendor workflow

1. Generate the master key **once**, on your own machine:

```powershell
python manage.py generate_master_key
```

This prints the plaintext **activation key** and its **hash**. Save the plaintext key somewhere offline and secret (password manager, etc.) — this is the one key you'll type into every client's activation screen when they pay. Paste only the **hash** into `LICENSE_MASTER_KEY_HASH` in `.env` before building the distributable; it's safe to ship since a hash can't be reversed back into the key.

2. When a client is ready to pay (or you're setting them up), open their activation screen (`/licensing/activate/`, shown automatically once the trial ends, or reachable anytime) and type in your saved activation key. That machine is now activated — no fingerprint exchange, no per-client key generation, no internet connection needed.

### Client-facing behavior

- The activation page shows the trial countdown while it's still running.
- On expiry, the app locks to `/licensing/activate/` with the machine's ID displayed (informational, for support) and an "Activation key" field.
- Activation is a one-time action per machine; the recorded fingerprint is re-checked on every request, not just cached as a flag.

### Security notes

- The activation key is never shipped in plaintext — only its SHA-256 hash lives in the built app, so extracting the build doesn't reveal the key.
- Because the same key activates any machine you type it into, its secrecy is what protects against unlimited activations — treat it like a master password. If it ever leaks, rotate it: generate a new one, update `LICENSE_MASTER_KEY_HASH`, and rebuild.
- What *is* strongly protected: an already-activated install cannot be copied to a second machine and remain licensed there, because the fingerprint check is re-derived locally every time, not carried in a portable token.
- The dual-stored trial start date is a reasonable deterrent against casually deleting the app's data folder to "restart" the trial, not a guarantee against a determined, technically skilled attacker patching the app itself. There is no purely offline desktop licensing scheme that fully defeats that threat.
- Relevant files: `licensing/fingerprint.py`, `licensing/state.py`, `licensing/services.py`, `licensing/middleware.py`, `licensing/management/commands/generate_master_key.py`.

## Offline desktop install

Use this when the shop computer should run the POS without internet.

### Option 1: Run from source on Windows

1. Install Python 3.12+ on the shop computer
2. Copy the project folder to the computer
3. Open PowerShell inside the project folder
4. Create the environment:

```powershell
python -m venv env
.\env\Scripts\activate
pip install -r requirements.txt
```

5. Prepare the local database:

```powershell
python manage.py migrate
python manage.py createsuperuser
```

6. Start the POS locally:

```powershell
python manage.py runserver 127.0.0.1:9000
```

7. Open `http://127.0.0.1:9000/` in the browser

This keeps all data on that desktop in the local `db.sqlite3` file.

### Option 2: Build a Windows executable

Build on a prepared machine, then move the output to the shop PC:

```powershell
pip install pyinstaller
powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1
```

The generated app is `dist\DurielBizPOS.exe`.

Important runtime behavior:

- On first launch, the EXE prepares a local working copy in `%LOCALAPPDATA%\DurielBizPOS\runtime`
- The local SQLite database is stored in `%LOCALAPPDATA%\DurielBizPOS\db.sqlite3` by default
- Older `%LOCALAPPDATA%\DurielBizPOS\db.sqlite3` continues to be reused automatically
- First launch may take a few seconds because migrations run automatically
- Rebuild the EXE after launcher changes; the current build keeps the PyInstaller runtime alive so the local Django server does not lose bundled files
- The build now bundles `tzdata`, so `Africa/Lagos` resolves correctly on offline Windows machines

### Option 3: Build a Windows installer

Use this if you want a normal installer with Start Menu and desktop shortcuts.

1. Build the desktop EXE first:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1
```

2. Install Inno Setup 6 on the build machine.
3. Build the installer:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
```

4. Distribute the installer from:

```text
dist\installer\DurielBizPOS-Setup.exe
```

To prevent Windows from showing `Unknown publisher`, the installer must be signed with a real code-signing certificate. The release build supports signing when these environment variables are set:

- `DURIELTECH_SIGNTOOL_PATH`
- `DURIELTECH_SIGN_PFX`
- `DURIELTECH_SIGN_PFX_PASSWORD`
- optional `DURIELTECH_TIMESTAMP_URL`

Without a certificate, Windows will still show `Unknown publisher` even if the installer metadata says `DurielTech`.

Installer behavior:

- Installs the EXE to `C:\Program Files\DurielBizPOS`
- Creates Start Menu shortcut
- Optionally creates a desktop shortcut
- Stores the desktop app runtime under `%LOCALAPPDATA%\DurielBizPOS\runtime`
- The Windows background sync service is packaged, but install it manually when needed
- Uninstall removes the app files and local app data for that Windows user

### Create an admin user for the desktop app

Open PowerShell in the folder that contains `DurielBizPOSAdmin.exe`, then run:

```powershell
.\DurielBizPOSAdmin.exe --manage createsuperuser
```

That creates the login user inside the desktop app's local database in `%LOCALAPPDATA%\DurielBizPOS\db.sqlite3` by default.

You can also run other Django management commands the same way:

```powershell
.\DurielBizPOSAdmin.exe --manage changepassword USERNAME
.\DurielBizPOSAdmin.exe --manage shell
```

### Recommended offline deployment notes

- Keep regular backups of `db.sqlite3`
- Put the project folder in a simple path such as `C:\DurielBiz`
- Create a desktop shortcut to `DurielBizPOS.exe` or the server start command
- If Windows Firewall prompts, allow local access for private networks
- Use a UPS if the system will be used in a shop with unstable power

### Update an installed desktop app

Use this when you have changed the code and need the shop PC to run the new version.

1. Build fresh desktop binaries on the build machine:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1
```

2. If you distribute with the installer, rebuild it too:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_installer.ps1
```

3. On the shop PC, close the running app completely.
4. Replace the old `DurielBizPOS.exe` with the new one, or run the new installer.
5. Start the app again.
6. On first launch after update, the app refreshes files in `%LOCALAPPDATA%\DurielBizPOS\runtime` and runs any pending migrations automatically.

Important:

- Business data stays in `%LOCALAPPDATA%\DurielBizPOS\db.sqlite3` by default
- Replacing the EXE does not delete existing data
- If a release includes a new migration, let the first launch finish before closing the app

### Windows background sync service

The desktop build now includes a real Windows service for cloud sync:

- `dist\DurielBizPOSSyncService\DurielBizPOSSyncService.exe`
- Service name: `DurielBizPOSSyncService`
- Service runtime: `C:\ProgramData\DurielBizPOS\sync-service-runtime`
- Shared data depends on the account the service runs under unless `DURIELBIZ_DATA_DIR` is set explicitly

This service keeps scheduled cloud sync running even when the POS window or browser is closed. For it to use the same local database as the desktop app, install it under the same Windows user account as the shop app, or set `DURIELBIZ_DATA_DIR` explicitly before installation.

#### Install manually

```powershell
powershell -ExecutionPolicy Bypass -File .\build_desktop.ps1
powershell -ExecutionPolicy Bypass -File .\install_sync_service.ps1 -Username ".\YOUR_WINDOWS_USER" -Password "YOUR_WINDOWS_PASSWORD"
```

#### Remove manually

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall_sync_service.ps1
```

#### Direct service commands

```powershell
.\dist\DurielBizPOSSyncService\DurielBizPOSSyncService.exe --startup auto install
.\dist\DurielBizPOSSyncService\DurielBizPOSSyncService.exe start
.\dist\DurielBizPOSSyncService\DurielBizPOSSyncService.exe stop
.\dist\DurielBizPOSSyncService\DurielBizPOSSyncService.exe remove
```

#### Logs

- Desktop launcher: `%LOCALAPPDATA%\DurielBizPOS\runtime\launcher.log`
- Sync service: `C:\ProgramData\DurielBizPOS\sync-service-runtime\sync_service.log`

## Remote viewing

There are two practical ways to view data remotely with the current codebase.

### Option 1: View over local network

Use this if the phone or another PC is on the same Wi‑Fi/LAN as the POS computer.

#### Step by step with the desktop EXE

1. Install and test the app normally on the shop PC.
2. On the shop PC, find the IPv4 address:

```powershell
ipconfig
```

3. Note the IPv4 address for the active network adapter, for example `192.168.1.25`.
4. Open Windows Defender Firewall and allow inbound TCP port `9000` on the Private network profile.
5. Start the app from PowerShell with LAN binding enabled:

```powershell
$env:DURIELBIZ_BIND_HOST="0.0.0.0"
$env:DURIELBIZ_ALLOWED_HOSTS="127.0.0.1,localhost,192.168.1.25"
.\DurielBizPOS.exe
```

6. On the shop PC, the browser still opens locally.
7. On a phone or another PC on the same Wi‑Fi, open:

```text
http://192.168.1.25:9000/
```

8. Log in with an existing app user.

#### Step by step from source

1. Find the shop computer IP address:

```powershell
ipconfig
```

2. Start Django on all interfaces and allow the host:

```powershell
$env:DURIELBIZ_ALLOWED_HOSTS="127.0.0.1,localhost,192.168.1.25"
python manage.py runserver 0.0.0.0:9000
```

3. Open from another device on the same network:

```text
http://192.168.1.25:9000/
```

This is the simplest remote view option for a single location.

### Option 2: Cloud dashboard sync

Use this if you want true remote viewing outside the shop network.

Current support in this project:

- Business Settings stores:
  - `cloud_sync_enabled`
  - `cloud_sync_token`
  - `sync_dashboard_url`
- Export payload generation is available locally
- Push sync is available through the `Sync Now` action
- Cloud ingest endpoint is available at `/cloud/api/ingest/`

#### Step by step

1. Deploy this project to PythonAnywhere for the cloud dashboard.
2. In the shop POS, open Business Settings.
3. Enable cloud sync.
4. Create a cloud business account from `/accounts/signup/`.
5. Open `/cloud/settings/` and copy:
   - the sync token
   - the ingest URL
6. Set `cloud_sync_token` on the local POS to the token copied from the cloud dashboard.
7. Set `sync_dashboard_url` on the local POS to the ingest URL copied from the cloud dashboard.
8. Use `Sync Now` from local Business Settings.
9. The local POS pushes branches, sales, purchases, and inventory logs to the cloud dashboard.
10. Open the cloud dashboard from your phone or browser anywhere.

Current limitation:

- Sync is manual through the `Sync Now` button
- Automatic scheduled sync can still be added later if needed

### Security note for remote viewing

- Do not expose the local Django server directly to the public internet in `DEBUG=True`
- For internet access, use a proper hosted server, HTTPS, authentication, and firewall rules
- Treat `cloud_sync_token` like a password

## Cloud dashboard for multiple businesses

The project now includes a cloud dashboard module for multi-business remote monitoring.

### What it does

- lets each business create its own online dashboard account
- isolates cloud data per business
- receives synced data from local POS deployments
- shows synced branches and sales remotely

### Main cloud routes

- `/accounts/signup/` creates a cloud business account
- `/cloud/` cloud dashboard overview
- `/cloud/sales/` synced remote sales
- `/cloud/branches/` synced branch list
- `/cloud/settings/` sync token and ingest URL
- `/cloud/api/ingest/` sync ingest endpoint for local POS

### Cloud models

- `cloudsync.Business`
- `cloudsync.BusinessMembership`
- `cloudsync.SyncCredential`
- `cloudsync.RemoteBranch`
- `cloudsync.RemoteSale`
- `cloudsync.RemoteSaleItem`
- `cloudsync.RemotePurchase`
- `cloudsync.RemotePurchaseItem`
- `cloudsync.RemoteInventoryLog`
- `cloudsync.SyncEvent`

### Local POS to cloud sync

1. Deploy this project to PythonAnywhere for the cloud dashboard.
2. Create a business account from:

```text
/accounts/signup/
```

3. Open cloud sync settings from:

```text
/cloud/settings/
```

4. Copy:
   - the ingest URL
   - the sync token
5. On the local POS desktop app, open Business Settings.
6. Set:
   - `cloud_sync_enabled`
   - `cloud_sync_token`
   - `sync_dashboard_url`
7. Optional: enable `auto_sync_enabled` and set `auto_sync_interval_minutes`.
8. Use `Sync Now` from Business Settings to push local data to the cloud dashboard immediately.
9. In the desktop app, automatic sync can run server-side in the background while the local POS server is running.
10. On Windows installs, the background sync service can keep sync running even when the app is closed.

### PythonAnywhere deployment overview

Use PythonAnywhere only for the cloud dashboard and sync API. Keep the sales terminal local.

#### Recommended deploy steps

1. Create a PythonAnywhere account.
2. Upload or clone this project into your PythonAnywhere home folder.
3. Create a virtual environment and install requirements.
4. Create a web app for Django.
5. Point the PythonAnywhere WSGI file to `pos_system.wsgi`.
6. Run:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

7. Reload the web app.
8. Open the public URL and create the first business account from `/accounts/signup/`.

Static files (CSS/JS/images) are served through the app itself via WhiteNoise (`whitenoise.middleware.WhiteNoiseMiddleware`), so no separate PythonAnywhere "static files" mapping is required — it works correctly whether or not `collectstatic` has been run.

#### Local-to-cloud configuration example

If your PythonAnywhere app URL is:

```text
https://yourname.pythonanywhere.com
```

Then the local POS should use:

- `sync_dashboard_url = https://yourname.pythonanywhere.com/cloud/api/ingest/`
- `cloud_sync_token = <token copied from /cloud/settings/>`

### Current sync mode

- local POS pushes data manually with the `Sync Now` button
- local desktop app also runs automatic sync server-side when enabled
- sync is token-protected
- each cloud dashboard user sees only their own business data
- branch data is separated within each business

### Server-side automatic sync

The local desktop launcher now starts a background sync worker automatically. This means scheduled sync no longer depends on an open browser tab.

For Windows packaged installs, use the dedicated Windows service when you want scheduled sync to continue even after closing the desktop app. A lock file prevents duplicate sync runs if both the launcher worker and the service are active at the same time.

For non-desktop deployments, the same worker can be run manually with:

```bash
python manage.py run_autosync
```

To run a single due-check and exit:

```bash
python manage.py run_autosync --once
```

This is the command to use with platform schedulers such as PythonAnywhere tasks if you need a hosted worker process.

## Thermal printing

- Receipts are optimized for `80mm` thermal paper by default
- Business Settings includes a paper width option for `58mm` or `80mm`
- Print styles remove shadows and card chrome during printing

## Validation commands

Use these during development:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python -m compileall .
```

## Data model notes

Core implemented models include:

- `accounts.User`
- `accounts.ActivityLog`
- `products.Category`
- `products.Product`
- `suppliers.Supplier`
- `inventory.InventoryLog`
- `purchases.Purchase`
- `sales.Customer`
- `sales.Sale`
- `sales.SaleItem`
- `reports.BusinessSettings`

## Known next steps

These are logical next implementation targets, not yet completed:

- customer merge/search improvements
- minimum redeemable point rules
- printable loyalty statements
- customer credit sales

## Notes

- SQLite is the default development database for local offline use
- Tailwind styling is currently template-driven
- Django admin still exists for backend access, but the application now uses custom in-app screens for daily workflows

