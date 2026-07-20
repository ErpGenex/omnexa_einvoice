// Copyright (c) 2026, Omnexa and contributors
// License: MIT

frappe.ui.form.on("ZATCA Submission Log", {
	refresh(frm) {
		if (!frm.doc.qr_base64) {
			return;
		}
		frappe.call({
			method: "omnexa_einvoice.zatca.phase1.qr_embed.qr_tlv_to_png_base64",
			args: { qr_tlv_base64: frm.doc.qr_base64 },
			callback(r) {
				const imgB64 = r.message;
				if (!imgB64 || !frm.fields_dict.qr_base64) {
					return;
				}
				const $wrap = frm.fields_dict.qr_base64.$wrapper;
				$wrap.find(".zatca-qr-preview").remove();
				$wrap.prepend(
					`<div class="zatca-qr-preview text-center margin-bottom">
						<p><strong>${__("ZATCA QR Code")}</strong></p>
						<img src="data:image/png;base64,${imgB64}" style="max-width:220px;height:auto;" alt="QR" />
					</div>`
				);
			},
		});
	},
});
