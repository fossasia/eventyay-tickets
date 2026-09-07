function parseData(id) {
    const el = document.getElementById(id)
    if (!el) return null
    try {
        return JSON.parse(el.textContent)
    } catch (e) {
        console.error('meetup-analytics: failed to parse JSON for', id, e)
        return null
    }
}

const FONT_FAMILY = '"Open Sans", "OpenSans", "Helvetica Neue", Helvetica, Arial, sans-serif'
const PALETTE = ['#2185d0', '#21ba45', '#f2711c', '#db2828', '#a333c8', '#fbbd08', '#00b5ad']

function drawMeetupOrdersOverTime() {
    const chartEl = document.getElementById('meetup-orders-over-time-chart')
    if (!chartEl) return

    const series = parseData('meetup-orders-over-time-data')
    if (!series || series.length === 0) return

    const labelOrdered = chartEl.dataset.labelOrdered || 'Placed'
    const labelPaid = chartEl.dataset.labelPaid || 'Confirmed'

    const options = {
        series: [
            { name: labelOrdered, data: series.map(d => ({ x: new Date(d.x).getTime(), y: d.ordered })) },
            { name: labelPaid, data: series.map(d => ({ x: new Date(d.x).getTime(), y: d.paid })) }
        ],
        chart: {
            type: 'area',
            width: '100%',
            height: 240,
            fontFamily: FONT_FAMILY,
            redrawOnParentResize: true,
            toolbar: { show: false },
            animations: { enabled: true }
        },
        colors: [PALETTE[0], PALETTE[1]],
        xaxis: {
            type: 'datetime',
            tooltip: { enabled: false },
            labels: {
                format: 'dd MMM',
                datetimeUTC: true,
                style: { fontFamily: FONT_FAMILY }
            }
        },
        yaxis: { min: 0, labels: { formatter: (v) => Math.round(v), style: { fontFamily: FONT_FAMILY } } },
        stroke: { curve: 'smooth', width: 2 },
        fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.45, opacityTo: 0.05, stops: [20, 100, 100, 100] } },
        markers: { size: 3, hover: { size: 5 } },
        dataLabels: { enabled: false, style: { fontFamily: FONT_FAMILY } },
        legend: { position: 'top', horizontalAlign: 'right', fontFamily: FONT_FAMILY },
        tooltip: {
            shared: true,
            x: { format: 'dd MMM yyyy' },
            style: { fontFamily: FONT_FAMILY }
        }
    }
    new ApexCharts(chartEl, options).render()
}

function drawMeetupOrdersByStatus() {
    const chartEl = document.getElementById('meetup-orders-by-status-chart')
    if (!chartEl) return

    const series = parseData('meetup-orders-by-status-data')
    if (!series || series.length === 0) return

    const options = {
        series: series.map((d) => d.value),
        labels: series.map((d) => d.label),
        chart: {
            type: 'donut',
            width: '100%',
            height: 240,
            fontFamily: FONT_FAMILY,
            redrawOnParentResize: true,
            animations: { enabled: true },
        },
        colors: PALETTE,
        dataLabels: { enabled: false, style: { fontFamily: FONT_FAMILY } },
        legend: {
            position: 'bottom',
            fontFamily: FONT_FAMILY,
            formatter: (val, opts) => {
                const short = val.length > 15 ? val.slice(0, 15) + '...' : val
                return `${short} (${opts.w.globals.series[opts.seriesIndex]})`
            },
        },
        plotOptions: {
            pie: {
                donut: {
                    size: '65%',
                    labels: {
                        show: true,
                        total: {
                            show: true,
                            label: 'Total RSVPs',
                            fontFamily: FONT_FAMILY,
                            formatter: (w) => w.globals.seriesTotals.reduce((a, b) => a + b, 0),
                        },
                        value: {
                            fontFamily: FONT_FAMILY,
                        },
                    },
                },
            },
        },
        tooltip: { enabled: true, style: { fontFamily: FONT_FAMILY } },
    }
    new ApexCharts(chartEl, options).render()
}

function drawMeetupRevenueOverTime() {
    const chartEl = document.getElementById('meetup-revenue-over-time-chart')
    if (!chartEl) return

    const series = parseData('meetup-revenue-over-time-data')
    if (!series || series.length === 0) return

    const currency = chartEl.dataset.currency || ''
    const label = chartEl.dataset.label || 'Cumulative Revenue'

    const options = {
        series: [
            { name: label, data: series.map(d => ({ x: new Date(d.x).getTime(), y: d.revenue })) }
        ],
        chart: {
            type: 'area',
            width: '100%',
            height: 240,
            fontFamily: FONT_FAMILY,
            redrawOnParentResize: true,
            toolbar: { show: false },
            animations: { enabled: true }
        },
        colors: [PALETTE[1]],
        xaxis: {
            type: 'datetime',
            tooltip: { enabled: false },
            labels: {
                format: 'dd MMM',
                datetimeUTC: true,
                style: { fontFamily: FONT_FAMILY }
            }
        },
        yaxis: {
            min: 0,
            labels: {
                style: { fontFamily: FONT_FAMILY },
                formatter: (v) => {
                    return currency ? `${currency} ${v.toFixed(2)}` : v.toFixed(2)
                }
            }
        },
        stroke: { curve: 'smooth', width: 2 },
        fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0.05, stops: [20, 100, 100, 100] } },
        markers: { size: 3, hover: { size: 5 } },
        dataLabels: { enabled: false, style: { fontFamily: FONT_FAMILY } },
        legend: { position: 'top', horizontalAlign: 'right', fontFamily: FONT_FAMILY },
        tooltip: {
            shared: true,
            style: { fontFamily: FONT_FAMILY },
            x: { format: 'dd MMM yyyy' },
            y: {
                formatter: (v) => {
                    return currency ? `${currency} ${v.toFixed(2)}` : v.toFixed(2)
                }
            }
        }
    }
    new ApexCharts(chartEl, options).render()
}

function init() {
    if (typeof ApexCharts === 'undefined') return
    setTimeout(() => {
        drawMeetupOrdersOverTime()
        drawMeetupOrdersByStatus()
        drawMeetupRevenueOverTime()
    }, 50)
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
} else {
    init()
}
