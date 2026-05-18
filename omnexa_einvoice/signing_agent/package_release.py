#!/usr/bin/env python3
"""Zip dist/OmnexaESigningAgent for ERP workspace download."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist" / "OmnexaESigningAgent"
OUT_DIR = ROOT.parent / "public" / "downloads"
ZIP_NAME = "OmnexaESigningAgent-win64.zip"
VERSION_FILE = OUT_DIR / "signing_agent_version.json"


def main() -> int:
	if not DIST.is_dir():
		print(f"Missing build output: {DIST}")
		print("Run build_signing_agent_exe.bat on Windows first.")
		return 1

	OUT_DIR.mkdir(parents=True, exist_ok=True)
	zip_path = OUT_DIR / ZIP_NAME
	if zip_path.is_file():
		zip_path.unlink()

	with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
		for path in sorted(DIST.rglob("*")):
			if path.is_file():
				arc = path.relative_to(DIST.parent)
				zf.write(path, arc.as_posix())

	meta = {
		"version": date.today().isoformat(),
		"filename": ZIP_NAME,
		"size_bytes": zip_path.stat().st_size,
		"port": 5002,
		"health_url": "http://127.0.0.1:5002/health",
	}
	VERSION_FILE.write_text(json.dumps(meta, indent=2), encoding="utf-8")
	print(f"Wrote {zip_path} ({meta['size_bytes']:,} bytes)")
	print(f"Wrote {VERSION_FILE}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
