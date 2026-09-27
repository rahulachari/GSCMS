import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"

for p in [str(BACKEND_DIR), str(BASE_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gscms.settings')

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
app = application
handler = application
