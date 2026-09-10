const globalData = document.getElementById("global-data")
const statsRoot = document.getElementById("stats")
let dataMapping = {}
let searchUrl = ""

const TOTAL_LABEL = (statsRoot && (statsRoot.dataset.labelTotal || statsRoot.dataset.totalLabel)) || "Total"
const L_TOTAL_SESSIONS = (statsRoot && statsRoot.dataset.labelTotalSessions) || "Total sessions"
const L_PEAK_DAY = (statsRoot && statsRoot.dataset.labelPeakDay) || "Peak day"
const L_ACCEPTED_RATE = (statsRoot && statsRoot.dataset.labelAcceptedRate) || "Accepted rate"
const L_TOP_TYPE = (statsRoot && statsRoot.dataset.labelTopType) || "Top type"
const L_TOTAL_TYPES = (statsRoot && statsRoot.dataset.labelTotalTypes) || "Total types"
const L_NAME = (statsRoot && statsRoot.dataset.labelName) || "Name"
const L_COUNT = (statsRoot && statsRoot.dataset.labelCount) || "Count"
const L_NO_DATA = (statsRoot && statsRoot.dataset.labelNoData) || "No data for this status"
const L_SCHEDULED = (statsRoot && statsRoot.dataset.labelScheduled) || "Scheduled"
const L_UNSCHEDULED = (statsRoot && statsRoot.dataset.labelUnscheduled) || "Unscheduled"
const L_ACCEPTED = (statsRoot && statsRoot.dataset.labelAccepted) || "Accepted"
const L_NOT_ACCEPTED = (statsRoot && statsRoot.dataset.labelNotAccepted) || "Not accepted"
const L_SESSIONS = (statsRoot && statsRoot.dataset.labelSessions) || "Sessions"
const L_NO_TRACK = (statsRoot && statsRoot.dataset.labelNoTrack) || "No track"
const L_SELECTED = (statsRoot && statsRoot.dataset.labelSelected) || "selected"

/** Parse YYYY-MM-DD as a local calendar date to avoid UTC day shifts. */
const parseCalendarDate = (value) => {
    if (typeof value === "number") return value
    if (typeof value !== "string") return new Date(value).getTime()
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
    if (match) {
        return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3])).getTime()
    }
    return new Date(value).getTime()
}

try {
    if (globalData && globalData.dataset.mapping) {
        dataMapping = JSON.parse(globalData.dataset.mapping)
    }
    if (globalData && globalData.dataset.url) {
        searchUrl = globalData.dataset.url
    }
} catch (error) {
    console.error("Failed to parse analytics mapping", error)
}

const chartInstances = {
    timeline: null,
    type: null,
}

const SCOPE_COLORS = {
    all: "#2185d0",
    accepted: "#16a34a",
    not_accepted: "#ea580c",
}
const PALETTE = ["#2185d0", "#f97316", "#22c55e", "#8b5cf6", "#ef4444", "#06b6d4", "#f59e0b", "#ec4899", "#10b981", "#a78bfa"]
const MIN_STATS_ROWS = 3
const STATUS_SCOPE_CLASSES = ["is-scope-all", "is-scope-accepted", "is-scope-not-accepted"]

const clearNode = (node) => {
    if (!node) return
    while (node.firstChild) node.removeChild(node.firstChild)
}

const createEl = (tag, className, text) => {
    const node = document.createElement(tag)
    if (className) node.className = className
    if (text != null) node.textContent = String(text)
    return node
}

const safeCssColor = (value, fallback = "#94a3b8") => {
    const color = String(value || "").trim()
    if (/^#[0-9a-fA-F]{3,8}$/.test(color)) return color
    if (/^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}(?:\s*,\s*(?:0|1|0?\.\d+))?\s*\)$/.test(color)) {
        return color
    }
    return fallback
}

const createEmptyChartPlaceholder = () => {
    const empty = createEl("div", "td-analytics-empty-chart")
    empty.setAttribute("aria-hidden", "true")
    return empty
}

const renderSummaryItems = (slot, items) => {
    if (!slot) return
    clearNode(slot)
    items.forEach((item) => {
        const wrap = createEl("div", "td-ts-item")
        if (item.title) wrap.title = String(item.title)
        wrap.appendChild(createEl("div", "td-ts-label", item.label))
        wrap.appendChild(createEl("div", item.valueClass || "td-ts-value", item.value))
        slot.appendChild(wrap)
    })
    slot.classList.add("td-timeline-summary")
}

const loadPayload = () => {
    const payloadEl = document.getElementById("stats-payload")
    if (!payloadEl) return null
    try {
        return JSON.parse(payloadEl.textContent)
    } catch (error) {
        console.error("Failed to parse analytics payload", error)
        return null
    }
}

const destroyChart = (key) => {
    if (!chartInstances[key]) return
    try {
        chartInstances[key].destroy()
    } catch (error) {
        console.error("Failed to destroy analytics chart", key, error)
    }
    chartInstances[key] = null
}

const clearChartTarget = (elementId) => {
    clearNode(document.getElementById(elementId))
}

const clearSummary = (elementId) => {
    clearNode(document.querySelector(`[data-summary-for="${elementId}"]`))
}

const getMultiMenu = (multi) => {
    if (!multi) return null
    const local = multi.querySelector(".td-analytics-multi-menu")
    if (local) return local
    const key = `${multi.getAttribute("data-stats-card")}-${multi.getAttribute("data-stats-dim")}`
    return document.querySelector(`.td-analytics-multi-menu[data-stats-menu-for="${key}"]`)
}

const getCheckedOptions = (multi) => {
    const menu = getMultiMenu(multi)
    if (!menu) return []
    return Array.from(menu.querySelectorAll('input[type="checkbox"]:checked')).map((input) => ({
        value: input.value,
        label: (input.closest("label") && input.closest("label").querySelector("span")
            ? input.closest("label").querySelector("span").textContent
            : input.value).trim(),
        color: input.getAttribute("data-color") || null,
    }))
}

const getMultiValues = (multi) => getCheckedOptions(multi).map((item) => item.value)

const clearMultiValues = (multi) => {
    const menu = getMultiMenu(multi)
    if (!menu) return
    menu.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        input.checked = false
    })
}

const setMultiValues = (multi, values) => {
    const menu = getMultiMenu(multi)
    if (!menu) return
    const wanted = new Set((values || []).map(String))
    menu.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        input.checked = wanted.has(String(input.value))
    })
}

const closeAllMultiMenus = (except) => {
    document.querySelectorAll(".td-analytics-multi").forEach((multi) => {
        if (except && multi === except) return
        const menu = getMultiMenu(multi)
        const toggle = multi.querySelector(".td-analytics-multi-toggle")
        if (menu) {
            menu.hidden = true
            menu.classList.remove("is-ported")
            menu.style.removeProperty("top")
            menu.style.removeProperty("left")
            menu.style.removeProperty("min-width")
            if (menu.parentElement !== multi) multi.appendChild(menu)
        }
        if (toggle) toggle.setAttribute("aria-expanded", "false")
        multi.classList.remove("is-open")
    })
}

const positionMultiMenu = (multi, menu, toggle) => {
    const rect = toggle.getBoundingClientRect()
    const menuWidth = Math.max(rect.width, 168)
    let left = rect.left
    if (left + menuWidth > window.innerWidth - 8) {
        left = Math.max(8, window.innerWidth - menuWidth - 8)
    }
    menu.classList.add("is-ported")
    menu.hidden = false
    const estimatedHeight = Math.min(240, Math.max(menu.scrollHeight, 120))
    let top = rect.bottom + 4
    if (top + estimatedHeight > window.innerHeight - 8) {
        top = Math.max(8, rect.top - estimatedHeight - 4)
    }
    menu.style.top = `${Math.round(top)}px`
    menu.style.left = `${Math.round(left)}px`
    menu.style.minWidth = `${Math.round(menuWidth)}px`
}

const openMultiMenu = (multi) => {
    const toggle = multi.querySelector(".td-analytics-multi-toggle")
    const menu = getMultiMenu(multi)
    if (!toggle || !menu || toggle.disabled) return
    closeAllMultiMenus(multi)
    menu.setAttribute(
        "data-stats-menu-for",
        `${multi.getAttribute("data-stats-card")}-${multi.getAttribute("data-stats-dim")}`,
    )
    document.body.appendChild(menu)
    positionMultiMenu(multi, menu, toggle)
    toggle.setAttribute("aria-expanded", "true")
    multi.classList.add("is-open")
}

const styleMultiToggle = (multi) => {
    if (!multi) return
    const toggle = multi.querySelector(".td-analytics-multi-toggle")
    if (!toggle) return
    const dim = multi.getAttribute("data-stats-dim")
    const emptyLabel = multi.getAttribute("data-empty-label") || "All"
    const checked = getCheckedOptions(multi)

    let label = emptyLabel
    if (checked.length === 1) label = checked[0].label
    else if (checked.length === 2) label = `${checked[0].label}, ${checked[1].label}`
    else if (checked.length > 2) label = `${checked.length} ${L_SELECTED}`
    toggle.textContent = label
    toggle.title = checked.length ? checked.map((item) => item.label).join(", ") : emptyLabel

    if (dim === "status") {
        let scope = "all"
        if (checked.length === 1) scope = checked[0].value
        setStatusSelectClass(toggle, scope)
        toggle.style.removeProperty("--filter-accent")
        toggle.classList.remove("has-accent")
        return
    }

    if (checked.length === 1 && checked[0].color) {
        toggle.style.setProperty("--filter-accent", safeCssColor(checked[0].color, "#6d28d9"))
        toggle.classList.add("has-accent")
    } else {
        toggle.style.removeProperty("--filter-accent")
        toggle.classList.remove("has-accent")
    }
}

const normalizeExclusivePair = (values, pair) => {
    const selected = (values || []).map(String).filter((value) => pair.includes(value))
    if (selected.length >= pair.length) return []
    return selected
}

const readCardFilters = (cardName) => {
    const root = document.querySelector(`[data-stats-filters="${cardName}"]`)
    if (!root) {
        return { statuses: [], trackIds: [], tagIds: [], schedules: [] }
    }
    const statusEl = root.querySelector('[data-stats-dim="status"]')
    const trackEl = root.querySelector('[data-stats-dim="track"]')
    const tagEl = root.querySelector('[data-stats-dim="tag"]')
    const scheduleEl = root.querySelector('[data-stats-dim="schedule"]')
    return {
        statuses: normalizeExclusivePair(getMultiValues(statusEl), ["accepted", "not_accepted"]),
        trackIds: getMultiValues(trackEl).map(String),
        tagIds: getMultiValues(tagEl).map(String),
        schedules: normalizeExclusivePair(getMultiValues(scheduleEl), ["scheduled", "unscheduled"]),
    }
}

const isFilterActive = (filters) => (
    Boolean(filters.statuses.length)
    || Boolean(filters.trackIds.length)
    || Boolean(filters.tagIds.length)
    || Boolean(filters.schedules.length)
)

const updateResetButton = (cardName) => {
    const resetBtn = document.querySelector(`[data-stats-reset="${cardName}"]`)
    if (!resetBtn) return
    resetBtn.hidden = !isFilterActive(readCardFilters(cardName))
}

const resetCardFilters = (cardName) => {
    const root = document.querySelector(`[data-stats-filters="${cardName}"]`)
    if (!root) return
    root.querySelectorAll("[data-stats-dim]").forEach((multi) => {
        clearMultiValues(multi)
        styleMultiToggle(multi)
    })
    updateResetButton(cardName)
}

const filterRecords = (records, filters) => {
    const trackIds = new Set((filters.trackIds || []).map(String))
    const tagIds = new Set((filters.tagIds || []).map(String))
    const statuses = filters.statuses || []
    const schedules = filters.schedules || []
    const wantAccepted = statuses.includes("accepted")
    const wantNotAccepted = statuses.includes("not_accepted")
    const wantScheduled = schedules.includes("scheduled")
    const wantUnscheduled = schedules.includes("unscheduled")

    return (records || []).filter((row) => {
        if (wantAccepted && !wantNotAccepted && !row.accepted) return false
        if (wantNotAccepted && !wantAccepted && row.accepted) return false
        if (trackIds.size && !trackIds.has(String(row.track_id || ""))) return false
        if (tagIds.size && !(row.tags || []).some((tag) => tagIds.has(String(tag.id)))) return false
        if (wantScheduled && !wantUnscheduled && !row.scheduled) return false
        if (wantUnscheduled && !wantScheduled && row.scheduled) return false
        return true
    })
}

const countBy = (rows, keyFn, colorFn) => {
    const map = new Map()
    rows.forEach((row) => {
        const key = keyFn(row)
        if (!key) return
        const current = map.get(key) || { label: key, value: 0, color: null }
        current.value += 1
        if (!current.color && colorFn) current.color = colorFn(row)
        map.set(key, current)
    })
    return Array.from(map.values()).sort((a, b) => a.label.localeCompare(b.label))
}

const buildTypeRows = (rows) => countBy(rows, (row) => row.type)

const buildTrackRows = (rows) => countBy(
    rows,
    (row) => row.track,
    (row) => row.track_color || "#2185d0",
)

const buildTagRows = (rows) => {
    const map = new Map()
    rows.forEach((row) => {
        ;(row.tags || []).forEach((tag) => {
            const key = tag.label
            if (!key) return
            const current = map.get(key) || { label: key, value: 0, color: tag.color || "#2185d0" }
            current.value += 1
            map.set(key, current)
        })
    })
    return Array.from(map.values()).sort((a, b) => a.label.localeCompare(b.label))
}

const buildLanguageRows = (rows) => countBy(rows, (row) => row.language)

const buildStateRows = (rows) => countBy(
    rows,
    (row) => row.state_label || row.state,
    null,
).map((item) => {
    const match = rows.find((row) => (row.state_label || row.state) === item.label)
    return { ...item, state: match ? match.state : null }
})

const buildTimelinePoints = (rows, dateAxis) => {
    const counts = {}
    rows.forEach((row) => {
        if (!row.date) return
        counts[row.date] = (counts[row.date] || 0) + 1
    })
    const axis = (dateAxis && dateAxis.length)
        ? dateAxis
        : Object.keys(counts).sort()
    if (!axis.length) return []
    return axis.map((date) => ({ x: date, y: counts[date] || 0 }))
}

const seriesFromGroups = (groups, rows, dateAxis, matchFn) => {
    const series = groups.map((group) => ({
        label: group.label,
        color: group.color || "#2185d0",
        filterDim: group.filterDim || null,
        filterValue: group.filterValue == null ? "" : String(group.filterValue),
        data: buildTimelinePoints(rows.filter((row) => matchFn(row, group)), dateAxis),
    }))
    return series.filter((item) => item.data.some((point) => point.y > 0))
}

const singleSeries = (label, color, filterDim, filterValue, rows, dateAxis) => ({
    mode: "single",
    series: [{
        label,
        color,
        filterDim,
        filterValue: filterValue == null ? "" : String(filterValue),
        data: buildTimelinePoints(rows, dateAxis),
    }],
})

const buildTimelineSeries = (rows, dateAxis, filters, meta) => {
    const trackIds = (filters.trackIds || []).map(String)
    const tagIds = (filters.tagIds || []).map(String)
    const schedules = filters.schedules || []
    const statuses = filters.statuses || []

    if (trackIds.length === 1) {
        const track = (meta.tracks || []).find((item) => String(item.id) === trackIds[0])
        return singleSeries(
            (track && track.label) || "Track",
            (track && track.color) || "#2185d0",
            "track",
            trackIds[0],
            rows,
            dateAxis,
        )
    }
    if (trackIds.length > 1) {
        const selectedTracks = (meta.tracks || []).filter((track) => trackIds.includes(String(track.id)))
        const series = seriesFromGroups(
            selectedTracks.map((track) => ({
                label: track.label,
                color: track.color || "#2185d0",
                filterDim: "track",
                filterValue: track.id,
            })),
            rows,
            dateAxis,
            (row, group) => String(row.track_id || "") === String(group.filterValue),
        )
        if (series.length) return { mode: "track", series }
    }

    if (tagIds.length === 1) {
        const tag = (meta.tags || []).find((item) => String(item.id) === tagIds[0])
        return singleSeries(
            (tag && tag.label) || "Tag",
            (tag && tag.color) || "#2185d0",
            "tag",
            tagIds[0],
            rows,
            dateAxis,
        )
    }
    if (tagIds.length > 1) {
        const selectedTags = (meta.tags || []).filter((tag) => tagIds.includes(String(tag.id)))
        const series = seriesFromGroups(
            selectedTags.map((tag) => ({
                label: tag.label,
                color: tag.color || "#2185d0",
                filterDim: "tag",
                filterValue: tag.id,
            })),
            rows,
            dateAxis,
            (row, group) => (row.tags || []).some((tag) => String(tag.id) === String(group.filterValue)),
        )
        if (series.length) return { mode: "tag", series }
    }

    if (schedules.length === 1) {
        return singleSeries(
            schedules[0] === "scheduled" ? L_SCHEDULED : L_UNSCHEDULED,
            schedules[0] === "scheduled" ? "#16a34a" : "#64748b",
            "schedule",
            schedules[0],
            rows,
            dateAxis,
        )
    }

    if (statuses.length === 1) {
        return singleSeries(
            statuses[0] === "accepted" ? L_ACCEPTED : L_NOT_ACCEPTED,
            SCOPE_COLORS[statuses[0]],
            "status",
            statuses[0],
            rows,
            dateAxis,
        )
    }

    // No specific multi selection → multi mountains by Track, else Tag, else Schedule, else Status.
    if ((meta.tracks || []).length) {
        const trackGroups = (meta.tracks || []).map((track) => ({
            label: track.label,
            color: track.color || "#2185d0",
            filterDim: "track",
            filterValue: track.id,
        }))
        if (rows.some((row) => !row.track_id)) {
            trackGroups.push({
                label: L_NO_TRACK,
                color: "#94a3b8",
                filterDim: "track",
                filterValue: "",
            })
        }
        const series = seriesFromGroups(
            trackGroups,
            rows,
            dateAxis,
            (row, group) => String(row.track_id || "") === String(group.filterValue),
        )
        if (series.length) return { mode: "track", series }
    }

    if ((meta.tags || []).length) {
        const series = seriesFromGroups(
            (meta.tags || []).map((tag) => ({
                label: tag.label,
                color: tag.color || "#2185d0",
                filterDim: "tag",
                filterValue: tag.id,
            })),
            rows,
            dateAxis,
            (row, group) => (row.tags || []).some((tag) => String(tag.id) === String(group.filterValue)),
        )
        if (series.length) return { mode: "tag", series }
    }

    const scheduleSeries = seriesFromGroups(
        [
            { label: L_SCHEDULED, color: "#16a34a", filterDim: "schedule", filterValue: "scheduled" },
            { label: L_UNSCHEDULED, color: "#64748b", filterDim: "schedule", filterValue: "unscheduled" },
        ],
        rows,
        dateAxis,
        (row, group) => (group.filterValue === "scheduled" ? row.scheduled : !row.scheduled),
    )
    if (scheduleSeries.length) return { mode: "schedule", series: scheduleSeries }

    const statusSeries = seriesFromGroups(
        [
            { label: L_ACCEPTED, color: SCOPE_COLORS.accepted, filterDim: "status", filterValue: "accepted" },
            { label: L_NOT_ACCEPTED, color: SCOPE_COLORS.not_accepted, filterDim: "status", filterValue: "not_accepted" },
        ],
        rows,
        dateAxis,
        (row, group) => (group.filterValue === "accepted" ? row.accepted : !row.accepted),
    )
    if (statusSeries.length) return { mode: "status", series: statusSeries }

    return singleSeries(L_SESSIONS, SCOPE_COLORS.all, null, "", rows, dateAxis)
}

const toChartData = (rows) => {
    if (!rows || !rows.length) return null
    return {
        series: rows.map((row) => row.value),
        labels: rows.map((row) => row.label),
        states: rows.map((row) => row.state || null),
        colors: rows.map((row) => row.color || null),
    }
}

const padTimelinePoints = (timelineRows) => {
    let parsedData = timelineRows.map((point) => ({
        x: parseCalendarDate(point.x),
        y: point.y,
    }))
    parsedData.sort((a, b) => a.x - b.x)
    if (parsedData.length > 0) {
        const ONE_DAY = 86400000
        parsedData.unshift({ x: parsedData[0].x - ONE_DAY, y: 0 })
        parsedData.push({ x: parsedData[parsedData.length - 1].x + ONE_DAY, y: 0 })
    }
    return parsedData
}

const loadDeadlineAnnotations = () => {
    try {
        const annotations = globalData && globalData.dataset.annotations
            ? globalData.dataset.annotations
            : '{"deadlines":[]}'
        return JSON.parse(annotations).deadlines.map((element) => ({
            x: parseCalendarDate(element[0]),
            borderColor: "#ff4560",
            strokeDashArray: 0,
            label: {
                style: {
                    borderColor: "#ff4560",
                    background: "#ff4560",
                    color: "#fff",
                    fontSize: "14px",
                    padding: { top: 5 },
                },
                text: element[1],
            },
        }))
    } catch (error) {
        console.error("Failed to parse timeline annotations", error)
        return []
    }
}

const writeTimelineSummary = (targetId, parsedSeries, stateRows, sourceRows) => {
    let totalCount = 0
    let peakCount = 0
    let peakDate = "-"
    const dayTotals = new Map()

    // Prefer unique filtered records so overlapping tag series do not inflate totals.
    if (sourceRows && sourceRows.length) {
        sourceRows.forEach((row) => {
            if (!row.date) return
            totalCount += 1
            dayTotals.set(row.date, (dayTotals.get(row.date) || 0) + 1)
        })
    } else {
        parsedSeries.forEach((series) => {
            if (series.hidden) return
            series.data.forEach((point) => {
                totalCount += point.y
                dayTotals.set(point.x, (dayTotals.get(point.x) || 0) + point.y)
            })
        })
    }
    dayTotals.forEach((value, day) => {
        if (value > peakCount) {
            peakCount = value
            const dayValue = typeof day === "number" ? day : parseCalendarDate(day)
            peakDate = new Date(dayValue).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
            })
        }
    })

    let acceptedRate = "0.0%"
    if (stateRows && stateRows.length) {
        let accepted = 0
        let total = 0
        stateRows.forEach((row) => {
            total += row.value
            if (String(row.state || "").toLowerCase() === "accepted"
                || String(row.state || "").toLowerCase() === "confirmed") {
                accepted += row.value
            }
        })
        if (total > 0) acceptedRate = ((accepted / total) * 100).toFixed(1) + "%"
    }

    const slot = document.querySelector(`[data-summary-for="${targetId}"]`)
    if (!slot) return
    renderSummaryItems(slot, [
        { label: L_TOTAL_SESSIONS, value: totalCount },
        {
            label: L_PEAK_DAY,
            value: peakCount > 0 ? `${peakDate}, ${peakCount}` : "-",
        },
        { label: L_ACCEPTED_RATE, value: acceptedRate },
    ])
}

const timelineChartOptions = (parsedSeries, { empty = false } = {}) => ({
    series: parsedSeries.map((row) => ({ name: row.name, data: row.data })),
    colors: parsedSeries.map((row) => row.color),
    xaxis: {
        type: "datetime",
        tooltip: { enabled: false },
        labels: {
            datetimeUTC: false,
            format: "dd MMM",
            style: { fontWeight: 500, fontSize: "12.5px", colors: "#6b7280" },
        },
        axisBorder: { show: false },
        axisTicks: { show: false },
    },
    yaxis: {
        min: 0,
        max: empty ? 1 : undefined,
        tickAmount: empty ? 1 : undefined,
        labels: {
            style: { fontSize: "12.5px", colors: "#6b7280", fontWeight: 500 },
            formatter: (val) => (empty ? "" : String(Math.round(Number(val)))),
        },
    },
    annotations: { xaxis: empty ? [] : loadDeadlineAnnotations() },
    chart: {
        redrawOnParentResize: true,
        height: 200,
        type: "area",
        stacked: false,
        toolbar: { show: false },
        zoom: { enabled: false },
        animations: { enabled: !empty },
    },
    fill: empty
        ? { type: "solid", opacity: 0 }
        : {
            type: "gradient",
            gradient: {
                shadeIntensity: 0.35,
                opacityFrom: 0.45,
                opacityTo: 0.05,
            },
        },
    stroke: { width: empty ? 0 : 2, curve: "smooth" },
    dataLabels: { enabled: false },
    legend: { show: false },
    grid: {
        borderColor: "#f3f4f6",
        strokeDashArray: 3,
        padding: { left: 4, right: 4 },
    },
    tooltip: {
        enabled: !empty,
        shared: true,
        x: { show: true, format: "dd MMM yyyy" },
    },
})

const drawEmptyTimeline = (targetId, dateAxis) => {
    const targetElement = document.getElementById(targetId)
    if (!targetElement || typeof ApexCharts === "undefined") return null

    const axis = (dateAxis && dateAxis.length)
        ? dateAxis
        : [new Date().toISOString().slice(0, 10)]
    const parsedSeries = [{
        name: " ",
        color: "#e5e7eb",
        hidden: false,
        data: padTimelinePoints(axis.map((date) => ({ x: date, y: 0 }))),
    }]

    const chart = new ApexCharts(targetElement, timelineChartOptions(parsedSeries, { empty: true }))
    chart.render()
    writeTimelineSummary(targetId, [{ data: parsedSeries[0].data, hidden: false }], [], [])
    return chart
}

const drawTimelineSeries = (targetId, seriesRows, stateRows, sourceRows) => {
    const targetElement = document.getElementById(targetId)
    if (!targetElement || !seriesRows || !seriesRows.length) return null
    if (typeof ApexCharts === "undefined") {
        console.error("ApexCharts is not available for timeline rendering")
        return null
    }

    const parsedSeries = seriesRows.map((row) => ({
        name: row.label,
        color: row.color || "#2185d0",
        filterDim: row.filterDim || null,
        filterValue: row.filterValue == null ? "" : String(row.filterValue),
        hidden: false,
        data: padTimelinePoints(row.data || []),
    })).filter((row) => row.data.length)
    if (!parsedSeries.length) return null

    const chart = new ApexCharts(targetElement, timelineChartOptions(parsedSeries))
    chart.render()
    writeTimelineSummary(targetId, parsedSeries, stateRows, sourceRows)
    return chart
}

const drawHBarChart = (data, elementId, clickType, status, colorPalette) => {
    const element = document.getElementById(elementId)
    if (!element || !data || !data.series || !data.series.length) return null
    if (typeof ApexCharts === "undefined") {
        console.error("ApexCharts is not available for bar chart rendering")
        return null
    }

    const palette = (colorPalette && colorPalette.length) ? colorPalette : PALETTE
    const combined = data.labels.map((label, i) => ({
        label,
        value: data.series[i],
        color: (data.colors && data.colors[i]) || palette[i % palette.length],
    }))
    combined.sort((a, b) => b.value - a.value)

    const maxVal = Math.max(...combined.map((d) => d.value), 1)
    const axisMax = Math.max(Math.ceil(maxVal * 1.25), 3)
    const barColors = combined.map((d) => d.color)

    const chart = new ApexCharts(element, {
        series: [{ name: "Count", data: combined.map((d) => d.value) }],
        chart: {
            type: "bar",
            height: 200,
            width: "100%",
            redrawOnParentResize: true,
            toolbar: { show: false },
            events: {
                dataPointSelection: (event, chartContext, config) => {
                    if (!clickType || !dataMapping[clickType]) return
                    const typeMapping = {
                        track: "track",
                        type: "submission_type",
                        state: "state",
                        language: "content_locale",
                        tag: "tags",
                    }
                    const label = combined[config.dataPointIndex].label
                    const searchValue = dataMapping[clickType][label]
                    if (searchValue) {
                        window.location.href = searchUrl + "&" + typeMapping[clickType] + "=" + searchValue
                    }
                },
                dataPointMouseEnter: () => { element.classList.add("is-pointer") },
                dataPointMouseLeave: () => { element.classList.remove("is-pointer") },
            },
        },
        plotOptions: {
            bar: {
                horizontal: true,
                barHeight: "55%",
                borderRadius: 3,
                distributed: true,
                dataLabels: { position: "top" },
            },
        },
        dataLabels: {
            enabled: true,
            offsetX: 25,
            textAnchor: "start",
            style: { fontSize: "12px", fontWeight: 600, colors: ["#374151"] },
            background: { enabled: false },
        },
        xaxis: {
            categories: combined.map((d) => d.label),
            min: 0,
            max: axisMax,
            tickAmount: 3,
            labels: {
                style: { fontSize: "12.5px", colors: "#6b7280", fontWeight: 500 },
                formatter: (val) => String(Math.round(Number(val))),
            },
            axisBorder: { show: true, color: "#e5e7eb" },
            axisTicks: { show: false },
        },
        yaxis: {
            labels: {
                style: { fontSize: "12.5px", colors: "#374151", fontWeight: 500 },
                maxWidth: 130,
            },
        },
        colors: barColors,
        grid: {
            borderColor: "#f3f4f6",
            xaxis: { lines: { show: true } },
            yaxis: { lines: { show: false } },
            padding: { left: 0, right: 40, bottom: 0 },
        },
        tooltip: {
            enabled: true,
            x: { show: false },
            y: { formatter: (val) => val + " sessions" },
        },
        legend: { show: false },
    })
    chart.render()

    const totalCount = combined.reduce((a, b) => a + b.value, 0)
    const topItem = combined[0] ? combined[0].label : "-"
    let shortTopItem = topItem
    if (shortTopItem.length > 20) shortTopItem = shortTopItem.substring(0, 17) + "..."

    const slot = document.querySelector(`[data-summary-for="${elementId}"]`)
    if (slot) {
        renderSummaryItems(slot, [
            {
                label: L_TOP_TYPE,
                value: shortTopItem,
                title: topItem,
                valueClass: "td-ts-value is-compact",
            },
            { label: L_TOTAL_TYPES, value: combined.length },
            { label: L_TOTAL_SESSIONS, value: totalCount },
        ])
    }
    return chart
}

const appendStatsPadRow = (tbody) => {
    const tr = createEl("tr", "td-st-pad")
    tr.setAttribute("aria-hidden", "true")
    ;["td-st-dot", "td-st-name", "td-st-count", "td-st-pct"].forEach((cls) => {
        const td = createEl("td", cls)
        if (cls === "td-st-name") td.textContent = "\u00a0"
        tr.appendChild(td)
    })
    tbody.appendChild(tr)
}

const drawStatsTable = (data, elementId, options = {}) => {
    const element = document.getElementById(elementId)
    if (!element) return

    if (!data || !data.series || !data.series.length) {
        clearNode(element)
        element.appendChild(createEmptyChartPlaceholder())
        return
    }

    const assignmentTotal = data.series.reduce((a, b) => a + b, 0)
    const uniqueTotal = Number.isFinite(options.uniqueTotal) ? options.uniqueTotal : null
    const total = uniqueTotal != null ? uniqueTotal : assignmentTotal
    const rows = data.labels.map((label, i) => ({
        label,
        value: data.series[i],
        color: (data.colors && data.colors[i]) || null,
    }))
    rows.sort((a, b) => b.value - a.value)

    clearNode(element)
    const table = createEl("table", "td-stats-table")
    const colgroup = document.createElement("colgroup")
    ;["td-col-dot", "td-col-name", "td-col-count", "td-col-pct"].forEach((cls) => {
        colgroup.appendChild(createEl("col", cls))
    })
    table.appendChild(colgroup)

    const thead = document.createElement("thead")
    const headRow = document.createElement("tr")
    const nameTh = createEl("th", null, L_NAME)
    nameTh.colSpan = 2
    headRow.appendChild(nameTh)
    headRow.appendChild(createEl("th", "td-st-count", L_COUNT))
    headRow.appendChild(createEl("th", "td-st-pct", "%"))
    thead.appendChild(headRow)
    table.appendChild(thead)

    const tbody = document.createElement("tbody")
    rows.forEach(({ label, value, color }, i) => {
        const pct = total > 0 ? `${((value / total) * 100).toFixed(1)}%` : "0.0%"
        const tr = document.createElement("tr")
        const dotTd = createEl("td", "td-st-dot")
        const dot = document.createElement("span")
        dot.style.setProperty("--td-dot-color", safeCssColor(color || PALETTE[i % PALETTE.length]))
        dotTd.appendChild(dot)
        tr.appendChild(dotTd)
        tr.appendChild(createEl("td", "td-st-name", label))
        tr.appendChild(createEl("td", "td-st-count", value))
        tr.appendChild(createEl("td", "td-st-pct", pct))
        tbody.appendChild(tr)
    })

    const padTo = Math.max(MIN_STATS_ROWS, rows.length)
    for (let i = rows.length; i < padTo; i += 1) appendStatsPadRow(tbody)
    table.appendChild(tbody)

    const tfoot = document.createElement("tfoot")
    const footRow = document.createElement("tr")
    const totalLabel = document.createElement("td")
    totalLabel.colSpan = 2
    const totalStrong = document.createElement("strong")
    totalStrong.textContent = TOTAL_LABEL
    totalLabel.appendChild(totalStrong)
    footRow.appendChild(totalLabel)

    const totalCountTd = createEl("td", "td-st-count")
    const totalCountStrong = document.createElement("strong")
    totalCountStrong.textContent = String(total)
    totalCountTd.appendChild(totalCountStrong)
    footRow.appendChild(totalCountTd)

    const totalPctTd = createEl("td", "td-st-pct")
    const totalPctStrong = document.createElement("strong")
    totalPctStrong.textContent = uniqueTotal != null ? "" : "100%"
    totalPctTd.appendChild(totalPctStrong)
    footRow.appendChild(totalPctTd)

    tfoot.appendChild(footRow)
    table.appendChild(tfoot)
    element.appendChild(table)
}

const equalizeStatsTableRows = () => {
    const bodies = document.querySelectorAll(".td-analytics-bottom-row .td-stats-table tbody")
    if (!bodies.length) return
    let maxRows = MIN_STATS_ROWS
    bodies.forEach((tbody) => {
        maxRows = Math.max(maxRows, tbody.querySelectorAll("tr").length)
    })
    bodies.forEach((tbody) => {
        const current = tbody.querySelectorAll("tr").length
        for (let i = current; i < maxRows; i += 1) appendStatsPadRow(tbody)
    })
}

const setStatusSelectClass = (el, status) => {
    STATUS_SCOPE_CLASSES.forEach((cls) => el.classList.remove(cls))
    el.classList.add(`is-scope-${String(status || "all").replace(/_/g, "-")}`)
}

const statusScopeFromMulti = (multi) => {
    const values = normalizeExclusivePair(getMultiValues(multi), ["accepted", "not_accepted"])
    if (!values.length) return "all"
    return values[0]
}

const syncGlobalButtons = () => {
    const statusMultis = Array.from(document.querySelectorAll('[data-stats-dim="status"]'))
    if (!statusMultis.length) return
    const first = statusScopeFromMulti(statusMultis[0])
    const allMatch = statusMultis.every((multi) => statusScopeFromMulti(multi) === first)
    document.querySelectorAll("[data-stats-scope-global]").forEach((btn) => {
        const value = btn.getAttribute("data-stats-scope-global")
        const active = allMatch && value === first
        btn.classList.toggle("is-active", active)
        btn.setAttribute("aria-pressed", active ? "true" : "false")
    })
}

const renderCard = (payload, cardName) => {
    const filters = readCardFilters(cardName)
    const rows = filterRecords(payload.records || [], filters)
    const meta = payload.meta || { tracks: [], tags: [] }
    updateResetButton(cardName)

    if (cardName === "timeline") {
        destroyChart("timeline")
        clearChartTarget("stats-timeline")
        clearSummary("stats-timeline")
        const titleEl = document.querySelector("[data-stats-timeline-title]")
        if (titleEl && payload.titles) {
            const titleKey = filters.statuses.length === 1 ? filters.statuses[0] : "all"
            titleEl.textContent = payload.titles[titleKey] || payload.titles.all
        }
        const built = buildTimelineSeries(rows, payload.dateAxis || [], filters, meta)
        const series = (built && built.series) || []
        const hasData = series.some((item) => (item.data || []).some((point) => point.y > 0))
        if (hasData) {
            chartInstances.timeline = drawTimelineSeries(
                "stats-timeline",
                series,
                buildStateRows(rows),
                rows,
            )
        } else {
            chartInstances.timeline = drawEmptyTimeline("stats-timeline", payload.dateAxis || [])
        }
        return
    }

    if (cardName === "type") {
        destroyChart("type")
        clearChartTarget("stats-type-chart")
        clearSummary("stats-type-chart")
        const typeData = toChartData(buildTypeRows(rows))
        if (typeData) {
            const mountainColors = (meta.tracks || []).map((track) => track.color).filter(Boolean)
            chartInstances.type = drawHBarChart(
                typeData,
                "stats-type-chart",
                "type",
                filters.statuses.length === 1 ? filters.statuses[0] : "all",
                mountainColors,
            )
        } else {
            clearSummary("stats-type-chart")
            const slot = document.querySelector('[data-summary-for="stats-type-chart"]')
            if (slot) {
                clearNode(slot)
                slot.appendChild(createEmptyChartPlaceholder())
            }
        }
        return
    }

    if (cardName === "track") {
        if (!document.getElementById("stats-track-table")) return
        drawStatsTable(toChartData(buildTrackRows(rows)), "stats-track-table")
        return
    }

    if (cardName === "tag") {
        if (!document.getElementById("stats-tag-table")) return
        drawStatsTable(toChartData(buildTagRows(rows)), "stats-tag-table", {
            uniqueTotal: rows.length,
        })
        return
    }

    if (cardName === "language") {
        drawStatsTable(toChartData(buildLanguageRows(rows)), "stats-language-table")
        return
    }

    if (cardName === "state") {
        drawStatsTable(toChartData(buildStateRows(rows)), "stats-state-table")
    }
}

const CARD_NAMES = ["timeline", "type", "track", "tag", "language", "state"]

const renderAllCards = (payload) => {
    CARD_NAMES.forEach((cardName) => renderCard(payload, cardName))
    equalizeStatsTableRows()
}

const onMultiFilterChange = (payload, multi) => {
    const cardName = multi.getAttribute("data-stats-card")
    styleMultiToggle(multi)
    renderCard(payload, cardName)
    equalizeStatsTableRows()
    syncGlobalButtons()
}

const initAnalyticsFilters = () => {
    const payload = loadPayload()
    if (!payload) {
        equalizeStatsTableRows()
        return
    }

    renderAllCards(payload)
    syncGlobalButtons()

    document.querySelectorAll(".td-analytics-multi").forEach((multi) => {
        styleMultiToggle(multi)
        const toggle = multi.querySelector(".td-analytics-multi-toggle")
        const menu = getMultiMenu(multi)
        if (toggle) {
            toggle.addEventListener("click", (event) => {
                event.preventDefault()
                event.stopPropagation()
                if (toggle.disabled) return
                const isOpen = multi.classList.contains("is-open")
                if (isOpen) closeAllMultiMenus()
                else openMultiMenu(multi)
            })
        }
        if (menu) {
            menu.addEventListener("click", (event) => event.stopPropagation())
            menu.querySelectorAll('input[type="checkbox"]').forEach((input) => {
                input.addEventListener("change", () => onMultiFilterChange(payload, multi))
            })
        }
    })

    document.addEventListener("click", () => closeAllMultiMenus())
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeAllMultiMenus()
    })
    window.addEventListener("resize", () => closeAllMultiMenus())
    window.addEventListener("scroll", () => closeAllMultiMenus(), true)

    document.querySelectorAll("[data-stats-reset]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const cardName = btn.getAttribute("data-stats-reset")
            resetCardFilters(cardName)
            closeAllMultiMenus()
            renderCard(payload, cardName)
            equalizeStatsTableRows()
            syncGlobalButtons()
        })
    })

    document.querySelectorAll("[data-stats-scope-global]").forEach((btn) => {
        btn.addEventListener("click", () => {
            const status = btn.getAttribute("data-stats-scope-global") || "all"
            document.querySelectorAll('[data-stats-dim="status"]').forEach((multi) => {
                setMultiValues(multi, status === "all" ? [] : [status])
                styleMultiToggle(multi)
            })
            closeAllMultiMenus()
            renderAllCards(payload)
            syncGlobalButtons()
        })
    })
}

setTimeout(initAnalyticsFilters, 10)
