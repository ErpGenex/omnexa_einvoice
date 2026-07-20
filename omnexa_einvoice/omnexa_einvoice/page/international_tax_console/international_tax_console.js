// Copyright (c) 2026, Omnexa and contributors
// License: MIT

frappe.pages["international-tax-console"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("International Tax Console"),
		single_column: true,
	});

	const $main = $(wrapper).find(".layout-main-section");
	$main.html(`
		<div class="international-tax-console padding">
			<p class="text-muted">${__(
				"Phase 1: XML generation, scaffold signing, archive. Phase 2: authority API (or queue). Egypt and Saudi use their own consoles."
			)}</p>
			<div class="form-group">
				<label>${__("Country")}</label>
				<select class="form-control" id="itc-country"></select>
			</div>
			<div class="form-group">
				<label>${__("Sales Invoice")}</label>
				<input type="text" class="form-control" id="itc-ref" placeholder="SI-0001" />
			</div>
			<div class="form-group">
				<label>${__("Company")}</label>
				<input type="text" class="form-control" id="itc-company" />
			</div>
			<button class="btn btn-primary" id="itc-phase1">${__("Run Phase 1")}</button>
			<button class="btn btn-default" id="itc-phase2">${__("Run Phase 2 (sync in test)")}</button>
			<button class="btn btn-default btn-sm" id="itc-smoke-all">${__("Smoke test all countries")}</button>
			<button class="btn btn-default btn-sm" id="itc-smoke-sample">${__("Smoke sample (fast)")}</button>
			<pre class="small text-muted margin-top" id="itc-output"></pre>
		</div>
	`);

	function run(phase) {
		const code = $("#itc-country").val();
		const method =
			code === "AE"
				? "omnexa_einvoice.uae.submission.process_uae_invoice"
				: "omnexa_einvoice.tax_engine.submission.process_country_tax_invoice";
		const args =
			code === "AE"
				? {
						reference_name: $("#itc-ref").val(),
						company: $("#itc-company").val() || frappe.defaults.get_default("company"),
						phase,
						sync: phase === "phase2" ? 1 : 0,
					}
				: {
						country_code: code,
						reference_name: $("#itc-ref").val(),
						company: $("#itc-company").val() || frappe.defaults.get_default("company"),
						phase,
						sync: phase === "phase2" ? 1 : 0,
					};
		frappe.call({
			method,
			args,
			freeze: true,
			callback(r) {
				$("#itc-output").text(JSON.stringify(r.message || r, null, 2));
			},
		});
	}

	function loadCountries() {
		frappe.call({
			method: "omnexa_einvoice.tax_engine.dispatch.list_supported_countries",
			callback(r) {
				const rows = (r.message || []).filter(
					(row) => row.pipeline_enabled && !["EG", "SA"].includes(row.country_code)
				);
				const $sel = $("#itc-country").empty();
				rows.forEach((row) => {
					const label = row.label_ar ? `${row.label} / ${row.label_ar}` : row.label;
					$sel.append(`<option value="${row.country_code}">${frappe.utils.escape_html(label)} (${row.country_code})</option>`);
				});
			},
		});
	}

	loadCountries();
	$("#itc-phase1").on("click", () => run("phase1"));
	$("#itc-phase2").on("click", () => run("phase2"));
	$("#itc-smoke-all").on("click", () => {
		frappe.call({
			method: "omnexa_einvoice.tax_engine.deploy_check.run_smoke_tests",
			args: { full: 1 },
			freeze: true,
			callback(r) {
				$("#itc-output").text(JSON.stringify(r.message || r, null, 2));
			},
		});
	});
	$("#itc-smoke-sample").on("click", () => {
		frappe.call({
			method: "omnexa_einvoice.tax_engine.deploy_check.run_smoke_tests",
			args: { full: 0 },
			freeze: true,
			callback(r) {
				$("#itc-output").text(JSON.stringify(r.message || r, null, 2));
			},
		});
	});
};
