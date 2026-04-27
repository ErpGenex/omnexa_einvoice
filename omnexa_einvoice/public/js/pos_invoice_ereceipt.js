frappe.ui.form.on("POS Invoice", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Create E-Receipt Queue"), async () => {
			const r = await frappe.call({
				method: "omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.ensure_submission_for_document",
				args: { doctype: "POS Invoice", docname: frm.doc.name },
				freeze: true,
			});
			if (r.message?.name) {
				frappe.set_route("Form", "E Invoice Submission", r.message.name);
			}
		}, __("ETA"));
	},
});
