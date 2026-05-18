const ETA_BILLING_LABELS = {
	Regular: __("Regular Invoice"),
	"E-Invoice": __("Electronic Invoice"),
	"E-Receipt": __("Electronic Receipt"),
};

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		const billing = frm.doc.eta_billing_type || "Regular";
		if (frm.is_new() || billing === "Regular") {
			return;
		}
		const label =
			billing === "E-Receipt"
				? __("Create E-Receipt Queue")
				: __("Create E-Invoice Queue");
		frm.add_custom_button(label, async () => {
			const r = await frappe.call({
				method:
					"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.ensure_submission_for_document",
				args: { doctype: "Sales Invoice", docname: frm.doc.name },
				freeze: true,
			});
			if (r.message?.name) {
				frappe.set_route("Form", "E Invoice Submission", r.message.name);
			}
		}, __("ETA"));
		if (
			billing === "E-Invoice" &&
			frm.doc.branch &&
			omnexa.einvoice &&
			omnexa.einvoice.showCloudSigningBridgeTest
		) {
			frm.add_custom_button(
				__("Test cloud ↔ PC signing"),
				async () => {
					await omnexa.einvoice.showCloudSigningBridgeTest({
						branch: frm.doc.branch,
					});
				},
				__("ETA")
			);
		}
	},
	eta_billing_type(frm) {
		frm.set_df_property(
			"eta_billing_type",
			"description",
			frm.doc.eta_billing_type && frm.doc.eta_billing_type !== "Regular"
				? __("Requires ETA credentials on Branch {0}.", [frm.doc.branch || ""])
				: __("No ETA submission for regular invoices."),
		);
	},
	branch(frm) {
		if (frm.doc.eta_billing_type) {
			frm.trigger("eta_billing_type");
		}
	},
});
