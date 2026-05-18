# Omnexa USB Signing Agent — Windows release

The downloadable ZIP is built on a **Windows** PC with Python 3.13:

```
apps/omnexa_einvoice/omnexa_einvoice/signing_agent/build_signing_agent_exe.bat
```

Output (after build):

- `OmnexaESigningAgent-win64.zip` — copy here for E-Invoice workspace download
- `signing_agent_version.json` — version metadata

Then on the server:

```
bench build --app omnexa_einvoice
bench --site YOUR_SITE clear-cache
```

Users open **E-Invoice** workspace → **USB Signing Agent (Windows)**.
