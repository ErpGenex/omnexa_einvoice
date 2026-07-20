// Copyright (c) 2026, Omnexa and contributors
// License: MIT. See license.txt
/* global frappe */

/**
 * @deprecated Not loaded in hooks — use einvoice_usb_agent.js only (avoids overwriting cloud/PNA signing).
 * E-Invoice USB signing via local epass2003_agent (browser → 127.0.0.1:5002).
 */
frappe.provide("omnexa.einvoice");
omnexa.einvoice.AGENT_JS_VERSION = "20260517.4";

const EINV_AGENT_PAYLOAD_SIGN =
	"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.get_agent_sign_payload_for_submission";
const EINV_AGENT_PAYLOAD_BRANCH_TEST =
	"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.get_agent_sign_payload_for_branch_test";

omnexa.einvoice.postAgentSignPayload = async function postAgentSignPayload(msg) {
	const base = ((msg && msg.agent_url) || "http://127.0.0.1:5002").replace(/\/$/, "");
	const payload = (msg && msg.agent_body) || (msg && msg.agent_payload) || {};
	if (!payload.sign_session && !(payload.pin || payload.usb_token_pin || "").trim()) {
		throw new Error(
			__(
				"Signing session missing. bench update omnexa_einvoice, build, clear-cache, Ctrl+Shift+R."
			)
		);
	}
	if (!payload.erp_base_url) {
		payload.erp_base_url = window.location.origin;
	}
	let health;
	try {
		health = await fetch(`${base}/health`, { method: "GET" });
	} catch (e) {
		throw new Error(
			__(
				"Cannot reach signing agent at {0}. Run epass2003_agent.py on this Windows PC. {1}",
				[base, e.message || e]
			)
		);
	}
	if (!health.ok) {
		throw new Error(__("Signing agent health check failed at {0}", [base]));
	}
	const res = await fetch(`${base}/sign`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(payload),
	});
	let body = {};
	try {
		body = await res.json();
	} catch (e) {
		body = {};
	}
	if (!res.ok || !body.success) {
		throw new Error(body.message || body.error || res.statusText || __("Signing agent failed"));
	}
	const sigs = body.signatures || [];
	if (sigs[0] && sigs[0].value) {
		return sigs[0].value;
	}
	if (body.signature) {
		return body.signature;
	}
	throw new Error(__("Signing agent returned no signature"));
};

omnexa.einvoice.pickSigningSecretB64 = function pickSigningSecretB64(ctx) {
	const c = ctx || {};
	return (c.signing_secret_b64 || c.usb_pin_b64 || "").trim();
};

omnexa.einvoice.fetchBranchSigningSecretB64 = async function fetchBranchSigningSecretB64(branch) {
	const r = await frappe.call({
		method:
			"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.get_branch_signing_secret_b64",
		args: { branch },
	});
	return omnexa.einvoice.pickSigningSecretB64(r.message || {});
};

omnexa.einvoice.resolveSigningSecretB64 = async function resolveSigningSecretB64(ctx) {
	let b64 = omnexa.einvoice.pickSigningSecretB64(ctx);
	if (b64) {
		return b64;
	}
	const branch = (ctx && ctx.branch) || "";
	if (!branch) {
		throw new Error(
			__(
				"USB Token PIN was not returned from ERP. Hard-refresh (Ctrl+Shift+R), re-save Branch PIN, then retry."
			)
		);
	}
	return omnexa.einvoice.fetchBranchSigningSecretB64(branch);
};

omnexa.einvoice.decodeBranchUsbPin = function decodeBranchUsbPin(usbPinB64) {
	const raw = (usbPinB64 || "").trim();
	if (!raw) {
		throw new Error(
			__(
				"USB Token PIN is not set on Branch. Open Branch → Egypt ETA → USB Token PIN, enter it once, Save, then Ctrl+Shift+R. Sign/Send will not ask for PIN."
			)
		);
	}
	try {
		return decodeURIComponent(escape(atob(raw)));
	} catch (e) {
		throw new Error(__("Invalid USB PIN from Branch settings. Re-enter PIN on Branch and Save."));
	}
};

omnexa.einvoice.signWithLocalAgent = async function signWithLocalAgent({
	agentUrl,
	document,
	usbPinB64,
	signingSecretB64,
	branch,
	tokenType,
}) {
	let pinB64 = (signingSecretB64 || usbPinB64 || "").trim();
	if (!pinB64) {
		pinB64 = await omnexa.einvoice.resolveSigningSecretB64({
			branch,
			signing_secret_b64: signingSecretB64,
			usb_pin_b64: usbPinB64,
		});
	}
	if (!pinB64) {
		throw new Error(
			__(
				"USB Token PIN is not set on Branch. Open Branch → Egypt ETA → USB Token PIN, enter it once, Save, then Ctrl+Shift+R."
			)
		);
	}
	const plainPin = omnexa.einvoice.decodeBranchUsbPin(pinB64);
	const base = (agentUrl || "http://127.0.0.1:5002").replace(/\/$/, "");

	const unsigned = JSON.parse(JSON.stringify(document || {}));
	delete unsigned.signatures;

	let health;
	try {
		health = await fetch(`${base}/health`, { method: "GET" });
	} catch (e) {
		const detail = e.message || String(e);
		const refused =
			/failed to fetch|networkerror|connection refused|err_connection/i.test(detail);
		if (refused) {
			throw new Error(
				__(
					"Cannot reach signing agent at {0}. On the Windows PC with the USB token: run epass2003_agent.py, then retry. If ERP is open on another machine, use that PC's browser (127.0.0.1 is only local).",
					[base]
				)
			);
		}
		throw new Error(
			__("Cannot reach signing agent at {0}. Start epass2003_agent.py on this PC. {1}", [
				base,
				detail,
			])
		);
	}
	if (!health.ok) {
		throw new Error(__("Signing agent health check failed at {0}", [base]));
	}

	const res = await fetch(`${base}/sign`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({
			invoice: unsigned,
			pin: plainPin,
			pin_b64: pinB64,
			signing_secret_b64: pinB64,
			token_type: tokenType || "epass2003",
			use_chilkat: true,
			verify: false,
		}),
	});

	let body = {};
	try {
		body = await res.json();
	} catch (e) {
		body = {};
	}

	if (!res.ok || !body.success) {
		const msg = body.message || body.error || res.statusText || __("Signing agent failed");
		throw new Error(msg);
	}

	const sigs = body.signatures || [];
	if (sigs[0] && sigs[0].value) {
		return sigs[0].value;
	}
	if (body.signature) {
		return body.signature;
	}
	throw new Error(__("Signing agent returned no signature"));
};

omnexa.einvoice.formatSigningTestChecks = function formatSigningTestChecks(checks) {
	return (checks || [])
		.map((c) => {
			const ok = !!c.ok;
			const step = frappe.utils.escape_html(c.step || "");
			const msg = frappe.utils.escape_html(c.message || "");
			const color = ok ? "var(--green-600)" : "var(--red-600)";
			const mark = ok ? "✓" : "✗";
			const line = [
				'<div style="margin-bottom:6px;color:',
				color,
				'"><strong>',
				mark,
				" ",
				step,
				"</strong>: ",
				msg,
				"</div>",
			].join("");
			return line;
		})
		.join("");
};

omnexa.einvoice.showSigningTestResult = function showSigningTestResult({ title, indicator, checks, extra }) {
	const parts = [];
	if (checks && checks.length) {
		parts.push(omnexa.einvoice.formatSigningTestChecks(checks));
	}
	if (extra) {
		parts.push(`<div style="margin-top:12px">${extra}</div>`);
	}
	frappe.msgprint({
		title: title || __("USB Signing Test"),
		indicator: indicator || "blue",
		message: parts.join(""),
	});
};

omnexa.einvoice.testBranchUsbSigning = async function testBranchUsbSigning(branch) {
	const prep = await frappe.call({
		method: "omnexa_einvoice.eta_signing_agent.prepare_branch_usb_signing_test",
		args: { branch },
		freeze: true,
		freeze_message: __("Checking branch signing settings…"),
	});
	const ctx = prep.message || {};
	const checks = [...(ctx.checks || [])];

	if (!ctx.ok) {
		omnexa.einvoice.showSigningTestResult({
			title: __("USB Signing Test — configuration failed"),
			indicator: "red",
			checks,
			extra: frappe.utils.escape_html(
				__(
					"Fix the items marked ✗, Save the branch, then run the test again. No call was made to the local agent."
				)
			),
		});
		return { ok: false, checks };
	}

	let signature = null;
	try {
		const agentPrep = await frappe.call({
			method: EINV_AGENT_PAYLOAD_BRANCH_TEST,
			args: { branch },
		});
		signature = await omnexa.einvoice.postAgentSignPayload(agentPrep.message || {});
		checks.push({
			ok: true,
			step: "local_agent",
			message: __("Signing agent returned a signature ({0} characters).", [signature.length]),
		});
		checks.push({
			ok: true,
			step: "health",
			message: __("Agent reachable at {0}", [ctx.agent_url]),
		});
	} catch (e) {
		const errMsg = e.message || String(e);
		checks.push({
			ok: false,
			step: "local_agent",
			message: errMsg,
		});
		omnexa.einvoice.showSigningTestResult({
			title: __("USB Signing Test — agent error"),
			indicator: "red",
			checks,
			extra: [
				frappe.utils.escape_html(
					__(
						"On the PC with the USB token: start epass2003_agent.py, insert the token, verify PIN on Branch, then retry."
					)
				),
				"<br><br>",
				"<strong>",
				__("Agent URL"),
				":</strong> ",
				frappe.utils.escape_html(ctx.agent_url || ""),
			].join(""),
		});
		try {
			await frappe.call({
				method: "omnexa_einvoice.eta_signing_agent.report_branch_usb_signing_test_result",
				args: { branch, success: false, message: errMsg },
			});
		} catch (logErr) {
			// ignore logging failures
		}
		return { ok: false, checks, error: errMsg };
	}

	const preview = frappe.utils.escape_html(`${signature.slice(0, 48)}…`);
	omnexa.einvoice.showSigningTestResult({
		title: __("USB Signing Test — success"),
		indicator: "green",
		checks,
		extra: [
			"<strong>",
			__("Test internalID"),
			":</strong> ",
			frappe.utils.escape_html(ctx.internal_id || ""),
			"<br><strong>",
			__("Signature preview"),
			":</strong> ",
			preview,
			"<br><em>",
			frappe.utils.escape_html(
				__("This was a local test only; nothing was sent to ETA.")
			),
			"</em>",
		].join(""),
	});

	try {
		await frappe.call({
			method: "omnexa_einvoice.eta_signing_agent.report_branch_usb_signing_test_result",
			args: {
				branch,
				success: true,
				signature_length: signature.length,
				message: "ok",
			},
		});
	} catch (logErr) {
		// ignore
	}

	return { ok: true, checks, signature_length: signature.length };
};

omnexa.einvoice.signEInvoiceSubmission = async function signEInvoiceSubmission(name) {
	const prep = await frappe.call({
		method:
			"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.create_usb_sign_session",
		args: { name, for_send: 0 },
	});
	const clientSignature = await omnexa.einvoice.postAgentSignPayload(prep.message || {});
	return frappe.call({
		method:
			"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.sign_submission",
		args: { name, client_signature: clientSignature },
	});
};

omnexa.einvoice.sendEInvoiceSubmission = async function sendEInvoiceSubmission(name) {
	const prep = await frappe.call({
		method:
			"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.create_usb_sign_session",
		args: { name, for_send: 1 },
	});
	const clientSignature = await omnexa.einvoice.postAgentSignPayload(prep.message || {});
	return frappe.call({
		method:
			"omnexa_einvoice.omnexa_einvoice.doctype.e_invoice_submission.e_invoice_submission.send_submission_to_eta",
		args: { name, client_signature: clientSignature },
	});
};
