window.onload = () => {
	const body = document.querySelector("body")
	const div = document.createElement("div")
	div.classList = "popup__wrapper"
	const p = document.createElement("p")
	p.innerText = "Permanence décès"
	const p2 = document.createElement("p")
	p2.innerText = "7j/7 - 24h/24"
	const a1 = document.createElement("p")
	a1.innerText = "06.73.62.31.60"

	const a2 = document.createElement("p")
	a2.innerText = "06.45.66.50.02"

	div.append(p, p2, a1, a2)
	body.append(div)
	setTimeout(() => {
		div.classList.add("animate")
	}, 1000)
}
