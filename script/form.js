// Contact page (pages/contact.html): checked here, then e-mailed by the site's server (server/contact).
// The script is deferred, so this runs once the page is read, without waiting for its images: until it runs,
// sending the form would just reload the page.
;(() => {
	const form = document.querySelector(".form__prise_contact")
	const radioEmail = document.getElementById("pref__email")
	const radioTel = document.getElementById("pref__telephone")
	const inputEmail = document.getElementById("customer__email")
	const inputTel = document.getElementById("customer__tel")
	const submit = form.querySelector(".submit__form")
	const dialogForm = document.querySelector(".form__prise__contact__dialog")
	const closeDialog = document.getElementById("close__dialog")
	const imgDialog = document.getElementById("dialog__image")
	const messageDialog = document.getElementById("dialog__message")
	const PHONE_NUMBER = "01 39 89 17 88"

	// same rule as server/contact/views.py: a full French number, or an international one
	const phoneIsComplete = (value) => /^(0[1-9]\d{8}|(\+|00)330?\d{9}|(\+|00)(?!33)\d{8,15})$/.test(value.replace(/[ .()-]/g, ""))

	function checkPhone() {
		const wrong = !inputTel.disabled && inputTel.value && !phoneIsComplete(inputTel.value)
		inputTel.setCustomValidity(wrong ? "Indiquez votre numéro complet, par exemple 06 12 34 56 78." : "")
	}

	// the field not on screen is disabled: the browser cannot point at a hidden field to explain a problem
	function showChosenField() {
		const byEmail = radioEmail.checked
		inputEmail.disabled = !byEmail
		inputEmail.required = byEmail
		inputTel.disabled = byEmail
		inputTel.required = !byEmail
		checkPhone()
	}

	radioEmail.addEventListener("change", showChosenField)
	radioTel.addEventListener("change", showChosenField)
	inputTel.addEventListener("input", checkPhone)
	showChosenField()

	closeDialog.addEventListener("click", () => {
		dialogForm.close()
		// after a failure the visitor stays here, with what they wrote, to try again
		if (!dialogForm.classList.contains("error")) window.location.href = "/"
	})

	form.addEventListener("submit", async (e) => {
		e.preventDefault()
		if (submit.disabled) return // already sending
		const body = {
			reason: form.querySelector("#demande__devis").checked ? "devis" : "infos",
			name: form.querySelector("#nom").value,
			message: form.querySelector("#message").value || undefined,
			contact: radioEmail.checked ? inputEmail.value : inputTel.value,
			website: form.querySelector("#website").value,
		}
		const label = submit.textContent
		submit.disabled = true
		submit.textContent = "Envoi en cours…"
		let status = 0
		try {
			// saved by the site's server (server/contact), which also notifies the agency by e-mail
			const res = await fetch("/contact/envoyer/", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify(body),
			})
			status = res.status
		} catch (err) {}
		submit.disabled = false
		submit.textContent = label

		const ok = status === 200
		dialogForm.classList.toggle("error", !ok)
		imgDialog.src = ok ? "../img/check.svg" : "../img/error.svg"
		if (ok) {
			messageDialog.textContent = "Nous avons bien reçu votre demande, nous vous contacterons au plus vite !"
			form.reset()
			showChosenField()
		} else if (status === 429) {
			messageDialog.textContent = `Plusieurs demandes viennent d'être envoyées. Merci de réessayer dans quelques minutes ou de nous appeler au ${PHONE_NUMBER}.`
		} else {
			messageDialog.textContent = `Votre demande n'a pas pu être envoyée. Merci de réessayer ou de nous appeler au ${PHONE_NUMBER}.`
		}
		dialogForm.showModal()
	})
})()
