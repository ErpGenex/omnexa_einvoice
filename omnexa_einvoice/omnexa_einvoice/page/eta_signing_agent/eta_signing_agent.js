// Copyright (c) 2026, Omnexa and contributors
/* global frappe */

frappe.pages["eta-signing-agent"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("USB Signing Agent"),
		single_column: true,
	});

	page.set_primary_action(__("Refresh"), () => load_release(), "refresh");

	const $wrap = $("<div>").addClass("omnexa-signing-agent-page");
	const $info = $("<div>").addClass("alert alert-info");
	$info.text(
		__(
			"Install on the Windows PC that has the USB token. No Python required on that PC after install."
		)
	);
	const $panel = $("<div>").attr("data-release-panel", "").addClass("mb-4");
	const $h = $("<h6>").text(__("Setup"));
	const $ol = $("<ol>").addClass("small text-muted");
	[
		__("Download and extract the ZIP to a folder (e.g. C:\\OmnexaESigningAgent)."),
		__("Install ePass2003 / token drivers if not already installed."),
		__(
			"Optional: copy chilkat_config.json.example to chilkat_config.json and set your Chilkat v10 unlock code."
		),
		__("Run Start_Omnexa_ESigning_Agent.bat and keep the window open."),
		__(
			"In ERP: Branch → Egypt ETA → Signing Agent URL = http://127.0.0.1:5002 and USB PIN + Chilkat key."
		),
		__("Sign / Send E-Invoice from the browser on the same Windows PC."),
	].forEach((t) => $ol.append($("<li>").text(t)));

	$wrap.append($info, $panel, $h, $ol);
	page.main.append($wrap);

	function load_release() {
		frappe.call({
			method: "omnexa_einvoice.signing_agent_release.get_signing_agent_release",
			callback(r) {
				const data = r.message || {};
				const $target = page.main.find("[data-release-panel]");
				$target.empty();
				if (data.available) {
					const mb = ((data.size_bytes || 0) / (1024 * 1024)).toFixed(1);
					const $card = $("<div>").addClass("card");
					const $body = $("<div>").addClass("card-body");
					$body.append($("<h5>").addClass("card-title").text(__("Download")));
					$body.append(
						$("<p>")
							.addClass("text-muted small mb-2")
							.text(`${__("Version")}: ${data.version || "—"} · ${mb} MB`)
					);
					$body.append(
						$("<a>")
							.addClass("btn btn-primary btn-sm")
							.attr("href", data.download_url)
							.attr("download", data.filename)
							.text(`${__("Download")} ${data.filename}`)
					);
					const $hint = $("<p>").addClass("small text-muted mt-3 mb-0");
					$hint.append(document.createTextNode(`${__("After extract, run")} `));
					$hint.append($("<code>").text("Start_Omnexa_ESigning_Agent.bat"));
					$hint.append($("<br>"));
					$hint.append(document.createTextNode(`${__("Health check")}: `));
					$hint.append(
						$("<a>")
							.attr({ href: data.health_url, target: "_blank", rel: "noopener" })
							.text(data.health_url)
					);
					$body.append($hint);
					$card.append($body);
					$target.append($card);
				} else {
					const $warn = $("<div>").addClass("alert alert-warning mb-0");
					$warn.append($("<p>").addClass("mb-2").text(data.message || __("Package not available.")));
					const $p = $("<p>").addClass("small mb-0");
					$p.append(document.createTextNode(`${__("On a Windows build machine")}: `));
					$p.append($("<br>"));
					$p.append(
						$("<code>").text(
							"apps/omnexa_einvoice/omnexa_einvoice/signing_agent/build_signing_agent_exe.bat"
						)
					);
					$p.append($("<br>"));
					$p.append(document.createTextNode(`${__("Then")}: `));
					$p.append($("<code>").text("bench build --app omnexa_einvoice"));
					$warn.append($p);
					$target.append($warn);
				}
			},
		});
	}

	load_release();
};
