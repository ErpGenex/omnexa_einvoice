// Copyright (c) 2026, Omnexa and contributors
// License: MIT

/** Branch form: country-aware «Test connection» button (never Egypt ETA when country ≠ EG). */

function get_branch_country_iso(frm) {
	if (omnexa.einvoice && omnexa.einvoice.getBranchCountryIso) {
		return omnexa.einvoice.getBranchCountryIso(frm);
	}
	const iso = (frm.doc.country_iso || "").trim().toUpperCase();
	if (iso) {
		return iso;
	}
	const text = String(frm.doc.country_code || "EG");
	if (text.includes(" — ")) {
		return text.split(" — ", 1)[0].trim().toUpperCase();
	}
	return text.toUpperCase();
}

function sync_country_iso_from_select(frm) {
	const code = get_branch_country_iso(frm);
	if (frm.doc.country_iso !== code) {
		frm.set_value("country_iso", code);
	}
}

function remove_branch_tax_test_button(frm) {
	if (!frm.page) {
		return;
	}
	const labels = [
		"Test tax connection",
		"Test ETA connection",
		"Test ETA e-Invoice connection",
		"Test ETA E-Receipt connection",
	];
	for (const label of labels) {
		frm.page.remove_inner_button(__(label));
		frm.page.remove_inner_button(__(label), __("Egypt ETA"));
	}
	frm.page.inner_toolbar
		.find('.dropdown-item[data-branch-tax-test="1"]')
		.remove();
	frm.page.inner_toolbar.find("button[data-branch-tax-test='1']").remove();
}

async function refresh_branch_tax_test_button(frm) {
	if (frm.is_new()) {
		return;
	}

	sync_country_iso_from_select(frm);

	if (omnexa.einvoice && omnexa.einvoice.purgeForeignTaxToolbarGroups) {
		omnexa.einvoice.purgeForeignTaxToolbarGroups(frm);
	}

	remove_branch_tax_test_button(frm);

	const code = get_branch_country_iso(frm);

	let spec;
	try {
		spec = await omnexa.einvoice.fetchBranchTaxTestSpec({ branch: frm.doc.name });
	} catch (e) {
		return;
	}
	if (!spec || !spec.button_label) {
		return;
	}
	if (spec.country_code !== code) {
		return;
	}
	if (code !== "EG" && (spec.button_label || "").includes("ETA")) {
		return;
	}

	const group = spec.button_group || spec.tab_label || __("Tax");
	const btn = frm
		.add_custom_button(
			spec.button_label,
			async () => {
				await omnexa.einvoice.runBranchTaxConnectionTest({
					branch: frm.doc.name,
					freeze_message: `${spec.button_label}…`,
				});
			},
			group
		)
		.addClass("btn-default");
	if (btn && btn.$btn) {
		btn.$btn.attr("data-branch-tax-test", "1");
	} else if (btn && btn.length) {
		btn.attr("data-branch-tax-test", "1");
	}
}

frappe.ui.form.on("Branch", {
	async refresh(frm) {
		await refresh_branch_tax_test_button(frm);
	},
	async country_code(frm) {
		await refresh_branch_tax_test_button(frm);
	},
	async country_iso(frm) {
		await refresh_branch_tax_test_button(frm);
	},
	eta_einvoice_enabled(frm) {
		if (get_branch_country_iso(frm) === "EG") {
			refresh_branch_tax_test_button(frm);
		} else if (omnexa.einvoice && omnexa.einvoice.purgeForeignTaxToolbarGroups) {
			omnexa.einvoice.purgeForeignTaxToolbarGroups(frm);
		}
	},
	eta_ereceipt_enabled(frm) {
		if (get_branch_country_iso(frm) === "EG") {
			refresh_branch_tax_test_button(frm);
		} else if (omnexa.einvoice && omnexa.einvoice.purgeForeignTaxToolbarGroups) {
			omnexa.einvoice.purgeForeignTaxToolbarGroups(frm);
		}
	},
	zatca_enabled(frm) {
		refresh_branch_tax_test_button(frm);
	},
	intl_tax_enabled(frm) {
		refresh_branch_tax_test_button(frm);
	},
});
