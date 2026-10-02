const mobileNavOpenBtn = document.querySelector("#mobile_nav_open")
const close_mobile_nav = document.getElementById("close_mobile_nav")
const mobileNav = document.querySelector("#mobile_nav")

mobileNavOpenBtn.addEventListener("click", () => {
	mobileNav.classList.add("show")
})
// Footer legal links open their page's text in a popup (the pages still work on their own)
const legalDialog = document.createElement("dialog")
legalDialog.id = "dialog_mentions_legales"
legalDialog.addEventListener("click", (e) => {
	if (e.target === legalDialog) legalDialog.close() // click on the backdrop
})
document.body.append(legalDialog)

document.querySelectorAll(".footer-legal a").forEach((link) => {
	link.addEventListener("click", async (e) => {
		e.preventDefault()
		try {
			const res = await fetch(link.href)
			if (!res.ok) throw new Error(res.status)
			const page = new DOMParser().parseFromString(await res.text(), "text/html")
			const content = page.querySelector("article")
			// links inside the text are relative to the legal page, not the current one
			content.querySelectorAll("a[href]").forEach((a) => (a.href = new URL(a.getAttribute("href"), link.href)))

			const close = document.createElement("img")
			close.src = new URL("../img/close.svg", link.href)
			close.alt = "Fermer"
			close.addEventListener("click", () => legalDialog.close())
			const title = document.createElement("h2")
			title.textContent = link.textContent[0].toUpperCase() + link.textContent.slice(1)

			legalDialog.replaceChildren(close, title, ...content.children)
			legalDialog.showModal()
			legalDialog.scrollTop = 0
		} catch {
			window.location.href = link.href
		}
	})
})

close_mobile_nav.addEventListener("click", () => {
	mobileNav.style.left = "-100%"
	mobileNav.addEventListener(
		"transitionend",
		() => {
			mobileNav.style.left = ""
			mobileNav.classList.remove("show")
		},
		{ once: true }
	)
})
