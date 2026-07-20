# omnexa_einvoice.zatca

Saudi ZATCA e-invoicing (Phase 1 + Phase 2) — **fully isolated** from Egypt ETA / e-Receipt.

- Entry: `zatca.dispatch.process_zatca_hub_request`
- Hub adapter: `SaudiZatcaAdapter` in `einvoice_adapters.py`
- Docs: `Docs/2026-05-19_ZATCA/CHECKLIST.md`

Do not add DocType hooks on `Sales Invoice` from this package; use explicit submission / hub calls only.
