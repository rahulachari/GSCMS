# GSCMS — Jewellery & Goldsmith Workshop Architecture

## Overview
GSCMS (Goldsmith Workshop Management System) is an enterprise-grade ERP designed specifically for traditional, bespoke, and manufacturing jewellery workshops. Built with a clean modular monolith architecture in Python & Django, it enforces complete accountability across customers, split jobs, artisan stages, precious metal (gold), stones, quality control, payments, and delivery.

## Visual Design Reference
- **Theme**: Apple (España) — *Gallery vitrine in morning fog*
- **Canvas**: Fog Canvas `#f5f5f7`
- **Surfaces**: Pure White `#ffffff` with 28px border-radius and crisp `#e5e5ea` borders (no artificial drop shadows)
- **Primary Action (Conversion)**: Electric Blue `#0071e3` (pill button `border-radius: 980px`, white text)
- **Typography**: SF Pro Display / Inter Tight for display headlines with tight tracking; SF Pro Text / Inter for readable body.

## Folder Structure
```
GSCMS/
├── backend/                         # Backend Application & Engine
│   ├── gscms/                       # Django project root configuration
│   │   ├── settings.py              # Application settings, media & templates
│   │   ├── urls.py                  # Root URL dispatcher
│   │   ├── wsgi.py & asgi.py
│   ├── workshop/                    # Core ERP app
│   │   ├── models.py                # Database models
│   │   ├── views.py                 # Views & endpoints
│   │   ├── urls.py                  # App URL routing
│   │   ├── services.py              # OpenPyXL exports, Backup, Audit, ZIP packaging
│   │   ├── context_processors.py    # Workshop globals & notification counters
│   │   ├── generate_assets.py       # High-definition jewellery renders
│   │   ├── management/commands/     # Seed data & backup commands
│   │   └── tests.py                 # Automated test suite (8/8 passing)
│   ├── media/                       # Uploaded reference & final photos partitioned by job
│   ├── manage.py                    # Django management utility
│   └── db.sqlite3                   # Primary database (swappable to PostgreSQL)
├── frontend/                        # Frontend Assets & Templates
│   ├── static/
│   │   ├── css/
│   │   │   ├── apple-theme.css      # Apple España design system tokens & surfaces
│   │   │   └── workshop.css         # Kanban, timeline, delay cards, touch station
│   │   ├── js/
│   │   │   └── workshop.js          # Live search (Cmd+K), draft safety, lightbox, AJAX actions
│   │   └── img/sample_jewellery/    # Visual jewellery assets
│   └── templates/
│       ├── base.html                # Translucent dark nav & vitrine container
│       └── workshop/                # Modular templates
├── backups/                         # Full automated system snapshots (.zip)
├── docs/                            # Documentation
│   ├── ARCHITECTURE.md
│   ├── WORKSHOP_MANUAL.md
│   └── BACKUP_AND_RESTORE.md
├── requirements.txt
└── README.md
```

## Core Domain Flow
```
CUSTOMER ──► ORDER ──► JOB SPLITTING (J-2026-XXXXX-A/B)
                          │
         ┌────────────────┴───────────────┐
         ▼                                ▼
   GOLD ISSUED                      STONE ISSUED
(Granules/Wire/Plate)              (Diamonds/Rubies/Emeralds)
         │                                │
         └────────────────┬───────────────┘
                          ▼
            STAGE WORKFLOW & KARIGARS
   (Melting ─► Making ─► Setting ─► Polish)
                          │
                          ▼
        10-POINT QUALITY CONTROL (QC) DESK
        [ PASS ]                 [ REWORK REQUIRED ]
           │                                │
           ▼                                └─► Routed back to Karigar
     FINAL WEIGHT AUDIT
(Gross vs Net Gold vs Stone vs Wastage)
           │
           ▼
     CUSTOMER DELIVERY & PAYMENT SETTLEMENT
```
