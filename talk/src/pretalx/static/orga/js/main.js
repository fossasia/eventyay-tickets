const handleFeaturedChange = (element) => {
    const resetStatus = () => {
        statusWrapper.querySelectorAll("i").forEach((element) => {
            element.classList.add("d-none")
        })
    }
    const setStatus = (statusName) => {
        resetStatus()
        statusWrapper.querySelector("." + statusName).classList.remove("d-none")
        setTimeout(resetStatus, 3000)
    }
    const fail = () => {
        element.checked = !element.checked
        setStatus("fail")
    }

    const id = element.dataset.id
    const statusWrapper = element.parentElement.parentElement
    setStatus("working")

    const url = window.location.pathname + id + "/toggle_featured"
    const options = {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("pretalx_csrftoken"),
        },
        credentials: "include",
    }

    fetch(url, options)
        .then((response) => {
            if (response.status === 200) {
                setStatus("done")
            } else {
                fail()
            }
        })
        .catch((error) => fail())
}

const initScrollPosition = () => {
    document.querySelectorAll(".keep-scroll-position").forEach((el) => {
        el.addEventListener("click", () => {
            sessionStorage.setItem("scroll-position", window.scrollY)
        })
    })
    const oldScrollY = sessionStorage.getItem("scroll-position")
    if (oldScrollY) {
        window.scroll(window.scrollX, Math.max(oldScrollY, window.innerHeight))
        sessionStorage.removeItem("scroll-position")
    }
}

const getCookie = (name) => {
    let cookieValue = null
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";")
        for (var i = 0; i < cookies.length; i++) {
            let cookie = cookies[i].trim()
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === name + "=") {
                cookieValue = decodeURIComponent(
                    cookie.substring(name.length + 1),
                )
                break
            }
        }
    }
    return cookieValue
}

onReady(() => {
    initScrollPosition()
    document
        .querySelectorAll("input.submission_featured")
        .forEach((element) =>
            element.addEventListener("change", () =>
                handleFeaturedChange(element),
            ),
        )
})
