"""
WSGI config for gscms project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
for p in [str(BASE_DIR), str(ROOT_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gscms.settings')

application = get_wsgi_application()
app = application
handler = application
