# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""India GST signed QR code → PNG for print."""

from __future__ import annotations

import base64
import io


def signed_qr_to_png_base64(signed_qr: str) -> str:
	"""Render NIC SignedQRCode string as QR PNG (base64)."""
	text = (signed_qr or "").strip()
	if not text:
		return ""
	try:
		import qrcode

		img = qrcode.make(text)
		buf = io.BytesIO()
		img.save(buf, format="PNG")
		return base64.b64encode(buf.getvalue()).decode("ascii")
	except Exception:
		return ""
