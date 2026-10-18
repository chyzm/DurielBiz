# DurielBiz POS

Built by `DurielTech`, an IT company delivering operational software for healthcare, retail, mobility, and business automation.

Point of sale system built with Django. The packaged desktop app uses `127.0.0.1:8080`; the local cloud-mode development server uses Django's default `127.0.0.1:8000`.

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
- Business settings for receipt branding, branch defaults, and loyalty rules

### Branches

- Branch CRUD for multi-branch deployments
- Default branch assignment on sales, purchases, and inventory logs

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

Open `http://127.0.0.1:8000/`.

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
- `desktop_launcher.py` copies the packaged Django project into the packaged runtime directory
- The launcher runs migrations automatically, starts Django locally, and opens the POS only after the server is reachable

This is the current desktop strategy:

- backend runs locally
- UI opens in the system browser
- suitable for packaging as a lightweight Windows desktop install

## Licensing (trial & activation)

The desktop build includes a 14-day trial and a single-master-key activation system, implemented in the `licensing` app. It only ever applies to the packaged desktop app — the hosted deployment and local development (`manage.py runserver`) are never gated.

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
python manage.py runserver 127.0.0.1:8000
```

7. Open `http://127.0.0.1:8000/` in the browser

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

## Remote viewing

Use this if the phone or another PC is on the same Wi‑Fi/LAN as the POS computer.

### Step by step with the desktop EXE

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
python manage.py runserver 0.0.0.0:8080
```

3. Open from another device on the same network:

```text
http://192.168.1.25:8080/
```

This is the simplest remote view option for a single location.

### Security note for remote viewing

- Do not expose the local Django server directly to the public internet in `DEBUG=True`
- For internet access, use a proper hosted server, HTTPS, authentication, and firewall rules

## Cloud production requirements

The Docker Compose deployment is treated as production. Set these values in `.env` before
starting it:

- `DEBUG=False`
- `SECRET_KEY` to a unique, private value
- `DATABASE_URL` to the production MySQL database
- `DURIELBIZ_ALLOWED_HOSTS` to DNS hostnames only (no `https://` prefix)
- `DURIELBIZ_CSRF_TRUSTED_ORIGINS` to the HTTPS site origins

Cloud production fails startup when its secret, HTTPS origin, or MySQL database is
missing. Desktop installs continue using their local SQLite database. Docker Compose
runs a separate scheduler container at 08:00 in the configured Django timezone and
also catches up once when that container starts. The underlying
`python manage.py send_subscription_reminders` command remains available for hosts
that use their own daily scheduler. Each reminder is recorded once per subscription term.

## Cloud and desktop synchronization

Synchronization uses an authenticated device credential and a change log for each business.
The desktop launcher retries in the background every 60 seconds when sync is configured;
POS checkout stays available while the network is down. New desktop records use device-local
device-specific negative IDs so their keys do not collide with cloud-created records.

1. Apply migrations on the hosted deployment.
2. Create a device credential on the cloud host:

```powershell
python manage.py create_sync_device acme-stores "Shop PC"
```

3. Copy the printed values into the desktop `.env`. Set `DURIELBIZ_SYNC_URL` to the full
   HTTPS endpoint, such as `https://pos.example.com/api/sync/`.
4. Start the desktop app. On its first successful connection, the cloud business snapshot
   replaces that business's local records. Back up any desktop data you need before pairing.
   Later syncs send desktop changes and apply cloud changes in both directions.
5. Revoke a lost device by setting it inactive under Django Admin → Sync devices.

The first sync treats cloud data as authoritative. If the same record changes independently
while a desktop is offline, the latest change delivered to the receiving database wins. Sync
credentials are per device; keep the printed token private.

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

