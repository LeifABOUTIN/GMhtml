// Ceremony steps in the admin: picking a saved place (by its title) fills "lieu" and "adresse".
// They stay editable. The place field is a search box (select2), which only fires jQuery events.
django.jQuery(document).on("change", 'select[name$="-saved_place"]', async function () {
	if (!this.value) return
	const res = await fetch(`/admin/memorials/place/${this.value}/json/`)
	if (!res.ok) return
	const place = await res.json()
	const prefix = this.name.replace(/saved_place$/, "")
	this.form.elements[prefix + "place"].value = place.name
	this.form.elements[prefix + "address"].value = place.address
})
