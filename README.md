### Omnexa Einvoice (`omnexa_einvoice`)

Standalone Frappe app for **electronic invoice (e-Invoice)** and **electronic receipt (e-Receipt)** integrations (e.g. **Egypt ETA**, **Saudi ZATCA**), separate from `omnexa_core`.

`omnexa_core` keeps the shared **IntegrationHub**, **E-Document Submission** DocType, and generic `einvoice_stub` adapter. This app registers country adapters via the hook **`omnexa_register_integration_hub`** and provides **ETA helpers** (`eta_integration.py`: token cache, poll normalization, submission updates).

### Requirements

- `omnexa_core` must be installed (`required_apps` is set in `hooks.py`).

### Source (GitHub)

**https://github.com/microcol/omnexa_einvoice**

### Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/microcol/omnexa_einvoice.git
bench --site yoursite install-app omnexa_einvoice
bench migrate
```

### Usage (developers)

- **Hub adapters:** `einvoice_eta`, `einvoice_zatca` — available on `get_default_hub()` when this app is installed.
- **ETA utilities:** `from omnexa_einvoice.eta_integration import ensure_eta_access_token, apply_eta_poll_to_submission, ...`

### License

MIT
