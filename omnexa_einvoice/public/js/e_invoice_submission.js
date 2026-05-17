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
		if (!is_receipt && frm.doc.status === "Draft") {
			frm.add_custom_button(__("Dispatch to authority"), () => {
				frappe.call({
					method:
						"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.dispatch_submission",
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

		const sign_label = is_receipt
			? __("Prepare E-Receipt (UUID)")
			: __("Sign E-Invoice (ETA JSON)");

		if (allow_sign) {
			frm.add_custom_button(sign_label, async () => {
				if (is_receipt) {
					await frappe.call({
						method:
							"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.sign_submission",
						args: { name: frm.doc.name },
						freeze: true,
						freeze_message: __("Preparing receipt…"),
					});
				} else {
					try {
						await frappe.require("/assets/omnexa_einvoice/js/einvoice_usb_agent.js");
						if (!omnexa.einvoice?.signEInvoiceSubmission) {
							frappe.throw(
								__(
									"Signing scripts outdated. bench build --app omnexa_einvoice, clear cache, Ctrl+Shift+R."
								)
							);
						}
						const r = await omnexa.einvoice.signEInvoiceSubmission(frm.doc.name);
						if (r?.message?.signer_method) {
							frappe.show_alert({
								message: __("Signed via {0}", [r.message.signer_method]),
								indicator: "green",
							});
						}
					} catch (e) {
						frappe.msgprint({
							title: __("Signing"),
							indicator: "red",
							message: e.message || String(e),
						});
					}
				}
				await frm.reload_doc();
			});
		}

		if (allow_send) {
			frm.add_custom_button(__("Send to ETA"), async () => {
				try {
					let r;
					if (is_receipt) {
						r = await frappe.call({
							method:
								"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.send_submission_to_eta",
							args: { name: frm.doc.name },
							freeze: true,
							freeze_message: __("Sending..."),
						});
					} else {
						await frappe.require("/assets/omnexa_einvoice/js/einvoice_usb_agent.js");
						r = await omnexa.einvoice.sendEInvoiceSubmission(frm.doc.name);
					}
					if (r?.message) {
						const m = r.message;
						frappe.show_alert(
							{
								message: [m.status, m.uuid, m.submission_id, m.message].filter(Boolean).join(" · "),
								indicator: m.ok ? "green" : "red",
							},
							8
						);
						if (m.ok) {
							frappe.msgprint({
								title: __("ETA"),
								indicator: "green",
								message: __("Sent successfully. UUID: {0}", [m.uuid || "—"]),
							});
						}
					}
				} catch (e) {
					frappe.msgprint({
						title: __("ETA"),
						indicator: "red",
						message: e.message || String(e),
					});
				}
				await frm.reload_doc();
			}).addClass("btn-primary");
		}
	},
});
