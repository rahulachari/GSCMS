# GSCMS — Workshop Operations Manual

## 1. Owner & Receptionist Daily Operations
### Morning Routine (5–10 Seconds)
1. Open Dashboard (`http://127.0.0.1:8000/`).
2. Review the **Owner's Daily Summary**:
   - Total active jobs on benches.
   - Attention Required (delayed jobs, jobs due today).
   - Ready for Delivery items waiting in vitrine.
   - Outstanding customer dues.

### Booking a New Order & Multi-Item Splitting
1. Click **+ New Order** (`/orders/new/`).
2. Choose **Existing Customer** or enter **New Customer** details.
3. Select order type (Custom Bespoke, New Jewellery, Repair, Resizing) and target delivery date.
4. Upload customer's reference sketch or WhatsApp photo.
5. In **Jewellery Items (Jobs)**, click **+ Add Another Item** if the customer has multiple pieces in this order (e.g. 1 Ring + 2 Earrings + 1 Necklace).
6. Each item automatically generates a unique identifier: e.g. `J-2026-000101-A`, `J-2026-000101-B`.
7. Enter advance payment received (UPI, Cash, Bank Transfer) to generate an official voucher.

---

## 2. Gold Accountability & The Immutable Ledger
In goldsmith ateliers, gold can never be unaccounted for.
1. When issuing metal: Navigate to **Gold Ledger** -> **Issue Gold to Worker**. Record exact grams (3 decimal places, e.g. `16.250g`), purity (`22K`), and Karigar name.
2. When the Karigar returns metal: Click **Record Gold Return**. Select return category:
   - **Finished Item Gold Returned**
   - **Scrap Gold Returned** (sprues, cut wire)
   - **Dust Recovered** (polishing suction / bench sweepings)
   - **Melting Loss** (fire oxidation)
3. The system computes the net difference. Differences are never deleted; adjustments require audit entries.

---

## 3. Karigar Bench Operations (Mobile & Tablet)
Artisans can operate from any mobile phone or bench tablet:
1. Open **Karigar Station** (`/station/`).
2. Select your name or scan the Job Card QR code.
3. See your assigned jewellery pieces with high-res reference blueprints and crafting instructions.
4. Touch **START WORK** to initiate active time tracking.
5. If paused for gold/stone waiting, touch **PAUSE**.
6. When complete, touch **COMPLETE STAGE** to advance the piece to the next station (e.g. Stone Setting or Polishing).

---

## 4. Quality Control (QC) & Rework Gate
Before any piece reaches the customer delivery vitrine, it must pass the 10-point QC desk:
1. Navigate to **QC Desk** (`/qc/`).
2. Click **Run QC Checklist**:
   - Design matches reference blueprint
   - Correct weight within tolerance
   - Dimensions & ring size confirmed
   - Stone setting rigidity (no loose prongs)
   - Surface flawless (no microporosity or scratches)
   - Polishing & lapping uniformity
   - Soldering joins solid
   - Locks, hinges & screw backs firm
   - BIS Hallmarking 916/750 sharp
   - High-res final photograph recorded
3. If defects exist, select **REWORK REQUIRED**, enter the detailed reason, and specify the stage (Making, Setting, or Polishing) to route it back.

---

## 5. Handover & Delivery Confirmation
1. Once QC passes, the piece enters **Ready for Delivery**.
2. Click **Record Customer Delivery** (`/jobs/<job_id>/delivery/`).
3. Verify the 4 gates: QC Passed, Final Weight Checked, Payment Cleared, Photo recorded.
4. Record the receiver's name and notes to finalize delivery and permanently archive the digital dossier.
