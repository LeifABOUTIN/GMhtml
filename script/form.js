window.onload = () => {
	const form__prise_contact = document.querySelector(".form__prise_contact")
	const radioTel = document.getElementById("pref__telephone")
	const radioEmail = document.getElementById("pref__email")
	const inputTel = document.getElementById("customer__tel")
	const inputEmail = document.getElementById("customer__email")
	const dialogForm = document.querySelector(".form__prise__contact__dialog")
	const closeDialog = document.getElementById("close__dialog")
	const imgDialog = document.getElementById("dialog__image")
	const messageDialog = document.getElementById("dialog__message")

	radioTel.addEventListener("change", (e) => {
		if (e.target.value === "on") {
			inputEmail.required = false
			inputTel.required = true
		} else {
			inputEmail.required = true
			inputTel.required = false
		}
	})
	radioEmail.addEventListener("change", (e) => {
		if (e.target.value === "on") {
			inputEmail.required = true
			inputTel.required = false
		} else {
			inputEmail.required = false
			inputTel.required = true
		}
	})
	closeDialog.addEventListener("click", () => {
		dialogForm.close()
		window.location.href = "/"
	})
	form__prise_contact.addEventListener("submit", async (e) => {
		e.preventDefault()
		const form = e.target

		const devis = form.querySelector("#demande__devis").checked

		const nom = form.querySelector("#nom").value
		const message = form.querySelector("#message").value

		const mail = form.querySelector("#customer__email").value

		const tel = form.querySelector("#customer__tel").value
		const body = {
			reason: devis === "on" ? "devis" : "infos",
			name: nom,
			message: message || undefined,

			contact: mail !== "" ? mail : tel,
		}
		console.log(body)
		try {
			const res = await fetch(
				"https://cmm7zvmefp2c65aqucfpnla6pu0zpzed.lambda-url.eu-west-3.on.aws",
				{
					method: "POST",

					headers: {
						"Content-Type": "application/json",
					},

					body: JSON.stringify(body),
				}
			)
			if (res.status === 200) {
				imgDialog.src = "../img/check.svg"
				messageDialog.textContent =
					"Nous avons bien reçu votre demande, nous vous contacterons au plus vite!"
				dialogForm.showModal()
			} else {
				imgDialog.src = "../img/error.svg"
				dialogForm.classList.add("error")
				messageDialog.textContent =
					"Il semble qu'il y est un probleme de notre coté.. réassayez plus tard.."

				dialogForm.showModal()
			}
		} catch (e) {}
	})
	console.log(mobileNavOpenBtn)
}
