console.log(qtf_results)

function getOdyseeURL(lbryURL) {
	return lbryURL.replace("lbry://", "https://odysee.com/").replaceAll("#", ":");
}

function toggleNextRow(row) {
	row.nextElementSibling.hidden = !row.nextElementSibling.hidden;
}

function main() {
	let main_div = document.querySelector("#main_div");

	let main_table = document.createElement("table");
	main_table.id = "results_table";
	let header_texts = [
		"Proposal URL",
		"Channel",
		"Contributors",
		"Contributed",
		"Matched",
	];

	//Create headers
	let tr = document.createElement("tr");
	tr.classList.add("header_row");
	header_texts.forEach((item) => {
		let th = document.createElement("th");
		th.innerHTML = item;
		tr.append(th);
	});
	main_table.append(tr);

	//Fill table
	qtf_results.proposals.forEach((proposal) => {
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
	main_div.append(main_table);


	//Make round details table
	
	let round_details_table = document.createElement("table");
	round_details_table.id = "round_details_table";
	tr = document.createElement("tr");
	tr.innerHTML = `
		<th colspan="100%">Round details</th>
	`;
	round_details_table.append(tr);
	for (const [key, value] of Object.entries(qtf_results)) {
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
			for (const [kez, value] of Object.entries(qtf_results[key])) {
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
	main_div.append(hr);
	main_div.append(round_details_table);


	//Fill list with round details
//	let ul = document.querySelector("ul");
//	for (const [key, value] of Object.entries(qtf_results)) {
//		if ( typeof(value) != 'object'  ) {
//			let text = key.replaceAll("_", " ");
//			text = text[0].toUpperCase() + text.substring(1);
//			let li = document.createElement("li");
//			li.innerHTML = `${text}: ${value}`;
//			ul.append(li);
//		  console.log(`${text}: ${value}`);
//		} else if (key == "round_details") {
//			for (const [kez, value] of Object.entries(qtf_results[key])) {
//			let text = kez.replaceAll("_", " ");
//			text = text[0].toUpperCase() + text.substring(1);
//			let li = document.createElement("li");
//			li.innerHTML = `${text}: ${value}`;
//			ul.append(li);
//		  console.log(`${text}: ${value}`);
//			}
//		}
//	}

}


window.onload = main;
