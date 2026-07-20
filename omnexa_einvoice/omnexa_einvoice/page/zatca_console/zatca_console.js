// Copyright (c) 2026, Omnexa and contributors
// License: MIT

frappe.pages["zatca-console"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("ZATCA Console"),
		single_column: true,
	});

	const $main = $(wrapper).find(".layout-main-section");
	$main.html(`
		<div class="zatca-console padding">
			<p class="text-muted">${__("Saudi ZATCA e-invoicing — Phase 1 local generation and Phase 2 API clearance/reporting.")}</p>
			<div class="form-group">
				<label>${__("Reference")}</label>
				<input type="text" class="form-control" id="zatca-ref" placeholder="SI-0001" />
			</div>
			<div class="form-group">
				<label>${__("Company")}</label>
				<input type="text" class="form-control" id="zatca-company" />
			</div>
			<div class="form-group">
				<label>${__("Document type")}</label>
				<select class="form-control" id="zatca-doctype">
					<option value="tax_invoice">tax_invoice</option>
					<option value="simplified_invoice">simplified_invoice</option>
				</select>
			</div>
			<button class="btn btn-primary" id="zatca-run-phase1">${__("Run Phase 1")}</button>
			<button class="btn btn-default" id="zatca-run-phase2">${__("Run Phase 2 (queue)")}</button>
			<pre class="small text-muted margin-top" id="zatca-output"></pre>
		</div>
	`);

	function runZatca(phase) {
		frappe.call({
			method: "omnexa_einvoice.zatca.submission.process_zatca_invoice",
			args: {
				reference_name: $("#zatca-ref").val(),
				document_type: $("#zatca-doctype").val(),
				phase,
				company: $("#zatca-company").val() || frappe.defaults.get_default("company"),
			},
			callback(r) {
				const data = r.message || r;
				if (phase === "phase1" && data.qr_image_base64) {
					$("#zatca-output").html(
						`<div class="text-center margin-bottom"><img src="data:image/png;base64,${data.qr_image_base64}" style="max-width:240px;" /><p class="small text-muted">${__(
							"ZATCA QR"
						)}</p></div><pre class="small">${frappe.utils.escape_html(
							JSON.stringify(data, null, 2)
						)}</pre>`
					);
				} else {
					$("#zatca-output").text(JSON.stringify(data, null, 2));
				}
			},
		});
	}

	$("#zatca-run-phase1").on("click", () => runZatca("phase1"));
	$("#zatca-run-phase2").on("click", () => runZatca("phase2"));
};
