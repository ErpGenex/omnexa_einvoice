# -*- coding: utf-8 -*-
"""
Chilkat unlock — dynamic key (never hardcode your license in git).

Priority (first match wins):
  1. POST /sign body: chilkat_unlock_code (from ERP Branch via sign_session)
  2. Environment: CHILKAT_UNLOCK_CODE
  3. File next to agent: chilkat_config.json  →  { "unlock_code": "HALA4A...." }
  4. Legacy built-in keys only if CHILKAT_ALLOW_BUILTIN_KEYS=1

Version:
  Set CHILKAT_VERSION=10 in env or chilkat_config.json when using Chilkat v10 DLL.
  If Python loads 11.x from pip while you own v10, run: pip uninstall chilkat2
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

def _agent_runtime_dir() -> Path:
	"""PyInstaller: chilkat_config.json beside OmnexaESigningAgent.exe."""
	import sys

	if getattr(sys, "frozen", False):
		return Path(sys.executable).resolve().parent
	return Path(__file__).resolve().parent


_AGENT_DIR = Path(__file__).resolve().parent
_CONFIG_FILE = _agent_runtime_dir() / "chilkat_config.json"

CHILKAT_V10_UNLOCK_CODE = "2BBBV5.CBX082025_K5RCHVYV1RC4"
CHILKAT_TEMP_ETR_UNLOCK_CODE = "8VU94Z.CBX082025_A9LAOYTYoCDG"
CHILKAT_TRIAL_FALLBACK = "Anything for 30-day trial"

_LICENSE_ERROR_MARKERS = (
	"trial period has expired",
	"unlockbundle failed",
	"unlockstatus: 0",
	"purchase a license",
	"the previous call to unlockbundle failed",
)


class ChilkatLicenseError(Exception):
	"""Chilkat is installed but not licensed (not a PIN/token error)."""


def load_local_chilkat_config() -> dict[str, Any]:
	"""D:\\python\\chilkat_config.json — copy from chilkat_config.json.example"""
	if not _CONFIG_FILE.is_file():
		return {}
	try:
		data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
		return data if isinstance(data, dict) else {}
	except Exception:
		return {}


def chilkat_runtime_version(chilkat2_module) -> str:
	try:
		glob = chilkat2_module.Global()
		return (getattr(glob, "Version", None) or "").strip()
	except Exception:
		return ""


def desired_chilkat_major() -> str:
	"""10 or 11 from env / config / empty."""
	for src in (
		(os.getenv("CHILKAT_VERSION") or "").strip(),
		str(load_local_chilkat_config().get("chilkat_version") or "").strip(),
	):
		if src.startswith("10"):
			return "10"
		if src.startswith("11"):
			return "11"
	return ""


def ensure_chilkat_runtime_matches_request(chilkat2_module) -> None:
	"""Fail fast when user expects v10 but pip loaded v11."""
	runtime = chilkat_runtime_version(chilkat2_module)
	want = desired_chilkat_major()
	if want == "10" and runtime.startswith("11."):
		import sys

		py = f"{sys.version_info.major}.{sys.version_info.minor}"
		py_hint = ""
		if sys.version_info.minor >= 14:
			py_hint = (
				f"\nPython {py}: لا يوجد chilkat2 v10 على PyPI — استخدم Python 3.13 "
				"(مثلاً %LocalAppData%\\Programs\\Python\\Python313\\python.exe) "
				"وشغّل run_agent_py313.bat."
			)
		raise ChilkatLicenseError(
			f"Python يحمّل Chilkat {runtime} بينما إعدادك يطلب v10.{py_hint}\n"
			"على Python 3.10–3.13:\n"
			"  python -m pip uninstall -y chilkat2\n"
			"  python -m pip install chilkat2==10.1.3\n"
			"أو: fix_chilkat_v10.bat / run_agent_py313.bat\n"
			f"مفتاح v10: Branch → Chilkat Unlock Code أو {_CONFIG_FILE.name}. ليس خطأ PIN."
		)


def resolve_unlock_code_from_request(request_data: dict | None) -> tuple[str, str]:
	"""
	Returns (unlock_code, source_label).
	source: erp_session | request | env | config_file | builtin | empty
	"""
	data = request_data or {}
	direct = (data.get("chilkat_unlock_code") or data.get("CHILKAT_UNLOCK_CODE") or "").strip()
	if direct:
		return direct, "request"

	cfg = load_local_chilkat_config()
	env_code = (os.getenv("CHILKAT_UNLOCK_CODE") or "").strip()
	cfg_code = (cfg.get("unlock_code") or cfg.get("CHILKAT_UNLOCK_CODE") or "").strip()

	if env_code:
		return env_code, "env"
	if cfg_code:
		return cfg_code, "config_file"
	return "", ""


def ordered_unlock_codes(chilkat2_module, primary_code: str = "") -> list[str]:
	codes: list[str] = []
	if (primary_code or "").strip():
		codes.append(primary_code.strip())

	if os.getenv("CHILKAT_ALLOW_BUILTIN_KEYS", "").strip() in ("1", "true", "yes"):
		if desired_chilkat_major() == "10" or chilkat_runtime_version(chilkat2_module).startswith("10."):
			builtin = (CHILKAT_V10_UNLOCK_CODE, CHILKAT_TEMP_ETR_UNLOCK_CODE, CHILKAT_TRIAL_FALLBACK)
		else:
			builtin = (CHILKAT_TEMP_ETR_UNLOCK_CODE, CHILKAT_V10_UNLOCK_CODE, CHILKAT_TRIAL_FALLBACK)
		for code in builtin:
			if code not in codes:
				codes.append(code)
	return codes


def is_chilkat_license_error(message: str | None) -> bool:
	text = (message or "").lower()
	return any(marker in text for marker in _LICENSE_ERROR_MARKERS)


def unlock_chilkat_global(
	chilkat2_module,
	*,
	request_data: dict | None = None,
	primary_unlock_code: str | None = None,
) -> tuple[bool, str]:
	ensure_chilkat_runtime_matches_request(chilkat2_module)
	glob = chilkat2_module.Global()
	runtime_ver = chilkat_runtime_version(chilkat2_module) or "unknown"

	code, source = resolve_unlock_code_from_request(request_data)
	if (primary_unlock_code or "").strip():
		code = primary_unlock_code.strip()
		source = source or "erp_session"

	if not code:
		raise ChilkatLicenseError(
			f"لا يوجد مفتاح Chilkat. الإصدار المحمّل: {runtime_ver}. "
			f"ضع المفتاح في ERP: Branch → Egypt ETA → Chilkat Unlock Code (يُرسل مع sign_session)، "
		 f"أو ملف {_CONFIG_FILE}، أو set CHILKAT_UNLOCK_CODE=HALA4A.CBX082025_.... "
			"ليس خطأ PIN."
		)

	for attempt in ordered_unlock_codes(chilkat2_module, code):
		if attempt and glob.UnlockBundle(attempt):
			masked = _mask_unlock_code(attempt)
			return True, f"v{runtime_ver} unlocked ({masked}, source={source})"

	last = (glob.LastErrorText or "").strip()
	if is_chilkat_license_error(last):
		raise ChilkatLicenseError(
			f"Chilkat {runtime_ver}: فشل فك القفل للمفتاح من {source} ({_mask_unlock_code(code)}). "
			"تأكد أن المفتاح يطابق نفس إصدار Chilkat المثبت (v10 ≠ v11). "
			f"ملف الإعدادات: {_CONFIG_FILE}. ليس خطأ PIN."
		)
	return False, f"v{runtime_ver} unlock failed ({source}): {last or 'UnlockBundle failed'}"


def user_facing_sign_error(exc: BaseException) -> str:
	text = str(exc) or ""
	if isinstance(exc, ChilkatLicenseError) or is_chilkat_license_error(text):
		return str(exc) if isinstance(exc, ChilkatLicenseError) else (
			"ترخيص Chilkat: راجع Branch → Chilkat Unlock Code أو chilkat_config.json "
			"أو CHILKAT_UNLOCK_CODE. تحقق من /health → chilkat_runtime_version."
		)
	if "smartcard" in text.lower() or "pin" in text.lower():
		return f"{text} — تحقق من PIN والتوكن."
	return text


def unlock_status_for_health(chilkat2_module, request_data: dict | None = None) -> dict[str, Any]:
	"""Diagnostics for GET /health (no secrets)."""
	code, source = resolve_unlock_code_from_request(request_data)
	runtime = chilkat_runtime_version(chilkat2_module)
	out = {
		"chilkat_runtime_version": runtime or None,
		"chilkat_desired_major": desired_chilkat_major() or None,
		"unlock_source": source or None,
		"has_unlock_code": bool(code),
		"config_file": str(_CONFIG_FILE),
		"config_file_exists": _CONFIG_FILE.is_file(),
	}
	try:
		ok, note = unlock_chilkat_global(chilkat2_module, request_data=request_data, primary_unlock_code=code)
		out["chilkat_unlock_ok"] = ok
		out["chilkat_unlock_note"] = note
	except ChilkatLicenseError as exc:
		out["chilkat_unlock_ok"] = False
		out["chilkat_unlock_note"] = str(exc)
	except Exception as exc:
		out["chilkat_unlock_ok"] = False
		out["chilkat_unlock_note"] = str(exc)
	return out


def _mask_unlock_code(code: str) -> str:
	code = (code or "").strip()
	if len(code) <= 12:
		return "***"
	return code[:6] + "…" + code[-4:]
