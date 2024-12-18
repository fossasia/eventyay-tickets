const initUserSearch = () => {
    const remoteURL = document.getElementById("vars").getAttribute("remoteUrl")
    let select = document.querySelector("#id_email")
    if (!select) select = document.querySelector("#id_invite-email")
    if (!select) select = document.querySelector("#id_speaker-email")
    if (!select) return

    const choices = new Choices(select, {
        maxItemCount: 1,
        singleModeForMultiSelect: true,
        closeDropdownOnSelect: true,
        addChoices: true,
        removeItems: true,
        removeItemButton: true,
        removeItemButtonAlignLeft: true,
        searchEnabled: true,
        searchFloor: 3,
        searchResultLimit: -1,
        placeholder: true,
        placeholderValue: select.getAttribute("placeholder"),
        itemSelectText: "",
        noResultsText: "",
        noChoicesText: "",
        addItemText: "",
        removeItemLabelText: "×",
        removeItemIconText: "×",
        maxItemText: "",
    })
    select.addEventListener("search", (ev) => {
        fetch(`${remoteURL}?search=${ev.detail.value}`)
            .then((r) => r.json())
            .then((data) => {
                choices.setChoices(
                    data.results.map(
                        (item) => ({
                            value: item.email,
                            label: `${item.name} <${item.email}>`,
                            customProperties: {
                                name: item.name,
                            },
                        }),
                        "id",
                        "name",
                        true,
                    ),
                )
            })
    })
    // when an item is selected, optionally set other fields
    select.addEventListener("addItem", (ev) => {
        if (ev.detail.customProperties && ev.detail.customProperties.name) {
            let nameInput = document.querySelector("#id_name")
            if (!nameInput) nameInput = document.querySelector("#id_speaker")
            if (!nameInput) nameInput = document.querySelector("#id_speaker-name")
            if (!nameInput || nameInput.value.length) return
            nameInput.value = ev.detail.customProperties.name
        }
    })
    select.parentElement.parentElement
        .querySelector("input")
        .addEventListener("blur", (ev) => {
            unfinishedInput = ev.target.value
            if (!unfinishedInput) return
            if (select.value != unfinishedInput) {
                select.value = unfinishedInput
                choices.setChoices([
                    {
                        value: unfinishedInput,
                        label: unfinishedInput,
                        selected: true,
                    },
                ])
                ev.target.value = ""
            }
        })
}
initUserSearch()
