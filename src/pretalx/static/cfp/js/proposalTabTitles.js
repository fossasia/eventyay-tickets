const titleParts = document.title.split("::");

function updateTitle(newTitle) {
    if (newTitle === "") {
        document.title = titleParts.join("::");
    } else {
        document.title = `${newTitle} ::${titleParts[1]}::${titleParts[2]}`;
    }
}

function checkForTitle() {
    const titleInput = document.getElementById("id_title").value;
    updateTitle(titleInput);
}

function titleChangeHandler(event) {
    const newTitle = event.target.value;
    updateTitle(newTitle);
}

if (titleParts.length !== 3) {
    console.error(
        "Could not parse site title while adding proposal title change listener."
    );
} else {
    document.addEventListener("DOMContentLoaded", checkForTitle);
    document
        .getElementById("id_title")
        .addEventListener("change", titleChangeHandler);
}
