// Ceremony steps in the admin: picking a saved place fills "lieu" and "adresse" (they stay editable)
document.addEventListener("change", (e) => {
	const select = e.target
	if (!select.matches?.('select[name$="-saved_place"]')) return
	const option = select.selectedOptions[0]
	if (!option || !option.value) return
	let name = option.dataset.name
	let address = option.dataset.address
	if (address === undefined) {
		// a place just added with the "+" button has no data: its label is "lieu – adresse"
		const i = option.text.lastIndexOf(" – ")
		;[name, address] = i < 0 ? ["", option.text] : [option.text.slice(0, i), option.text.slice(i + 3)]
	}
	const prefix = select.name.replace(/saved_place$/, "")
	const form = select.form
	form.elements[prefix + "place"].value = name
	form.elements[prefix + "address"].value = address
})
