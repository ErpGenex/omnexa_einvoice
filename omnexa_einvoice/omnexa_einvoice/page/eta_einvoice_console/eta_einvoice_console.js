frappe.pages["eta-einvoice-console"].on_page_load = function (wrapper) {
	frappe.provide("omnexa.einvoice");

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("ETA E-Invoice Console"),
		single_column: true,
	});

	page.set_primary_action(__("Refresh"), () => load_queue(), "refresh");
	page.set_secondary_action(__("New E-Invoice"), () => {
		frappe.new_doc("Sales Invoice", { eta_billing_type: "E-Invoice" });
	});

	const $root = $(`
		<div class="eta-einvoice-console">
			<p class="text-muted small mb-3">
				${__(
					"E-Invoice sales invoices: sign (USB agent on Windows or server signer), then send to ETA. Submit the Sales Invoice first."
				)}
			</p>
			<div class="row g-2 mb-3">
				<div class="col-md-3">
					<label class="small text-muted">${__("Company")}</label>
					<select class="form-select form-select-sm" data-filter="company"></select>
				</div>
				<div class="col-md-3">
					<label class="small text-muted">${__("Branch")}</label>
					<select class="form-select form-select-sm" data-filter="branch">
						<option value="">${__("All")}</option>
					</select>
				</div>
				<div class="col-md-2">
					<label class="small text-muted">${__("From Date")}</label>
					<input type="date" class="form-control form-control-sm" data-filter="from_date" />
				</div>
				<div class="col-md-2">
					<label class="small text-muted">${__("To Date")}</label>
					<input type="date" class="form-control form-control-sm" data-filter="to_date" />
				</div>
				<div class="col-md-2">
					<label class="small text-muted">${__("ETA Status")}</label>
					<select class="form-select form-select-sm" data-filter="eta_status">
						<option value="">${__("All")}</option>
						<option value="pending">${__("Pending sign")}</option>
						<option value="ready">${__("Signed — ready to send")}</option>
						<option value="completed">${__("Completed")}</option>
					</select>
				</div>
			</div>
			<div class="mb-3 d-flex gap-2 flex-wrap align-items-center">
				<button class="btn btn-outline-secondary btn-sm" data-action="select-all">${__("Select all")}</button>
				<button class="btn btn-outline-secondary btn-sm" data-action="clear-sel">${__("Clear")}</button>
				<button class="btn btn-default btn-sm" data-action="test-auth">${__("Test ETA connection")}</button>
				<button class="btn btn-default btn-sm" data-action="test-signing-bridge">${__("Test cloud ↔ PC signing")}</button>
				<button class="btn btn-warning btn-sm" data-action="sign-sel">${__("Sign selected")}</button>
				<button class="btn btn-primary btn-sm" data-action="send-sel">${__("Send selected to ETA")}</button>
				<span class="text-muted small">${__("USB signing runs on this PC (agent :5002).")}</span>
			</div>
			<div class="alert alert-light py-2 small mb-2" data-section="summary">${__("Loading…")}</div>
			<div class="table-responsive border rounded">
				<table class="table table-sm table-hover mb-0">
					<thead class="table-light">
						<tr>
							<th style="width:32px"><input type="checkbox" data-action="toggle-page" title="${__("Select page")}" /></th>
							<th>${__("Sales Invoice")}</th>
							<th>${__("Date")}</th>
							<th>${__("Customer")}</th>
							<th>${__("Branch")}</th>
							<th class="text-end">${__("Amount")}</th>
							<th>${__("Invoice")}</th>
							<th>${__("ETA Status")}</th>
							<th>${__("Signer")}</th>
							<th style="width:280px">${__("Actions")}</th>
						</tr>
					</thead>
					<tbody data-section="rows">
						<tr><td colspan="10" class="text-muted p-3">${__("Loading…")}</td></tr>
					</tbody>
				</table>
			</div>
		</div>
	`);

	$(page.body).append($root);

	let queue_rows = [];
	const selected = new Set();

	const filter_val = (k) => String($root.find(`[data-filter="${k}"]`).val() || "").trim();

	const status_indicator = (status) => {
		const map = {
			Completed: "green",
			Signed: "blue",
			Draft: "orange",
			Failed: "red",
			Queued: "purple",
			"Not Registered": "grey",
		};
		return map[status] || "grey";
	};

	const render_rows = () => {
		const $tbody = $root.find('[data-section="rows"]');
		if (!queue_rows.length) {
			$tbody.html(
				`<tr><td colspan="10" class="text-muted p-3">${__(
					"No e-invoice sales invoices match the filters."
				)}</td></tr>`
			);
			$root
				.find('[data-section="summary"]')
				.text(__("{0} invoice(s)", [0]));
			return;
		}
		const html = queue_rows
			.map((row) => {
				const checked = selected.has(row.sales_invoice) ? "checked" : "";
				const amt = format_currency(row.grand_total, row.currency);
				const si = frappe.utils.escape_html(row.sales_invoice);
				const submitted = parseInt(row.docstatus, 10) === 1;
				const invStatus = frappe.utils.escape_html(row.invoice_status || "");
				const signer = frappe.utils.escape_html(
					row.browser_signing ? __("USB Agent") : row.signer_mode || "—"
				);
				const canSign = submitted && row.can_sign;
				const canSend = submitted && row.can_send;
				return `
				<tr data-invoice="${si}" data-submission="${frappe.utils.escape_html(row.submission || "")}" data-browser="${row.browser_signing ? "1" : "0"}">
					<td><input type="checkbox" class="row-check" data-invoice="${si}" ${checked} /></td>
					<td><a href="/app/sales-invoice/${encodeURIComponent(row.sales_invoice)}">${si}</a></td>
					<td>${row.posting_date || ""}</td>
					<td>${frappe.utils.escape_html(row.customer_name || row.customer || "")}</td>
					<td>${frappe.utils.escape_html(row.branch || "")}</td>
					<td class="text-end">${amt}</td>
					<td><span class="indicator-pill ${submitted ? "green" : "orange"} filterable no-indicator-dot">${invStatus}</span></td>
					<td><span class="indicator-pill ${status_indicator(row.eta_status)} filterable no-indicator-dot">${__(
					row.eta_status
				)}</span></td>
					<td class="small text-muted">${signer}</td>
					<td class="text-nowrap">
						<button class="btn btn-xs btn-default" data-row-action="preview" data-invoice="${si}">${__(
					"Preview"
				)}</button>
						<button class="btn btn-xs btn-warning" data-row-action="sign" data-invoice="${si}" ${
					canSign ? "" : "disabled"
				}>${__("Sign")}</button>
						<button class="btn btn-xs btn-primary" data-row-action="send" data-invoice="${si}" ${
					canSend ? "" : "disabled"
				}>${__("Send")}</button>
					</td>
				</tr>`;
			})
			.join("");
		$tbody.html(html);
		$root
			.find('[data-section="summary"]')
			.text(__("{0} invoice(s) · {1} selected", [queue_rows.length, selected.size]));
	};

	const load_queue = async () => {
		$root.find('[data-section="summary"]').text(__("Loading…"));
		const r = await frappe.call({
			method: "omnexa_einvoice.einvoice_console.get_einvoice_queue",
			args: {
				company: filter_val("company") || null,
				branch: filter_val("branch") || null,
				from_date: filter_val("from_date") || null,
				to_date: filter_val("to_date") || null,
				eta_status: filter_val("eta_status") || null,
			},
		});
		queue_rows = r.message || [];
		render_rows();
	};

	const load_companies = async () => {
		const r = await frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Company",
				fields: ["name"],
				limit_page_length: 200,
				order_by: "name asc",
			},
		});
		const $sel = $root.find('[data-filter="company"]');
		$sel.empty().append(`<option value="">${__("All")}</option>`);
		(r.message || []).forEach((c) => $sel.append(`<option value="${c.name}">${c.name}</option>`));
	};

	const load_branches = async (company) => {
		const $sel = $root.find('[data-filter="branch"]');
		$sel.find("option:not(:first)").remove();
		if (!company) return;
		const r = await frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Branch",
				filters: { company },
				fields: ["name", "branch_name"],
				limit_page_length: 200,
			},
		});
		(r.message || []).forEach((b) => {
			$sel.append(`<option value="${b.name}">${b.branch_name || b.name}</option>`);
		});
	};

	const row_by_invoice = (invoice) => queue_rows.find((r) => r.sales_invoice === invoice);

	const load_invoice_ctx = async (sales_invoice) => {
		let row = row_by_invoice(sales_invoice);
		if (row && row.submission) {
			return row;
		}
		const r = await frappe.call({
			method: "omnexa_einvoice.einvoice_console.preview_einvoice",
			args: { sales_invoice, signed: 0 },
		});
		const m = r.message || {};
		row = {
			sales_invoice,
			submission: m.submission,
			browser_signing: m.browser_signing,
			can_sign: m.can_sign,
			can_send: m.can_send,
		};
		return row;
	};

	const sign_invoice = async (sales_invoice) => {
		const row = await load_invoice_ctx(sales_invoice);
		const submission = row.submission;
		if (row.browser_signing) {
			await omnexa.einvoice.signEInvoiceSubmission(submission);
		} else {
			await frappe.call({
				method: "omnexa_einvoice.einvoice_console.sign_einvoice_server",
				args: { sales_invoice },
				freeze: true,
				freeze_message: __("Signing…"),
			});
		}
		frappe.show_alert({ message: __("Signed"), indicator: "green" });
	};

	const send_invoice = async (sales_invoice) => {
		const row = await load_invoice_ctx(sales_invoice);
		const submission = row.submission;
		if (row.browser_signing) {
			await omnexa.einvoice.sendEInvoiceSubmission(submission);
		} else {
			const r = await frappe.call({
				method: "omnexa_einvoice.einvoice_console.send_einvoice",
				args: { sales_invoice },
				freeze: true,
				freeze_message: __("Sending to ETA…"),
			});
			const m = r.message || {};
			if (!m.ok) {
				frappe.throw(m.message || __("Send failed"));
			}
		}
		frappe.show_alert({ message: __("Sent to ETA"), indicator: "green" });
	};

	const show_preview_dialog = (payload) => {
		const row = row_by_invoice(payload.sales_invoice) || {};
		const d = new frappe.ui.Dialog({
			title: __("E-Invoice preview — {0}", [payload.sales_invoice]),
			size: "large",
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "meta",
					options: `<div class="small text-muted mb-2">${__(
						"Branch"
					)}: <b>${payload.branch}</b> · ${__("Internal ID")}: <b>${payload.internal_id || "—"}</b>${
						payload.signed ? ` · ${__("Signed")}` : ""
					}</div>`,
				},
				{
					fieldtype: "Code",
					fieldname: "json",
					label: __("Invoice JSON"),
					options: "JSON",
					default: JSON.stringify(payload.document, null, 2),
				},
			],
			primary_action_label: row.can_send ? __("Send to ETA") : __("Sign"),
			primary_action: async () => {
				d.hide();
				frappe.dom.freeze(row.can_send ? __("Sending…") : __("Signing…"));
				try {
					if (row.can_send) {
						await send_invoice(payload.sales_invoice);
					} else {
						await sign_invoice(payload.sales_invoice);
					}
					await load_queue();
				} finally {
					frappe.dom.unfreeze();
				}
			},
			secondary_action_label: __("Close"),
			secondary_action() {
				d.hide();
			},
		});
		d.show();
		d.fields_dict.json.$wrapper.find("textarea").attr("rows", 18);
	};

	const show_review_dialog = async (names, bulkAction) => {
		const r = await frappe.call({
			method: "omnexa_einvoice.einvoice_console.get_review_summary",
			args: { sales_invoices: names },
			freeze: true,
		});
		const rows = r.message || [];
		const table = rows
			.map(
				(row) => `<tr>
				<td>${frappe.utils.escape_html(row.sales_invoice)}</td>
				<td>${format_currency(row.grand_total, row.currency)}</td>
				<td>${frappe.utils.escape_html(row.branch || "")}</td>
				<td>${frappe.utils.escape_html(row.eta_status)}</td>
				<td class="small">${frappe.utils.escape_html(row.eta_uuid || "—")}</td>
			</tr>`
			)
			.join("");
		const d = new frappe.ui.Dialog({
			title: __("Review before send"),
			size: "large",
			fields: [
				{
					fieldtype: "HTML",
					options: `<table class="table table-sm">
						<thead><tr><th>${__("Invoice")}</th><th>${__("Amount")}</th><th>${__("Branch")}</th><th>${__(
						"Status"
					)}</th><th>${__("UUID")}</th></tr></thead>
						<tbody>${table}</tbody>
					</table>`,
				},
			],
			primary_action_label: bulkAction === "sign" ? __("Sign selected") : __("Send to ETA"),
			primary_action: async () => {
				d.hide();
				if (bulkAction === "sign") {
					await run_bulk_sign(names);
				} else {
					await run_bulk_send(names);
				}
			},
		});
		d.show();
	};

	const run_bulk_sign = async (names) => {
		const results = [];
		frappe.dom.freeze(__("Signing…"));
		try {
			for (const name of names) {
				try {
					await sign_invoice(name);
					results.push({ sales_invoice: name, ok: true });
				} catch (e) {
					results.push({ sales_invoice: name, ok: false, error: e.message || String(e) });
				}
			}
			show_bulk_result(results, __("Sign"));
			await load_queue();
		} finally {
			frappe.dom.unfreeze();
		}
	};

	const run_bulk_send = async (names) => {
		const usb = names.filter((n) => (row_by_invoice(n) || {}).browser_signing);
		const server = names.filter((n) => !(row_by_invoice(n) || {}).browser_signing);
		const results = [];
		frappe.dom.freeze(__("Sending to ETA…"));
		try {
			for (const name of usb) {
				try {
					await send_invoice(name);
					results.push({ sales_invoice: name, ok: true });
				} catch (e) {
					results.push({ sales_invoice: name, ok: false, error: e.message || String(e) });
				}
			}
			if (server.length) {
				const r = await frappe.call({
					method: "omnexa_einvoice.einvoice_console.bulk_send_einvoices",
					args: { sales_invoices: server },
				});
				results.push(...(r.message || []));
			}
			show_bulk_result(results, __("Send"));
			await load_queue();
		} finally {
			frappe.dom.unfreeze();
		}
	};

	const show_bulk_result = (results, action_label) => {
		const ok = results.filter((x) => x.ok).length;
		const fail = results.length - ok;
		let html = `<p>${action_label}: <b>${ok}</b> ${__("OK")}, <b>${fail}</b> ${__("failed")}</p>`;
		if (fail) {
			html += '<ul class="small">';
			results
				.filter((x) => !x.ok)
				.forEach((x) => {
					html += `<li>${frappe.utils.escape_html(x.sales_invoice)}: ${frappe.utils.escape_html(
						x.error || x.message || __("Unknown error")
					)}</li>`;
				});
			html += "</ul>";
		}
		frappe.msgprint({ title: __("Bulk result"), message: html, indicator: fail ? "orange" : "green" });
	};

	const selected_names = () => Array.from(selected);

	$root.on("change", '[data-filter="company"]', function () {
		load_branches($(this).val());
		load_queue();
	});
	$root.on("change", '[data-filter="branch"], [data-filter="from_date"], [data-filter="to_date"], [data-filter="eta_status"]', () =>
		load_queue()
	);

	$root.on("change", ".row-check", function () {
		const name = $(this).data("invoice");
		if (this.checked) selected.add(name);
		else selected.delete(name);
		render_rows();
	});

	$root.on("click", '[data-action="select-all"]', () => {
		queue_rows.forEach((r) => selected.add(r.sales_invoice));
		render_rows();
	});
	$root.on("click", '[data-action="clear-sel"]', () => {
		selected.clear();
		render_rows();
	});
	$root.on("change", '[data-action="toggle-page"]', function () {
		if (this.checked) queue_rows.forEach((r) => selected.add(r.sales_invoice));
		else selected.clear();
		render_rows();
	});

	$root.on("click", '[data-action="test-auth"]', async () => {
		const r = await frappe.call({
			method: "omnexa_einvoice.einvoice_console.test_eta_einvoice_connection",
			args: {
				company: filter_val("company") || null,
				branch: filter_val("branch") || null,
			},
			freeze: true,
			freeze_message: __("Testing ETA…"),
		});
		const m = r.message || {};
		frappe.msgprint({
			title: __("ETA e-Invoice connection"),
			indicator: m.ok ? "green" : "red",
			message: m.ok
				? `${m.message}<br>${__("Branch")}: ${m.branch}<br>${__("Environment")}: <b>${m.environment}</b><br>${__(
						"API"
				  )}: ${m.api_base_url || ""}<br>${__("RIN")}: ${m.rin || ""}`
				: `<p>${m.message || ""}</p><p class="small text-danger">${frappe.utils.escape_html(
						m.error || ""
				  )}</p>`,
		});
	});

	$root.on("click", '[data-action="test-signing-bridge"]', async () => {
		const branch = filter_val("branch");
		if (!branch) {
			frappe.msgprint(__("Select a Branch filter first."));
			return;
		}
		if (!omnexa.einvoice || !omnexa.einvoice.showCloudSigningBridgeTest) {
			frappe.msgprint(__("Reload ERP (Ctrl+Shift+R) after omnexa_einvoice update."));
			return;
		}
		await omnexa.einvoice.showCloudSigningBridgeTest({ branch });
	});

	$root.on("click", '[data-action="sign-sel"]', async () => {
		const names = selected_names();
		if (!names.length) {
			frappe.msgprint(__("Select at least one invoice."));
			return;
		}
		await show_review_dialog(names, "sign");
	});

	$root.on("click", '[data-action="send-sel"]', async () => {
		const names = selected_names();
		if (!names.length) {
			frappe.msgprint(__("Select at least one invoice."));
			return;
		}
		await show_review_dialog(names, "send");
	});

	$root.on("click", "[data-row-action]", async function () {
		const action = $(this).data("row-action");
		const invoice = $(this).data("invoice");
		frappe.dom.freeze();
		try {
			if (action === "preview") {
				const r = await frappe.call({
					method: "omnexa_einvoice.einvoice_console.preview_einvoice",
					args: { sales_invoice: invoice, signed: 0 },
				});
				show_preview_dialog(r.message);
			} else if (action === "sign") {
				await sign_invoice(invoice);
				await load_queue();
			} else if (action === "send") {
				await send_invoice(invoice);
				await load_queue();
			}
		} catch (e) {
			frappe.msgprint({
				title: __("E-Invoice"),
				indicator: "red",
				message: e.omnexa_html ? e.message : frappe.utils.escape_html(e.message || String(e)),
			});
		} finally {
			frappe.dom.unfreeze();
		}
	});

	(async () => {
		await load_companies();
		const today = frappe.datetime.get_today();
		const month_start = frappe.datetime.month_start(today);
		$root.find('[data-filter="from_date"]').val(month_start);
		$root.find('[data-filter="to_date"]').val(today);
		await load_queue();
	})();
};
