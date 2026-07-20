# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA Phase 1 signing scaffold (hash + placeholder signature)."""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from omnexa_einvoice.zatca.phase1.invoice_builder import hash_xml_sha256


def sign_invoice_xml(
	xml_text: str,
	*,
	private_key_pem: str | None = None,
	certificate_pem: str | None = None,
) -> dict[str, Any]:
	"""
	Phase 1 signing hook.

	When ``private_key_pem`` is missing, returns a deterministic scaffold signature for dev/tests.
	Production must supply CSID/private key from ``ZATCA Company Settings`` (Phase 2 onboarding).
	"""
	digest = hash_xml_sha256(xml_text)
	raw = bytes.fromhex(digest) if len(digest) == 64 else hashlib.sha256(xml_text.encode()).digest()
	hash_hex = raw.hex() if isinstance(raw, bytes) else digest
	hash_b64 = base64.b64encode(bytes.fromhex(hash_hex)).decode("ascii")
	if not private_key_pem:
		placeholder = base64.b64encode(f"ZATCA-SCAFFOLD:{hash_hex}".encode()).decode("ascii")
		return {
			"ok": True,
			"signer": "scaffold",
			"hash_hex": hash_hex,
			"hash_b64": hash_b64,
			"invoice_hash": hash_hex,
			"signature": placeholder,
			"signature_b64": placeholder,
			"signed_xml": xml_text
	}

	# Real ECDSA / XAdES integration — Phase 1.1 task
	_ = certificate_pem
	raise NotImplementedError("Hardware/software signing with CSID private key not implemented yet.")
