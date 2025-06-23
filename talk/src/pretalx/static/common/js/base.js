/* This file will be loaded on all pretalx pages.
 * It will be loaded before all other scripts. */

/* This function makes sure a given function is run after the DOM is fully loaded. */
const onReady = (fn) => {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", fn)
    } else {
        fn()
    }
}
