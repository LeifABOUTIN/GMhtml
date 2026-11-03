// Mobile menu
const siteHeader = document.querySelector(".site-header")
const navToggle = document.querySelector(".nav-toggle")

function setMenu(open) {
	siteHeader.classList.toggle("nav-open", open)
	navToggle.setAttribute("aria-expanded", open)
	navToggle.querySelector("img").src = open ? navToggle.dataset.close : navToggle.dataset.open
	navToggle.querySelector("img").alt = open ? "Fermer le menu" : "Menu"
}

navToggle.addEventListener("click", () => setMenu(!siteHeader.classList.contains("nav-open")))

// a click or tap anywhere outside the header, or the Escape key, closes the menu
document.addEventListener("click", (e) => {
	if (siteHeader.classList.contains("nav-open") && !siteHeader.contains(e.target)) setMenu(false)
})
document.addEventListener("keydown", (e) => {
	if (e.key === "Escape" && siteHeader.classList.contains("nav-open")) setMenu(false)
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

// "Cérémonie et itinéraires" on a notice: slides open and closed instead of jumping
document.querySelectorAll("details.memorial__ceremony").forEach((details) => {
	const summary = details.querySelector("summary")
	let running = null
	summary.addEventListener("click", (e) => {
		if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
		e.preventDefault()
		const start = details.getBoundingClientRect().height
		const opening = !details.open || running?.closing
		running?.animation.cancel()
		details.open = true
		const style = getComputedStyle(details)
		const end = opening
			? details.getBoundingClientRect().height
			: summary.getBoundingClientRect().height + parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
				+ parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth)
		details.style.overflow = "hidden"
		const animation = details.animate({ height: [`${start}px`, `${end}px`] }, { duration: 280, easing: "ease-out" })
		running = { animation, closing: !opening }
		animation.onfinish = () => {
			details.open = opening
			details.style.overflow = ""
			running = null
		}
	})
})
