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
const L_TOP_TRACK = (statsRoot && statsRoot.dataset.labelTopTrack) || "Top track"
const L_TOTAL_TRACKS = (statsRoot && statsRoot.dataset.labelTotalTracks) || "Total tracks"
const L_NAME = (statsRoot && statsRoot.dataset.labelName) || "Name"
const L_COUNT = (statsRoot && statsRoot.dataset.labelCount) || "Count"
const L_NO_DATA = (statsRoot && statsRoot.dataset.labelNoData) || "No data for this status"

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
    track: null,
}

const ACCEPTED_STATES = new Set(["accepted", "confirmed"])

const escapeHtml = (value) => String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")

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

const toChartData = (rows) => {
    if (!rows || !rows.length) return null
    return {
        series: rows.map((row) => row.value),
        labels: rows.map((row) => row.label),
        states: rows.map((row) => row.state || null),
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
    const element = document.getElementById(elementId)
    if (element) element.innerHTML = ""
}

const clearSummary = (elementId) => {
    const slot = document.querySelector(`[data-summary-for="${elementId}"]`)
    if (slot) slot.innerHTML = ""
}

const getScopeBundle = (payload, scope) => {
    if (!payload) return null
    return payload[scope] || null
}

/* ─── Timeline (area chart) ─────────────────────────────────────────────── */
const drawTimeline = (targetId, timelineRows, label, stateRows) => {
    const targetElement = document.getElementById(targetId)
    if (!targetElement || !timelineRows || !timelineRows.length) return null
    if (typeof ApexCharts === "undefined") {
        console.error("ApexCharts is not available for timeline rendering")
        return null
    }

    let deadlines = []
    try {
        const annotations = globalData && globalData.dataset.annotations
            ? globalData.dataset.annotations
            : '{"deadlines":[]}'
        deadlines = JSON.parse(annotations).deadlines.map((element) => ({
            x: new Date(element[0]).getTime(),
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
        deadlines = []
    }

    let parsedData = timelineRows.map((point) => ({
        x: new Date(point.x).getTime(),
        y: point.y,
    }))
    parsedData.sort((a, b) => a.x - b.x)

    if (parsedData.length > 0) {
        const ONE_DAY = 86400000
        const firstTime = parsedData[0].x
        parsedData.unshift({ x: firstTime - ONE_DAY, y: 0 })
        const lastTime = parsedData[parsedData.length - 1].x
        parsedData.push({ x: lastTime + ONE_DAY, y: 0 })
    }

    const options = {
        series: [{ name: label, data: parsedData }],
        xaxis: {
            type: "datetime",
            tooltip: { enabled: false },
            labels: {
                datetimeUTC: false,
                format: "dd MMM",
                datetimeFormatter: {
                    year: "yyyy",
                    month: "MMM yyyy",
                    day: "dd MMM",
                    hour: "HH:mm",
                },
                style: { fontWeight: 500, fontSize: "12.5px", colors: "#6b7280" },
            },
            axisBorder: { show: false },
            axisTicks: { show: false },
        },
        yaxis: {
            labels: {
                style: { fontSize: "12.5px", colors: "#6b7280", fontWeight: 500 },
            },
        },
        annotations: { xaxis: deadlines },
        chart: {
            redrawOnParentResize: true,
            height: 200,
            type: "area",
            toolbar: { show: false },
            sparkline: { enabled: false },
        },
        colors: ["#2185d0", "#22c55e", "#ef4444"],
        fill: { type: ["gradient", "gradient", "gradient"] },
        stroke: { width: 2, curve: "smooth" },
        dataLabels: { enabled: false },
        legend: {
            formatter: function (val) {
                if (val.length > 15) val = val.slice(0, 15) + "…"
                return val
            },
            position: "top",
            horizontalAlign: "left",
            fontSize: "12px",
            markers: { width: 8, height: 8, radius: 4 },
        },
        grid: {
            borderColor: "#f3f4f6",
            strokeDashArray: 3,
            padding: { left: 4, right: 4 },
        },
        tooltip: {
            enabled: true,
            shared: true,
            x: { show: true, format: "dd MMM yyyy" },
            marker: { show: true },
        },
    }

    const chart = new ApexCharts(targetElement, options)
    chart.render()

    let totalCount = 0
    let peakCount = 0
    let peakDate = "-"
    parsedData.forEach((point) => {
        totalCount += point.y
        if (point.y > peakCount) {
            peakCount = point.y
            peakDate = new Date(point.x).toLocaleDateString("en-US", {
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
            const stateCode = String(row.state || "").toLowerCase()
            if (ACCEPTED_STATES.has(stateCode)) {
                accepted += row.value
            }
        })
        if (total > 0) acceptedRate = ((accepted / total) * 100).toFixed(1) + "%"
    }

    const summaryHtml = `
        <div class="td-ts-item">
            <div class="td-ts-label">${escapeHtml(L_TOTAL_SESSIONS)}</div>
            <div class="td-ts-value">${totalCount}</div>
        </div>
        <div class="td-ts-item">
            <div class="td-ts-label">${escapeHtml(L_PEAK_DAY)}</div>
            <div class="td-ts-value">${peakCount > 0 ? `${escapeHtml(peakDate)}, ${peakCount}` : "-"}</div>
        </div>
        <div class="td-ts-item">
            <div class="td-ts-label">${escapeHtml(L_ACCEPTED_RATE)}</div>
            <div class="td-ts-value">${acceptedRate}</div>
        </div>
    `
    const slot = document.querySelector(`[data-summary-for="${targetId}"]`)
    if (slot) {
        slot.innerHTML = summaryHtml
        slot.classList.add("td-timeline-summary")
    }

    return chart
}

/* ─── Horizontal Bar Chart ──────────────────────────────────────────────── */
const drawHBarChart = (data, elementId, clickType) => {
    const element = document.getElementById(elementId)
    if (!element || !data || !data.series || !data.series.length) return null
    if (typeof ApexCharts === "undefined") {
        console.error("ApexCharts is not available for bar chart rendering")
        return null
    }

    const combined = data.labels.map((label, i) => ({ label, value: data.series[i] }))
    combined.sort((a, b) => b.value - a.value)

    const chartHeight = 200
    const maxVal = Math.max(...combined.map((d) => d.value), 1)
    const axisMax = Math.max(Math.ceil(maxVal * 1.25), 3)

    const options = {
        series: [{ name: "Count", data: combined.map((d) => d.value) }],
        chart: {
            type: "bar",
            height: chartHeight,
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
                    }
                    const label = combined[config.dataPointIndex].label
                    const searchValue = dataMapping[clickType][label]
                    if (searchValue) {
                        window.location.href = searchUrl + "&" + typeMapping[clickType] + "=" + searchValue
                    }
                },
                dataPointMouseEnter: () => {
                    element.style.cursor = "pointer"
                },
                dataPointMouseLeave: () => {
                    element.style.cursor = "inherit"
                },
            },
        },
        plotOptions: {
            bar: {
                horizontal: true,
                barHeight: "55%",
                borderRadius: 3,
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
            forceNiceScale: false,
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
        colors: ["#2185d0"],
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
    }

    const chart = new ApexCharts(element, options)
    chart.render()

    const totalCount = combined.reduce((a, b) => a + b.value, 0)
    const uniqueCount = combined.length
    const topItem = combined[0] ? combined[0].label : "-"

    let topLabel = "Top Item"
    let totalLabel = "Total Items"
    if (clickType === "type") {
        totalLabel = L_TOTAL_TYPES
        topLabel = L_TOP_TYPE
    } else if (clickType === "track") {
        totalLabel = L_TOTAL_TRACKS
        topLabel = L_TOP_TRACK
    }

    let shortTopItem = topItem
    if (shortTopItem.length > 20) shortTopItem = shortTopItem.substring(0, 17) + "..."

    const summaryHtml = `
        <div class="td-ts-item" title="${escapeHtml(topItem)}">
            <div class="td-ts-label">${escapeHtml(topLabel)}</div>
            <div class="td-ts-value" style="font-size: 13px;">${escapeHtml(shortTopItem)}</div>
        </div>
        <div class="td-ts-item">
            <div class="td-ts-label">${escapeHtml(totalLabel)}</div>
            <div class="td-ts-value">${uniqueCount}</div>
        </div>
        <div class="td-ts-item">
            <div class="td-ts-label">${escapeHtml(L_TOTAL_SESSIONS)}</div>
            <div class="td-ts-value">${totalCount}</div>
        </div>
    `
    const slot = document.querySelector(`[data-summary-for="${elementId}"]`)
    if (slot) {
        slot.innerHTML = summaryHtml
        slot.classList.add("td-timeline-summary")
    }

    return chart
}

/* ─── Stats Table (language / state) ───────────────────────────────────── */
const PALETTE = ["#2185d0", "#f97316", "#22c55e", "#8b5cf6", "#ef4444", "#06b6d4", "#f59e0b", "#ec4899", "#10b981", "#a78bfa"]
const MIN_STATS_ROWS = 3

const drawStatsTable = (data, elementId) => {
    const element = document.getElementById(elementId)
    if (!element) return

    if (!data || !data.series || !data.series.length) {
        element.innerHTML = `<p class="td-analytics-empty">${escapeHtml(L_NO_DATA)}</p>`
        return
    }

    const total = data.series.reduce((a, b) => a + b, 0)
    const rows = data.labels.map((label, i) => ({ label, value: data.series[i] }))
    rows.sort((a, b) => b.value - a.value)

    // Data rows stay above Total; pad so every card has the same body height
    let html = `<table class="td-stats-table">
        <colgroup>
            <col class="td-col-dot" />
            <col class="td-col-name" />
            <col class="td-col-count" />
            <col class="td-col-pct" />
        </colgroup>
        <thead><tr>
            <th colspan="2">${escapeHtml(L_NAME)}</th>
            <th class="td-st-count">${escapeHtml(L_COUNT)}</th>
            <th class="td-st-pct">%</th>
        </tr></thead>
        <tbody>`

    rows.forEach(({ label, value }, i) => {
        const pct = total > 0 ? ((value / total) * 100).toFixed(1) : "0.0"
        const color = PALETTE[i % PALETTE.length]
        html += `<tr>
            <td class="td-st-dot"><span style="background:${color}"></span></td>
            <td class="td-st-name">${escapeHtml(label)}</td>
            <td class="td-st-count">${value}</td>
            <td class="td-st-pct">${pct}%</td>
        </tr>`
    })

    const padTo = Math.max(MIN_STATS_ROWS, rows.length)
    for (let i = rows.length; i < padTo; i += 1) {
        html += `<tr class="td-st-pad" aria-hidden="true">
            <td class="td-st-dot"></td>
            <td class="td-st-name">&nbsp;</td>
            <td class="td-st-count"></td>
            <td class="td-st-pct"></td>
        </tr>`
    }

    html += `</tbody>
        <tfoot><tr>
            <td colspan="2"><strong>${escapeHtml(TOTAL_LABEL)}</strong></td>
            <td class="td-st-count"><strong>${total}</strong></td>
            <td class="td-st-pct"><strong>100%</strong></td>
        </tr></tfoot>
    </table>`

    element.innerHTML = html
}

/** Pad every stats table body to the same row count so Total lines up. */
const equalizeStatsTableRows = () => {
    const bodies = document.querySelectorAll(".td-analytics-bottom-row .td-stats-table tbody")
    if (!bodies.length) return

    let maxRows = MIN_STATS_ROWS
    bodies.forEach((tbody) => {
        maxRows = Math.max(maxRows, tbody.querySelectorAll("tr").length)
    })

    bodies.forEach((tbody) => {
        const current = tbody.querySelectorAll("tr").length
        for (let i = current; i < maxRows; i += 1) {
            const tr = document.createElement("tr")
            tr.className = "td-st-pad"
            tr.setAttribute("aria-hidden", "true")
            tr.innerHTML = `<td class="td-st-dot"></td><td class="td-st-name">&nbsp;</td><td class="td-st-count"></td><td class="td-st-pct"></td>`
            tbody.appendChild(tr)
        }
    })
}

/* ─── Per-card render ───────────────────────────────────────────────────── */
const renderCard = (payload, cardName, scope) => {
    const bundle = getScopeBundle(payload, scope)
    if (!bundle) return

    if (cardName === "timeline") {
        destroyChart("timeline")
        clearChartTarget("stats-timeline")
        clearSummary("stats-timeline")
        const titleEl = document.querySelector("[data-stats-timeline-title]")
        if (titleEl && payload.titles) {
            titleEl.textContent = payload.titles[scope] || payload.titles.all
        }
        if (bundle.timeline && bundle.timeline.length) {
            chartInstances.timeline = drawTimeline(
                "stats-timeline",
                bundle.timeline,
                bundle.timelineLabel || "Sessions",
                bundle.state,
            )
        } else {
            clearChartTarget("stats-timeline")
            const slot = document.querySelector('[data-summary-for="stats-timeline"]')
            if (slot) slot.innerHTML = `<p class="td-analytics-empty">${escapeHtml(L_NO_DATA)}</p>`
        }
        return
    }

    if (cardName === "type") {
        destroyChart("type")
        clearChartTarget("stats-type-chart")
        clearSummary("stats-type-chart")
        const typeData = toChartData(bundle.type)
        if (typeData) {
            chartInstances.type = drawHBarChart(typeData, "stats-type-chart", "type")
        } else {
            const slot = document.querySelector('[data-summary-for="stats-type-chart"]')
            if (slot) slot.innerHTML = `<p class="td-analytics-empty">${escapeHtml(L_NO_DATA)}</p>`
        }
        return
    }

    if (cardName === "track") {
        destroyChart("track")
        clearChartTarget("stats-track-chart")
        clearSummary("stats-track-chart")
        const trackData = toChartData(bundle.track)
        if (trackData) {
            chartInstances.track = drawHBarChart(trackData, "stats-track-chart", "track")
        } else {
            const slot = document.querySelector('[data-summary-for="stats-track-chart"]')
            if (slot) slot.innerHTML = `<p class="td-analytics-empty">${escapeHtml(L_NO_DATA)}</p>`
        }
        return
    }

    if (cardName === "language") {
        drawStatsTable(toChartData(bundle.language), "stats-language-table")
        return
    }

    if (cardName === "state") {
        drawStatsTable(toChartData(bundle.state), "stats-state-table")
    }
}

const initAnalyticsFilters = () => {
    const payload = loadPayload()
    if (!payload) {
        equalizeStatsTableRows()
        return
    }

    const filters = document.querySelectorAll("[data-stats-filter]")
    filters.forEach((filter) => {
        const cardName = filter.getAttribute("data-stats-filter")
        renderCard(payload, cardName, filter.value || "all")
        filter.addEventListener("change", () => {
            renderCard(payload, cardName, filter.value || "all")
            equalizeStatsTableRows()
        })
    })
    equalizeStatsTableRows()
}

setTimeout(initAnalyticsFilters, 10)
