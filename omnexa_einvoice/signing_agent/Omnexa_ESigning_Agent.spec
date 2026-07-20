# -*- mode: python ; coding: utf-8 -*-
# Build on Windows with Python 3.13 + chilkat2==10.1.3:
#   build_signing_agent_exe.bat

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

a = Analysis(
	[str(root / "epass2003_agent.py")],
	pathex=[str(root)],
	binaries=[],
	datas=[
		(str(root / "omnexa_agent_pin.py"), "."),
		(str(root / "chilkat_license.py"), "."),
		(str(root / "itida_cms.py"), "."),
		(str(root / "chilkat_config.json.example"), "."),
	],
	hiddenimports=[
		"flask",
		"flask_cors",
		"werkzeug",
		"jinja2",
		"click",
		"itsdangerous",
		"markupsafe",
		"requests",
		"urllib3",
		"certifi",
		"charset_normalizer",
		"idna",
		"PyKCS11",
		"asn1crypto",
		"asn1crypto.cms",
		"asn1crypto.x509",
		"cryptography",
		"chilkat2",
		"engineio.async_drivers.threading",
	],
	hookspath=[],
	hooksconfig={},
	runtime_hooks=[],
	excludes=["tkinter", "matplotlib", "numpy", "pandas"],
	cipher=block_cipher,
	noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
	pyz,
	a.scripts,
	[],
	exclude_binaries=True,
	name="OmnexaESigningAgent",
	debug=False,
	bootloader_ignore_signals=False,
	strip=False,
	upx=False,
	console=True,
	disable_windowed_traceback=False,
	argv_emulation=False,
	target_arch=None,
	codesign_identity=None,
	entitlements_file=None,
)

coll = COLLECT(
	exe,
	a.binaries,
	a.zipfiles,
	a.datas,
	strip=False,
	upx=False,
	upx_exclude=[],
	name="OmnexaESigningAgent",
)
