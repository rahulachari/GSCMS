# GSCMS — Permanent Archival & Backup / Restore Guide

## 1. Overview
GSCMS guarantees business data permanence through automated and manual snapshots. Every backup bundle contains:
1. Complete SQLite relational database (`db.sqlite3`).
2. Complete media storage directory (`backend/media/` containing all reference design sketches, progress photos, final hallmark photographs, and QR codes).
3. Configuration and metadata.

---

## 2. Generating a Backup
### Method A: One-Click Web UI
1. Navigate to **Backup Center** (`/backup/`).
2. Click **BACKUP NOW**.
3. A timestamped ZIP archive (e.g. `GSCMS_Backup_20260924_121500.zip`) is generated in the root `backups/` directory and logged with file size and timestamp.

### Method B: Automated Nightly Cron / Windows Task Scheduler
In PowerShell:
```powershell
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gscms.settings'); django.setup(); from workshop.services import perform_system_backup; perform_system_backup('Scheduled Nightly Backup')"
```

---

## 3. Restoring from a Backup
If you move to a new machine or need to restore from hardware failure:
1. Locate your target backup file in `backups/` (or from offsite USB storage).
2. Unzip `GSCMS_Backup_YYYYMMDD_HHMMSS.zip`.
3. Copy `db.sqlite3` into `backend/`.
4. Copy the `media/` folder into `backend/media/`.
5. Start the workshop server:
```powershell
cd backend
python manage.py runserver
```
All customer orders, job stages, gold ledgers, and photographs will be fully restored.
