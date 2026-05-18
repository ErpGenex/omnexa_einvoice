// Copyright (c) 2026, Omnexa and contributors
// License: MIT. See license.txt
/* global frappe */

/** E-Invoice USB signing v2 — sign_session (PIN fetched by agent from ERP). E-Receipt unchanged. */
const OMNEXA_EINV_SIGN_SESSION =
	"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.create_usb_sign_session";

async function omnexaPostAgentSignBody(msg) {
	const base = ((msg && msg.agent_url) || "http://127.0.0.1:5002").replace(/\/$/, "");
	const body = (msg && msg.agent_body) || {};
	if (!body.sign_session) {
		frappe.throw(
			__(
				"Signing session missing. Run bench update + build omnexa_einvoice, clear cache, Ctrl+Shift+R."
			)
		);
	}
	if (!body.erp_base_url) {
		body.erp_base_url = window.location.origin;
	}
	let health;
	try {
		health = await fetch(`${base}/health`, { method: "GET", mode: "cors" });
	} catch (e) {
		const hint =
			(typeof omnexa !== "undefined" &&
				omnexa.einvoice &&
				omnexa.einvoice.formatAgentFetchError &&
				omnexa.einvoice.formatAgentFetchError(e, base)) ||
			e.message ||
			"Failed to fetch";
		const err = new Error(hint);
		err.omnexa_html = true;
		throw err;
	}
	if (!health.ok) {
		frappe.throw(__("Signing agent not reachable at {0}", [base]));
	}
	let res;
	try {
		res = await fetch(`${base}/sign`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body),
			mode: "cors",
		});
	} catch (e) {
		const hint =
			(typeof omnexa !== "undefined" &&
				omnexa.einvoice &&
				omnexa.einvoice.formatAgentFetchError &&
				omnexa.einvoice.formatAgentFetchError(e, base)) ||
			e.message ||
			"Failed to fetch";
		const err = new Error(hint);
		err.omnexa_html = true;
		throw err;
	}
	let parsed = {};
	try {
		parsed = await res.json();
	} catch (e) {
		parsed = {};
	}
	if (!res.ok || !parsed.success) {
		frappe.throw(parsed.message || parsed.error || __("Signing agent failed"));
	}
	const sigs = parsed.signatures || [];
	let signature = "";
	if (sigs[0] && sigs[0].value) {
		signature = sigs[0].value;
	} else if (parsed.signature) {
		signature = parsed.signature;
	}
	if (!signature) {
		frappe.throw(__("Signing agent returned no signature"));
	}
	if (!parsed.signed_document) {
		frappe.throw(
			__(
				"Agent must return signed_document (update epass2003_agent.py on Windows). ITIDA rejects mismatched JSON."
			)
		);
	}
	if (!parsed.signed_document_json) {
		frappe.throw(
			__(
				"Agent must return signed_document_json (Chilkat Emit). Update epass2003_agent.py on Windows — fixes ETA 4043."
			)
		);
	}
	return {
		signature,
		signed_document: parsed.signed_document,
		signed_document_json: parsed.signed_document_json,
		canonical_json: parsed.canonical_json || null,
	};
}

async function omnexaSignEInvoiceViaAgent(submissionName) {
	const prep = await frappe.call({
		method: OMNEXA_EINV_SIGN_SESSION,
		args: { name: submissionName, for_send: 0 },
		freeze: true,
		freeze_message: __("Signing E-Invoice…"),
	});
	const signResult = await omnexaPostAgentSignBody(prep.message || {});
	return frappe.call({
		method:
			"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.sign_submission",
		args: {
			name: submissionName,
			client_signature: signResult.signature,
			agent_signed_document: signResult.signed_document,
			agent_signed_document_json: signResult.signed_document_json,
			agent_canonical_json: signResult.canonical_json,
		},
	});
}

async function omnexaSendEInvoiceViaAgent(submissionName) {
	const prep = await frappe.call({
		method: OMNEXA_EINV_SIGN_SESSION,
		args: { name: submissionName, for_send: 1 },
		freeze: true,
		freeze_message: __("Signing before ETA send…"),
	});
	const signResult = await omnexaPostAgentSignBody(prep.message || {});
	return frappe.call({
		method:
			"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.send_submission_to_eta",
		args: {
			name: submissionName,
			client_signature: signResult.signature,
			agent_signed_document: signResult.signed_document,
			agent_signed_document_json: signResult.signed_document_json,
			agent_canonical_json: signResult.canonical_json,
		},
	});
}

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
						const r = await omnexaSignEInvoiceViaAgent(frm.doc.name);
						const msg = r?.message || {};
						if (msg.signer_method) {
							frappe.show_alert({
								message: __("Signed via {0}", [msg.signer_method]),
								indicator: "green",
							});
						}
						if (msg.browser_live) {
							await omnexaSendEInvoiceViaAgent(frm.doc.name);
							frappe.show_alert({
								message: __("Sent to ETA (Live mode)"),
								indicator: "green",
							});
						} else if (msg.enqueued) {
							frappe.show_alert({
								message: __("Queued for ETA send (Live mode)"),
								indicator: "blue",
							});
						}
					} catch (e) {
						frappe.msgprint({
							title: __("Signing"),
							indicator: "red",
							message: e.omnexa_html ? e.message : frappe.utils.escape_html(e.message || String(e)),
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
						r = await omnexaSendEInvoiceViaAgent(frm.doc.name);
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
