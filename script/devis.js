// Quote forms (pages/devis-obseques.html, pages/devis-marbrerie.html): steps, then e-mailed by server/contact
window.addEventListener("DOMContentLoaded", () => {
	const form = document.querySelector(".quote")
	const steps = [...form.querySelectorAll(".quote__step")]
	const bar = form.querySelector(".quote__progress-bar")
	const label = form.querySelector(".quote__progress-label")
	const dialog = document.querySelector(".form__prise__contact__dialog")
	const dialogImg = document.getElementById("dialog__image")
	const dialogMsg = document.getElementById("dialog__message")
	const email = document.getElementById("customer__email")
	const tel = document.getElementById("customer__tel")
	let current = 0

	function show(i) {
		current = i
		steps.forEach((s, n) => (s.hidden = n !== i))
		bar.style.width = `${((i + 1) / steps.length) * 100}%`
		label.textContent = `Étape ${i + 1} sur ${steps.length} – ${steps[i].dataset.title}`
		form.scrollIntoView({ behavior: "smooth", block: "start" })
	}

	// only the step on screen is checked before going on
	function stepIsValid() {
		const fields = [...steps[current].querySelectorAll("input, textarea, select")]
		return fields.every((f) => f.disabled || f.reportValidity())
	}

	form.querySelectorAll("[data-next]").forEach((b) =>
		b.addEventListener("click", () => stepIsValid() && show(current + 1))
	)
	form.querySelectorAll("[data-back]").forEach((b) => b.addEventListener("click", () => show(current - 1)))

	// e-mail or phone, as on the contact page
	form.querySelectorAll('input[name="preference"]').forEach((r) =>
		r.addEventListener("change", () => {
			const byMail = document.getElementById("pref__email").checked
			email.required = byMail
			email.disabled = !byMail
			tel.required = !byMail
			tel.disabled = byMail
		})
	)
	email.disabled = tel.disabled = true

	// same rule as server/contact/views.py: a full French number, or an international one
	tel.addEventListener("input", () => {
		const complete = /^(0[1-9]\d{8}|(\+|00)330?\d{9}|(\+|00)(?!33)\d{8,15})$/.test(tel.value.replace(/[ .()-]/g, ""))
		tel.setCustomValidity(!tel.value || complete ? "" : "Indiquez votre numéro complet, par exemple 06 12 34 56 78.")
	})

	document.getElementById("close__dialog").addEventListener("click", () => {
		dialog.close()
		if (!dialog.classList.contains("error")) window.location.href = "/"
	})

	form.addEventListener("submit", async (e) => {
		e.preventDefault()
		if (!stepIsValid()) return
		const data = new FormData(form)
		const body = { kind: form.dataset.kind, extras: data.getAll("extras") }
		for (const [k, v] of data) if (k !== "extras" && k !== "preference") body[k] = v
		body.contact = email.disabled ? tel.value : email.value
		delete body.email
		delete body.telephone

		const button = form.querySelector("[type=submit]")
		button.disabled = true
		let ok = false
		try {
			const res = await fetch("/contact/devis/", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(body),
			})
			ok = res.status === 200
		} catch (err) {}
		button.disabled = false
		dialog.classList.toggle("error", !ok)
		dialogImg.src = ok ? "../img/check.svg" : "../img/error.svg"
		dialogMsg.textContent = ok
			? "Merci, votre demande de devis est bien envoyée. Nous vous rappelons au plus vite."
			: "Votre demande n'a pas pu être envoyée. Merci de réessayer ou de nous appeler au 01 39 89 17 88."
		dialog.showModal()
	})

	show(0)
})
