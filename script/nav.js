// Mobile menu
const siteHeader = document.querySelector(".site-header")
const navToggle = document.querySelector(".nav-toggle")

navToggle.addEventListener("click", () => {
	const open = siteHeader.classList.toggle("nav-open")
	navToggle.setAttribute("aria-expanded", open)
	navToggle.querySelector("img").src = open ? navToggle.dataset.close : navToggle.dataset.open
	navToggle.querySelector("img").alt = open ? "Fermer le menu" : "Menu"
})

// Legal links open their page's text in a popup (the pages also work on their own)
const legalDialog = document.createElement("dialog")
legalDialog.id = "legal-dialog"
legalDialog.addEventListener("click", (e) => {
	if (e.target === legalDialog) legalDialog.close() // click on the backdrop
})
document.body.append(legalDialog)

document.querySelectorAll(".legal-link").forEach((link) => {
	link.addEventListener("click", async (e) => {
		e.preventDefault()
		try {
			const res = await fetch(link.href)
			if (!res.ok) throw new Error(res.status)
			const page = new DOMParser().parseFromString(await res.text(), "text/html")
			const content = page.querySelector(".prose")
			// links inside the text are relative to the legal page, not the current one
			content.querySelectorAll("a[href]").forEach((a) => (a.href = new URL(a.getAttribute("href"), link.href)))

			const head = document.createElement("div")
			head.className = "legal-dialog__head"
			const title = document.createElement("h2")
			title.textContent = link.textContent
			const close = document.createElement("button")
			close.type = "button"
			const closeImg = document.createElement("img")
			closeImg.src = new URL("../img/close.svg", link.href)
			closeImg.alt = "Fermer"
			close.append(closeImg)
			close.addEventListener("click", () => legalDialog.close())
			head.append(title, close)

			legalDialog.replaceChildren(head, content)
			legalDialog.showModal()
			legalDialog.scrollTop = 0
		} catch {
			window.location.href = link.href
		}
	})
})
