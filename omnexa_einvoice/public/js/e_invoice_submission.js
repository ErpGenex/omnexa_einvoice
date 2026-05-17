// Copyright (c) 2026, Omnexa and contributors
// License: MIT. See license.txt

frappe.ui.form.on("E Invoice Submission", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 0) {
			return;
		}
		const is_receipt = frm.doc.submission_kind === "E-Receipt";
		const allow_sign = ["Draft", "Failed", ...(is_receipt ? ["Queued"] : [])].includes(frm.doc.status);
		const allow_send = ["Signed", "Draft", "Failed", ...(is_receipt ? ["Queued"] : [])].includes(
			frm.doc.status
		);
		if (!allow_sign && !allow_send) {
			return;
		}
		if (!is_receipt && frm.doc.status && frm.doc.status !== "Draft") {
			// hub dispatch only from Draft (e-invoice)
		} else if (!is_receipt && frm.doc.status === "Draft") {
		frm.add_custom_button(__("Dispatch to authority"), () => {
			frappe.call({
				method: "omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.dispatch_submission",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Dispatching…"),
				callback(r) {
					if (!r.exc) {
						frappe.show_alert({ message: __("Integration hub updated"), indicator: "green" });
						frm.reload_doc();
					}
				},
			});
		}).addClass("btn-primary");
		}

		const sign_label =
			frm.doc.submission_kind === "E-Receipt" ? __("Prepare E-Receipt (UUID)") : __("Sign");
		if (allow_sign) {
		frm.add_custom_button(sign_label, async () => {
			let pin = "";
			if (frm.doc.submission_kind === "E-Invoice") {
				const values = await frappe.prompt(
					[{ fieldname: "pin", fieldtype: "Password", label: __("USB Token PIN"), reqd: 0 }],
					() => {},
					__("Sign Submission"),
					__("Sign"),
				);
				pin = values?.pin || "";
			}
			await frappe.call({
				method: "omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.sign_submission",
				args: { name: frm.doc.name, pin },
				freeze: true,
				freeze_message:
					frm.doc.submission_kind === "E-Receipt" ? __("Preparing receipt…") : __("Signing…"),
			});
			await frm.reload_doc();
		});
		}

		if (allow_send) {
		frm.add_custom_button(__("Send to ETA"), async () => {
			await frappe.call({
				method: "omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.send_submission_to_eta",
				args: { name: frm.doc.name },
				freeze: true,
				freeze_message: __("Sending..."),
			});
			await frm.reload_doc();
		}).addClass("btn-primary");
		}
	},
});
