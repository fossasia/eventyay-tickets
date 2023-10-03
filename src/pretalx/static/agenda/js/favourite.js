let isFaved = false
let eventSlug = null
let submissionId = null

// add argument "initial" defaulting to false
const updateButton = (initial = false) => {
    const favButton = document.getElementById('fav-button')
    favButton.classList.remove('d-none')

    if (isFaved && favButton.querySelector('.fa-star').classList.contains('d-none')) {
        // Make the star rotate after appearing
        favButton.querySelector('.fa-star-o').classList.add('d-none')
        favButton.querySelector('.fa-star').classList.remove('d-none')
        if (!initial) {
            favButton.querySelector('.fa-star').classList.add('fa-spin')
            setTimeout(() => {
                favButton.querySelector('.fa-star').classList.remove('fa-spin')
            }, 400)
        }
    } else if (!isFaved && favButton.querySelector('.fa-star-o').classList.contains('d-none')) {
        favButton.querySelector('.fa-star').classList.add('d-none')
        favButton.querySelector('.fa-star-o').classList.remove('d-none')
        if (!initial) {
            favButton.querySelector('.fa-star-o').classList.add('fa-spin')
            setTimeout(() => {
                favButton.querySelector('.fa-star-o').classList.remove('fa-spin')
            }, 400)
        }
    }
}

const loadFavs = () => {
    const data = localStorage.getItem(`${eventSlug}_favs`)
    let favs = []
	if (data) {
		try {
            favs = JSON.parse(data)
		} catch {
			localStorage.setItem(`${eventSlug}_favs`, '[]')
		}
	}
    return favs
}

const loadIsFaved = () => {
    return loadFavs().includes(submissionId)
}

const saveIsFaved = () => {
    let favs = loadFavs()
    if (isFaved && !favs.includes(submissionId)) {
        favs.push(submissionId)
    } else if (!isFaved && favs.includes(submissionId)) {
        favs = favs.filter(id => id !== submissionId)
    }
    localStorage.setItem(`${eventSlug}_favs`, JSON.stringify(favs))
}

const toggleFavs = () => {
    isFaved = loadIsFaved()
    isFaved = !isFaved
    saveIsFaved()
    updateButton()
}

document.addEventListener('DOMContentLoaded', () => {
    const favButton = document.getElementById('fav-button')
    favButton.addEventListener('click', toggleFavs)

    eventSlug = window.location.pathname.split('/')[1]
    submissionId = window.location.pathname.split('/')[3]

    isFaved = loadIsFaved()
    updateButton(true)
})
