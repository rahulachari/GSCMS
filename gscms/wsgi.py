import os
import sys
import shutil
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

for p in [str(BACKEND_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gscms.settings")

# Handle SQLite on Vercel: copy database to /tmp so it can be written to
tmp_db = Path("/tmp/db.sqlite3")
src_db = BACKEND_DIR / "db.sqlite3"
if src_db.exists() and not tmp_db.exists():
    try:
        shutil.copy2(src_db, tmp_db)
    except Exception:
        pass

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
app = application
