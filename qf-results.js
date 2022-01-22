console.log(qf_results)

const downArrow = "&#8595;";
const upArrow = "&#8593;";

function getOdyseeURL(lbryURL) {
	return lbryURL.replace("lbry://", "https://odysee.com/").replaceAll("#", ":");
}

function toggleNextRow(row) {
	row.nextElementSibling.hidden = !row.nextElementSibling.hidden;
}

function orderBy(item) {
	if ( item == "Proposal" || item == "Channel")
		return;

	item = item.replace(upArrow, "").replace(downArrow, "");

	const sortOnKey = (key, string, desc) => {
			console.log("Is desc: ", desc);
		  const caseInsensitive = string && string === "CI";
		  return (a, b) => {
				    a = caseInsensitive ? a[key].toLowerCase() : a[key];
				    b = caseInsensitive ? b[key].toLowerCase() : b[key];
				    if (string) {
							      return desc ? b.localeCompare(a) : a.localeCompare(b);
							    }
				    return desc ? b - a : a - b;
				  }
	};

	let key = "";
	let isDesc = item == qf_results.orderd_by? !qf_results.order_is_descending : true;
	if (item == "Contributors")
		key = "contributor_count";
	else if (item == "Contributed")
		key = "funded_amount";
	else if (item == "Matched")
		key = "matched_amount";


	qf_results.orderd_by = item;
	qf_results.order_is_descending = isDesc;
	qf_results.proposals.sort(sortOnKey(key, false, isDesc));
	createResultsTables();
}

function createResultsTables() {
	let table_div = document.querySelector("#table_div");
	table_div.innerHTML = "";

	let main_table = document.createElement("table");
	main_table.id = "results_table";
	let header_texts = [
		"Proposal",
		"Channel",
		"Contributors",
		"Contributed",
		"Matched",
	];

	for (let i = 0; i < header_texts.length; i++) {
		if (qf_results.orderd_by == null) {
			qf_results.orderd_by = "Matched";
			qf_results.order_is_descending = true;
		}
		console.log(qf_results.orderd_by);
		if (qf_results.orderd_by.match(header_texts[i].substr(0, header_texts[i].length - 1)))
			header_texts[i] += qf_results.order_is_descending ? downArrow : upArrow;
	};

	//Create headers
	let tr = document.createElement("tr");
	tr.classList.add("header_row");
	header_texts.forEach((item) => {
		let th = document.createElement("th");
		th.innerHTML = item;
		th.onclick = () => orderBy(item);
		tr.append(th);
	});
	main_table.append(tr);

	//Fill table
	qf_results.proposals.forEach((proposal) => {
		let tr = document.createElement("tr");
		tr.classList.add("proposal-row");
		tr.innerHTML = `
		<td><a href="${getOdyseeURL(proposal.claim.permanent_url)}">${proposal.claim.value.title}</a></td>
		<td><a href="${getOdyseeURL(proposal.claim.signing_channel.permanent_url)}">${proposal.claim.signing_channel.name}</a></td>
		<td>${proposal.contributors.length}</td>
		<td>${proposal.accepted_amount.toFixed(2)} (${proposal.funded_amount.toFixed(2)}) LBC</td>
		<td>${proposal.matched_amount.toFixed(2)} LBC</td>
		`;
		tr.onclick = () => toggleNextRow(tr);
		main_table.append(tr);

		// Store for sorting
		proposal["contributor_count"] = proposal.contributors.length;

		// Fill supports
		let tr2 = document.createElement("tr");
		let td = document.createElement("td");
		let contributions_table = document.createElement("table");
		contributions_table.classList.add("tips-table");
		proposal.contributors.forEach((contributor) => {
			let tr = document.createElement("tr");
			tr.innerHTML = `
			<td><a href="${getOdyseeURL(contributor.channel_claim.permanent_url)}">${contributor.channel_claim.name}</a></td>
			<td>${contributor.accepted_amount.toFixed(2)} (${contributor.tip_amount.toFixed(2)}) LBC</td>
			`;
			tr.onclick = () => toggleNextRow(tr);
			contributions_table.append(tr);

			// Fill separate tips
			let tr2 = document.createElement("tr");
			let td = document.createElement("td");
			let tips_table = document.createElement("table");
			contributor.tips.forEach((tip) => {
				let tr = document.createElement("tr");
				tr.innerHTML = `
					<td><a href="https://explorer.lbry.com/tx/${tip.txid}">${tip.amount.toFixed(2)}</a></td>
				`;
			tips_table.append(tr);
			});

			td.append(tips_table);
			td.colSpan = header_texts.length;
			tr2.append(td);
			tr2.hidden = true;
			contributions_table.append(tr2);

		});

		let tr3 = document.createElement("tr");
		tr3.innerHTML = `<td colspan="100%"; style="text-align:center">Invalid supports</td>`;
		tr3.classList.add("invalid-supports-title-row");
		tr3.onclick = () => toggleNextRow(tr3);
		contributions_table.append(tr3);

		//Fill invalid supports
		let tr4 = document.createElement("tr");		
		let td2 = document.createElement("td");
		let invalid_table = document.createElement("table");
		proposal.invalid_supports.forEach((support) => {
			if (support.reason == "View-reward")
				return;
			let tr = document.createElement("tr");
			tr.innerHTML = `
				<td><a href="https://explorer.lbry.com/tx/${support.txid}">${parseFloat(support.amount).toFixed(2)}</a></td>
				<td>${support.reason}</td>
			`;
			invalid_table.append(tr);
		});

		td2.append(invalid_table);
		td2.colSpan = header_texts.length;
		tr4.append(td2);
		tr4.hidden = true;
		contributions_table.append(tr4);

		td.append(contributions_table);
		td.colSpan = header_texts.length;
		tr2.append(td);
		tr2.hidden = true;
		main_table.append(tr2);
		

	});
	table_div.append(main_table);


	//Make round details table
	
	let round_details_table = document.createElement("table");
	round_details_table.id = "round_details_table";
	tr = document.createElement("tr");
	tr.innerHTML = `
		<th colspan="100%">Round details</th>
	`;
	round_details_table.append(tr);
	for (const [key, value] of Object.entries(qf_results)) {
		if (key == "orderd_by" || key == "order_is_descending")
			continue;
		if ( typeof(value) != 'object'  ) {
			let text = key.replaceAll("_", " ");
			text = text[0].toUpperCase() + text.substring(1);
			let tr = document.createElement("tr");
			tr.innerHTML = `
				<td>${text}</td>
				<td>${value}</td>
			`;
			round_details_table.append(tr);
		  console.log(`${text}: ${value}`);
		} else if (key == "round_details") {
			for (const [kez, value] of Object.entries(qf_results[key])) {
			let text = kez.replaceAll("_", " ");
			text = text[0].toUpperCase() + text.substring(1);
			let tr = document.createElement("tr");
			tr.innerHTML = `
				<td>${text}</td>
				<td>${value}</td>
			`;
			round_details_table.append(tr);
		  console.log(`${text}: ${value}`);
			}
		}
	}
	let hr = document.createElement("hr");
	table_div.append(hr);
	table_div.append(round_details_table);
}


function main() {

	createResultsTables();

	// Make wtfisqf url
	let wtf_url = "https://wtfisqf.com/?";
	qf_results.proposals.forEach((proposal) => { 
		wtf_url += "grant=";
		proposal.contributors.forEach((contributor) => {
			wtf_url += contributor.tip_amount.toString();
			if (proposal.contributors.indexOf(contributor) < (proposal.contributors.length - 1))
				wtf_url += ",";
		});
		wtf_url += "&";
	});
	wtf_url += `match=${qf_results.round_details.LBC_pool}`;

	document.querySelector("#wtfisqf_link").href = wtf_url;



}


window.onload = main;
