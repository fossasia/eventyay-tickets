/* Makes a table sortable by drag and drop, sending the new state to the server.
 * This implementation is hugely indebted to Julik Tarkhanov and his blog post at
 * https://blog.julik.nl/2022/10/drag-reordering */

const DIRECTION_HORIZONTAL = Symbol();
const DIRECTION_VERTICAL = Symbol();
const INTENT_BEFORE = Symbol();
const INTENT_AFTER = Symbol();

const computeCentroid = (element) => {
    const rect = element.getBoundingClientRect();
    const viewportX = (rect.left + rect.right) / 2;
    const viewportY = (rect.top + rect.bottom) / 2;
    return { x: viewportX + window.scrollX, y: viewportY + window.scrollY };
};

const getSortableElements = (parentElement) => {
    return Array.from(parentElement.querySelectorAll("[dragsort-id]")).map(
        (el) => {
            return { element: el, centroid: computeCentroid(el) };
        },
    );
};

const predictDirection = (a, b) => {
    if (!a || !b) return DIRECTION_HORIZONTAL;
    const dx = Math.abs(b.centroid.x - a.centroid.x);
    const dy = Math.abs(b.centroid.y - a.centroid.y);
    return dx > dy ? DIRECTION_HORIZONTAL : DIRECTION_VERTICAL;
};

const intentFrom = (direction, evt, centroid) => {
    if (direction === DIRECTION_HORIZONTAL) {
        return evt.clientX + window.scrollX < centroid.x
            ? INTENT_BEFORE
            : INTENT_AFTER;
    } else {
        return evt.clientY + window.scrollY < centroid.y
            ? INTENT_BEFORE
            : INTENT_AFTER;
    }
};

const pageDistanceBetweenPointerAndCentroid = (evt, centroid) => {
    return Math.hypot(
        centroid.x - (evt.clientX + window.scrollX),
        centroid.y - (evt.clientY + window.scrollY),
    );
};

const unstyleDragIndicators = (parentElement) => {
    parentElement.parentElement
        .querySelectorAll(".drag-indicator")
        .forEach((el) =>
            el.classList.remove(
                "insert-before",
                "insert-after",
                "drag-indicator",
            ),
        );
};

const dragStart = (el) => {
    const parentElement = el.closest("[dragsort-url]");

    const sortableElements = getSortableElements(parentElement);
    const listDirection = predictDirection(...sortableElements);
    const isTable = parentElement.tagName === "TBODY";

    let closest = el;
    let intent = INTENT_BEFORE;

    const dragoverHandler = (evt) => {
        evt.preventDefault();

        const byProximity = sortableElements
            .map((pe) => {
                return {
                    d: pageDistanceBetweenPointerAndCentroid(evt, pe.centroid),
                    ...pe,
                };
            })
            .sort((a, b) => a.d - b.d);
        const { element, centroid } = byProximity[0];

        closest = byProximity[0].element;
        intent = intentFrom(listDirection, evt, byProximity[0].centroid);

        unstyleDragIndicators(parentElement);
        if (intent === INTENT_BEFORE) {
            element.classList.add("drag-indicator", "insert-before");
            if (!element.previousElementSibling && isTable) {
                // First table row, got to add the class to the th row instead
                element.parentElement.parentElement
                    .querySelector("thead")
                    .classList.add("drag-indicator", "insert-after");
            }
        } else {
            element.classList.add("drag-indicator", "insert-after");
        }
    };

    parentElement.addEventListener("dragover", dragoverHandler);
    const stopDragging = () => {
        unstyleDragIndicators(parentElement);
        parentElement.removeEventListener("dragover", dragoverHandler);
        return { closest, intent };
    };
    return stopDragging;
};

const pushOrder = (parentElement) => {
    const url = parentElement.getAttribute("dragsort-url");
    const data = new URLSearchParams();
    const ids = Array.from(parentElement.querySelectorAll("[dragsort-id]")).map(
        (el) => el.getAttribute("dragsort-id"),
    );
    data.append("order", ids.join(","));
    fetch(url, {
        method: "POST",
        headers: {
            "X-CSRFToken": document.cookie
                .split("pretalx_csrftoken=")
                .pop()
                .split(";")
                .shift(),
        },
        body: data,
    });
};

onReady(() =>
    document.querySelectorAll("[dragsort-id]").forEach((el) => {
        el.querySelector(".dragsort-button").addEventListener(
            "dragstart",
            (evt) => {
                // Changing the element’s class in the dragstart handler will immediately
                // fire the dragend handler in Chrome, for cursed reasons, so we do it
                // outside the event.
                setTimeout(() => el.classList.add("dragging"), 0);
                setTimeout(() => document.querySelector("body").classList.add("dragging"), 0);
                const stop = dragStart(evt.target);
                el.parentElement.addEventListener(
                    "drop",
                    (evt) => evt.preventDefault(),
                    {
                        once: true,
                    },
                );
                document.addEventListener(
                    "dragend",
                    (evt) => {
                        evt.preventDefault();
                        el.classList.remove("dragging");
                        document
                            .querySelector("body")
                            .classList.remove("dragging");
                        const { closest, intent } = stop();
                        if (intent === INTENT_AFTER) {
                            closest.insertAdjacentElement("afterend", el);
                        } else {
                            closest.insertAdjacentElement("beforebegin", el);
                        }
                        pushOrder(el.parentElement);
                    },
                    { once: true },
                );
            },
        );
    }),
);
