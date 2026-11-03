// Compositions page: a photo opens larger in a viewer instead of leaving the page
window.addEventListener("DOMContentLoaded", () => {
	const viewer = document.querySelector(".compo__viewer")
	const img = viewer.querySelector("img")
	document.querySelectorAll(".compo__photo").forEach((link) =>
		link.addEventListener("click", (e) => {
			e.preventDefault()
			img.src = link.href
			img.alt = link.querySelector("img").alt
			viewer.showModal()
		})
	)
	viewer.addEventListener("click", () => viewer.close()) // a click anywhere closes it
})
