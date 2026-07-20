// Copyright (c) 2026, Omnexa and contributors
// License: MIT

/** Shared tax connection test UI (Branch + consoles). */

frappe.provide("omnexa.einvoice");

omnexa.einvoice.showTaxConnectionTestResult = function showTaxConnectionTestResult(m) {
	const msg = m || {};
	const title =
		msg.tab_label && msg.country_code
			? `${msg.tab_label} (${msg.country_code})`
			: __("Tax connection");
	if (msg.ok) {
		const lines = [
			msg.message || __("Connection successful."),
			msg.branch ? `${__("Branch")}: ${msg.branch}` : "",
			msg.environment ? `${__("Environment")}: <b>${frappe.utils.escape_html(msg.environment)}</b>` : "",
			msg.api_base_url
				? `${__("API URL")}: ${frappe.utils.escape_html(msg.api_base_url)}`
				: "",
			msg.token_url ? `${__("Token URL")}: ${frappe.utils.escape_html(msg.token_url)}` : "",
			msg.pos_serial ? `${__("POS Serial")}: ${frappe.utils.escape_html(msg.pos_serial)}` : "",
			msg.vat ? `${__("VAT")}: ${frappe.utils.escape_html(msg.vat)}` : "",
			msg.rin ? `RIN: ${frappe.utils.escape_html(msg.rin)}` : "",
			msg.irn ? `IRN: ${frappe.utils.escape_html(msg.irn)}` : "",
			msg.sat_uuid ? `${__("SAT UUID")}: ${frappe.utils.escape_html(msg.sat_uuid)}` : "",
			msg.sdi_id ? `${__("SDI ID")}: ${frappe.utils.escape_html(msg.sdi_id)}` : "",
			msg.chave_acesso ? `${__("Chave NFe")}: ${frappe.utils.escape_html(msg.chave_acesso)}` : "",
			msg.ksef_number ? `${__("KSeF No.")}: ${frappe.utils.escape_html(msg.ksef_number)}` : "",
			msg.registro_id ? `${__("Registro")}: ${frappe.utils.escape_html(msg.registro_id)}` : "",
			msg.cufe ? `CUFE: ${frappe.utils.escape_html(msg.cufe)}` : "",
			msg.tracking_id ? `${__("Tracking")}: ${frappe.utils.escape_html(msg.tracking_id)}` : "",
			msg.flow_id ? `${__("Flow ID")}: ${frappe.utils.escape_html(msg.flow_id)}` : "",
			msg.asp_reference ? `${__("ASP Ref")}: ${frappe.utils.escape_html(msg.asp_reference)}` : "",
		].filter(Boolean);
		frappe.msgprint({
			title,
			indicator: "green",
			message: lines.join("<br>"),
		});
		return;
	}
	const checklist = (msg.checklist || [])
		.map((line) => `<li>${frappe.utils.escape_html(line)}</li>`)
		.join("");
	frappe.msgprint({
		title,
		indicator: "red",
		message: `<p><b>${frappe.utils.escape_html(msg.summary || msg.message || __("Test failed"))}</b></p>
			${checklist ? `<ul class="small mb-2">${checklist}</ul>` : ""}
			${msg.error ? `<p class="small text-muted">${frappe.utils.escape_html(msg.error)}</p>` : ""}`,
	});
};

omnexa.einvoice.runBranchTaxConnectionTest = async function runBranchTaxConnectionTest({
	branch,
	company,
	freeze_message,
}) {
	const r = await frappe.call({
		method: "omnexa_einvoice.tax_engine.branch_tax_connection.test_branch_tax_connection",
		args: { branch: branch || null, company: company || null },
		freeze: true,
		freeze_message: freeze_message || __("Testing tax connection…"),
	});
	omnexa.einvoice.showTaxConnectionTestResult(r.message);
	return r.message;
};

omnexa.einvoice.parseBranchCountryCode = function parseBranchCountryCode(raw) {
	const text = String(raw || "").trim();
	if (!text) {
		return "";
	}
	if (text.includes(" — ")) {
		return text.split(" — ", 1)[0].trim().toUpperCase();
	}
	if (text.includes(" - ") && text.length > 4) {
		return text.split(" - ", 1)[0].trim().toUpperCase();
	}
	return text.toUpperCase();
};

/** Prefer country_code (user selection); country_iso can lag until save. */
omnexa.einvoice.getBranchCountryIso = function getBranchCountryIso(frm) {
	const fromSelect = omnexa.einvoice.parseBranchCountryCode(frm.doc.country_code || "");
	if (fromSelect) {
		return fromSelect;
	}
	const iso = (frm.doc.country_iso || "").trim().toUpperCase();
	return iso || "EG";
};

omnexa.einvoice.removeBranchToolbarGroup = function removeBranchToolbarGroup(frm, groupLabel) {
	if (!frm || !frm.page || !groupLabel) {
		return;
	}
	const labels = [groupLabel, __(groupLabel)];
	for (const label of labels) {
		const $group = frm.page.get_inner_group_button(label);
		if ($group && $group.length) {
			$group.remove();
		}
	}
};

omnexa.einvoice.purgeForeignTaxToolbarGroups = function purgeForeignTaxToolbarGroups(frm) {
	const code = omnexa.einvoice.getBranchCountryIso(frm);
	if (code !== "EG") {
		omnexa.einvoice.removeBranchToolbarGroup(frm, "Egypt ETA");
	}
	if (code !== "SA") {
		omnexa.einvoice.removeBranchToolbarGroup(frm, "Saudi ZATCA");
	}
};

omnexa.einvoice.fetchBranchTaxTestSpec = async function fetchBranchTaxTestSpec({
	branch,
	company,
}) {
	const r = await frappe.call({
		method: "omnexa_einvoice.tax_engine.branch_tax_connection.get_branch_tax_test_spec",
		args: { branch: branch || null, company: company || null },
	});
	return r.message || {};
};

omnexa.einvoice.refreshConsoleTaxTestButton = async function refreshConsoleTaxTestButton(
	$btn,
	{ branch, company }
) {
	if (!$btn || !$btn.length) {
		return null;
	}
	const spec = await omnexa.einvoice.fetchBranchTaxTestSpec({ branch, company });
	if (spec.button_label) {
		$btn.text(spec.button_label);
	}
	$btn.prop("disabled", !!spec.needs_branch);
	$btn.attr("title", spec.needs_branch ? __("Select a branch first") : "");
	return spec;
};
