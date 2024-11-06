document
    .querySelector("button#generate-widget")
    .addEventListener("click", (event) => {
        document.querySelector("#widget-generation").classList.add("d-none")
        document.querySelector("#generated-widget").classList.remove("d-none")
        const secondPre = document.querySelector("pre#widget-body")
        secondPre.innerHTML = secondPre.innerHTML.replace(
            "LOCALE",
            document.querySelector("#id_locale").value,
        )
        secondPre.innerHTML = secondPre.innerHTML.replace(
            "FORMAT",
            document.querySelector("#id_schedule_display").value,
        )
        const days = Array.from(document.querySelector("#id_days").querySelectorAll("option:checked"),e=>e.value)
        if (days.length) {
            secondPre.innerHTML = secondPre.innerHTML.replace(
                "FILTER_DAYS",
                ` filter-days="${days.join(",")}"`
            )
        } else {
            secondPre.innerHTML = secondPre.innerHTML.replace(
                "FILTER_DAYS",
                ""
            )
        }
    })
