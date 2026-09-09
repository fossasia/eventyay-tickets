/**
 * Client-side organizer dashboard filters (no page reload).
 */

function readJsonScript(id) {
  const el = document.getElementById(id)
  if (!el) return null
  try {
    return JSON.parse(el.textContent)
  } catch (err) {
    console.error('organizer-dashboard-filters: failed to parse', id, err)
    return null
  }
}

function setQueryParam(param, value) {
  const url = new URL(window.location.href)
  if (value) {
    url.searchParams.set(param, value)
  } else {
    url.searchParams.delete(param)
  }
  url.searchParams.delete('refresh')
  window.history.replaceState({}, '', url)
}

function syncSelects(selector, value) {
  document.querySelectorAll(selector).forEach((select) => {
    if (select.value !== value) {
      select.value = value
    }
  })
}

function applyRevenueFilter(currency) {
  const valueEl = document.querySelector('[data-od-revenue-value]')
  const metaEl = document.getElementById('od-revenue-filter-data')
  const options = readJsonScript('od-revenue-options') || []
  const allLabel = metaEl?.dataset.allLabel || ''

  if (valueEl) {
    if (!currency) {
      valueEl.textContent = allLabel
    } else {
      const match = options.find((row) => row.currency === currency)
      valueEl.textContent = match ? match.label : allLabel
    }
  }

  const table = document.querySelector('[data-od-top-events-table]')
  const empty = document.querySelector('[data-od-top-events-empty]')
  if (table) {
    let visible = 0
    table.querySelectorAll('tbody tr[data-currency]').forEach((row) => {
      const show = !currency || row.dataset.currency === currency
      row.hidden = !show
      if (show) visible += 1
    })
    table.classList.toggle('od-is-hidden', visible === 0)
    if (empty) {
      empty.classList.toggle('od-is-hidden', visible > 0)
    }
  }

  syncSelects('[data-od-revenue-filter]', currency)
  setQueryParam('revenue_currency', currency)
}

function bindRevenueFilters() {
  const selects = document.querySelectorAll('[data-od-revenue-filter]')
  if (!selects.length) return

  const initial = new URL(window.location.href).searchParams.get('revenue_currency') || ''
  applyRevenueFilter(initial)

  selects.forEach((select) => {
    select.addEventListener('change', () => {
      applyRevenueFilter(select.value || '')
    })
  })
}

function projectAttendanceSeries(dailyByEvent, dateLabels, eventId) {
  const eventIds = eventId
    ? [String(eventId)]
    : Object.keys(dailyByEvent || {})

  return (dateLabels || []).map((day) => {
    let orders = 0
    let registrations = 0
    eventIds.forEach((id) => {
      const bucket = dailyByEvent?.[id]?.[day] || {}
      orders += bucket.orders || 0
      registrations += bucket.registrations || 0
    })
    return { x: day, orders, registrations }
  })
}

function bindAttendanceFilter() {
  const select = document.querySelector('[data-od-attendance-filter]')
  if (!select) return

  select.addEventListener('change', () => {
    const eventId = select.value || ''
    setQueryParam('attendance_event', eventId)
    if (typeof window.odUpdateAttendanceChart === 'function') {
      const daily = readJsonScript('od-attendance-daily') || {}
      const dates = readJsonScript('od-attendance-dates') || []
      const series = projectAttendanceSeries(daily, dates, eventId)
      window.odUpdateAttendanceChart(series)
    }
  })
}

function initDashboardFilters() {
  bindRevenueFilters()
  bindAttendanceFilter()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDashboardFilters)
} else {
  initDashboardFilters()
}
