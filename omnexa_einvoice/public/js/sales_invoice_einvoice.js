frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.is_new()) return;
		const label = frm.doc.is_pos ? __("Create E-Receipt Queue") : __("Create E-Invoice Queue");
		frm.add_custom_button(label, async () => {
			const r = await frappe.call({
				method: "omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.ensure_submission_for_document",
				args: { doctype: "Sales Invoice", docname: frm.doc.name },
				freeze: true,
			});
			if (r.message?.name) {
				frappe.set_route("Form", "E Invoice Submission", r.message.name);
			}
		}, __("ETA"));
	},
});
