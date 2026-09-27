import os
import sys
import shutil
import traceback
from pathlib import Path

# Setup base paths
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
BACKEND_DIR = ROOT_DIR / "backend"

for p in [str(BACKEND_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gscms.settings")

_application = None
_init_error = None

def init_app():
    global _application
    # Setup directories in /tmp for writable filesystem on Vercel
    tmp_db = Path("/tmp/db.sqlite3")
    src_db = BACKEND_DIR / "db.sqlite3"

    if src_db.exists() and not tmp_db.exists():
        try:
            shutil.copy2(src_db, tmp_db)
        except Exception as e:
            print(f"Notice: copying source db to /tmp: {e}")

    os.makedirs("/tmp/media", exist_ok=True)
    os.makedirs("/tmp/backups", exist_ok=True)
    os.makedirs("/tmp/staticfiles", exist_ok=True)

    from django.core.wsgi import get_wsgi_application
    _application = get_wsgi_application()

    # Ensure database schema exists in /tmp
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
            if not tables or 'auth_user' not in tables:
                from django.core.management import call_command
                call_command('migrate', interactive=False)
                call_command('seed_data')
    except Exception as e:
        print(f"Notice: database verification: {e}")

    return _application

try:
    _application = init_app()
except Exception:
    _init_error = traceback.format_exc()

def app(environ, start_response):
    global _application, _init_error
    if _init_error:
        start_response('500 Internal Server Error', [('Content-Type', 'text/html; charset=utf-8')])
        html = f"""<!DOCTYPE html>
<html>
<head><title>GSCMS Initialization Error</title></head>
<body style="font-family: monospace; padding: 30px; background: #111; color: #ff6b6b;">
    <h2>GSCMS Startup Error</h2>
    <pre>{_init_error}</pre>
</body>
</html>"""
        return [html.encode('utf-8')]

    try:
        return _application(environ, start_response)
    except Exception:
        tb = traceback.format_exc()
        start_response('500 Internal Server Error', [('Content-Type', 'text/html; charset=utf-8')])
        html = f"""<!DOCTYPE html>
<html>
<head><title>GSCMS Request Error</title></head>
<body style="font-family: monospace; padding: 30px; background: #111; color: #ff6b6b;">
    <h2>GSCMS Request Execution Error</h2>
    <pre>{tb}</pre>
</body>
</html>"""
        return [html.encode('utf-8')]

application = app
handler = app
