onReady(() => {
    document
        .querySelector("#direction select")
        .addEventListener("change", (e) => {
            e.target.form.submit()
        })
})
