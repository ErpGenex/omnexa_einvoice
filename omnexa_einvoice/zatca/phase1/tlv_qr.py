# Copyright (c) 2026, Omnexa and contributors
# License: MIT. See license.txt

"""ZATCA Phase 1 QR — TLV tags 1–9."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime

from omnexa_einvoice.zatca.constants import (
	TLV_TAG_INVOICE_TOTAL,
	TLV_TAG_SELLER_NAME,
	TLV_TAG_TIMESTAMP,
	TLV_TAG_VAT_REGISTRATION,
	TLV_TAG_VAT_TOTAL,
)

TLV_TAG_HASH = 6
TLV_TAG_SIGNATURE = 7
TLV_TAG_PUBLIC_KEY = 8
TLV_TAG_CERT_SIGNATURE = 9


def _tlv_field(tag: int, value: str | bytes) -> bytes:
	if isinstance(value, str):
		raw = value.encode("utf-8")
	else:
		raw = value
	if len(raw) > 255:
		raise ValueError(f"TLV tag {tag} value too long")
	return bytes([tag, len(raw)]) + raw


def build_tlv_bytes_phase1(
	*,
	seller_name: str,
	vat_registration: str,
	timestamp: str | datetime,
	invoice_total_with_vat: str,
	vat_amount: str,
) -> bytes:
	if isinstance(timestamp, datetime):
		ts = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
	else:
		ts = str(timestamp).strip()
	return b"".join(
		[
			_tlv_field(TLV_TAG_SELLER_NAME, seller_name.strip()),
			_tlv_field(TLV_TAG_VAT_REGISTRATION, vat_registration.strip()),
			_tlv_field(TLV_TAG_TIMESTAMP, ts),
			_tlv_field(TLV_TAG_INVOICE_TOTAL, invoice_total_with_vat.strip()),
			_tlv_field(TLV_TAG_VAT_TOTAL, vat_amount.strip()),
		]
	)


def build_tlv_bytes_signed(
	*,
	seller_name: str,
	vat_registration: str,
	timestamp: str | datetime,
	invoice_total_with_vat: str,
	vat_amount: str,
	invoice_hash_hex: str,
	signature_b64: str,
	public_key_b64: str | None = None,
	cert_signature_b64: str | None = None,
) -> bytes:
	parts = [
		build_tlv_bytes_phase1(
			seller_name=seller_name,
			vat_registration=vat_registration,
			timestamp=timestamp,
			invoice_total_with_vat=invoice_total_with_vat,
			vat_amount=vat_amount,
		),
		_tlv_field(TLV_TAG_HASH, invoice_hash_hex),
		_tlv_field(TLV_TAG_SIGNATURE, signature_b64),
	]
	if public_key_b64:
		try:
			raw = base64.b64decode(public_key_b64)
			hex_chunks = binascii.hexlify(raw).decode("ascii")
			parts.append(_tlv_field(TLV_TAG_PUBLIC_KEY, bytes.fromhex(hex_chunks)))
		except Exception:
			parts.append(_tlv_field(TLV_TAG_PUBLIC_KEY, public_key_b64.encode()))
	if cert_signature_b64:
		parts.append(_tlv_field(TLV_TAG_CERT_SIGNATURE, cert_signature_b64))
	return b"".join(parts)


def build_tlv_qr_base64(**kwargs) -> str:
	if "invoice_hash_hex" in kwargs:
		return base64.b64encode(build_tlv_bytes_signed(**kwargs)).decode("ascii")
	return base64.b64encode(
		build_tlv_bytes_phase1(
			seller_name=kwargs["seller_name"],
			vat_registration=kwargs["vat_registration"],
			timestamp=kwargs["timestamp"],
			invoice_total_with_vat=kwargs["invoice_total_with_vat"],
			vat_amount=kwargs["vat_amount"],
		)
	).decode("ascii")


# Backward-compatible aliases
build_tlv_bytes = build_tlv_bytes_phase1
