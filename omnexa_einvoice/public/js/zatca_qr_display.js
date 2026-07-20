// Copyright (c) 2026, Omnexa and contributors
// License: MIT

/** Render ZATCA Phase 1 result with scannable QR image. */

frappe.provide("omnexa.zatca");

omnexa.zatca.format_phase1_message = function (result) {
	const data = result || {};
	let html = "";
	if (data.qr_image_base64) {
		html += `<div class="text-center margin-bottom">
			<p><strong>${__("ZATCA QR Code")}</strong></p>
			<img src="data:image/png;base64,${data.qr_image_base64}" alt="ZATCA QR" style="max-width:220px;height:auto;" />
		</div>`;
	} else if (data.qr_base64) {
		html += `<p class="text-muted small">${__(
			"QR TLV generated but image could not be rendered. Check server package: qrcode."
		)}</p>`;
	}
	if (data.uuid) {
		html += `<p class="small"><b>UUID:</b> ${frappe.utils.escape_html(data.uuid)}</p>`;
	}
	if (data.invoice_hash) {
		html += `<p class="small"><b>${__("Hash")}:</b> ${frappe.utils.escape_html(data.invoice_hash)}</p>`;
	}
	if (data.log_name) {
		html += `<p class="small"><a href="/app/zatca-submission-log/${encodeURIComponent(
			data.log_name
		)}">${__("Open ZATCA Submission Log")}</a></p>`;
	}
	html += `<details class="margin-top"><summary class="small text-muted">${__("Technical JSON")}</summary>
		<pre class="small">${frappe.utils.escape_html(JSON.stringify(data, null, 2))}</pre></details>`;
	return html;
};

omnexa.zatca.show_phase1_result = function (result, title) {
	frappe.msgprint({
		title: title || __("ZATCA Phase 1"),
		message: omnexa.zatca.format_phase1_message(result),
		indicator: "green",
	});
};
