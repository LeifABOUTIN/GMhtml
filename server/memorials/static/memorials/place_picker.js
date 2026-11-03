// Ceremony steps in the admin: picking a saved place fills "lieu" and "adresse" (they stay editable).
// The place field is a search box (select2), which only fires jQuery events, hence django.jQuery.
django.jQuery(document).on("change", 'select[name$="-saved_place"]', function () {
	const option = this.selectedOptions[0]
	if (!option || !option.value) return
	// the label is "lieu – adresse" (Place.__str__)
	const label = option.text
	const i = label.indexOf(" – ")
	const [name, address] = i < 0 ? ["", label] : [label.slice(0, i), label.slice(i + 3)]
	const prefix = this.name.replace(/saved_place$/, "")
	this.form.elements[prefix + "place"].value = name
	this.form.elements[prefix + "address"].value = address
})
