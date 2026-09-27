import os
import sys
import shutil
from pathlib import Path

# Setup paths
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
BACKEND_DIR = ROOT_DIR / "backend"

# Ensure backend and root are in sys.path
for p in [str(BACKEND_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Handle Vercel serverless read-only filesystem by copying database to /tmp
tmp_db = Path("/tmp/db.sqlite3")
src_db = BACKEND_DIR / "db.sqlite3"
if src_db.exists() and not tmp_db.exists():
    try:
        shutil.copy2(src_db, tmp_db)
    except Exception as e:
        print(f"Notice: could not copy db to /tmp: {e}")

# Handle media folder copy to /tmp for writable file uploads on serverless
tmp_media = Path("/tmp/media")
src_media = BACKEND_DIR / "media"
if src_media.exists() and not tmp_media.exists():
    try:
        shutil.copytree(src_media, tmp_media)
    except Exception as e:
        print(f"Notice: could not copy media to /tmp: {e}")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gscms.settings")

from django.core.wsgi import get_wsgi_application
app = get_wsgi_application()
