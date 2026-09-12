document.addEventListener('DOMContentLoaded', function () {
  var form = document.querySelector('[data-global-plugins-form]')
  if (!form) return

  var tabField = form.querySelector('[data-active-tab-field]')
  var tables = form.querySelectorAll('[data-global-plugins-table]')

  var tabLinks = document.querySelectorAll('[data-global-plugins-tabs] a[data-tab-key]')
  tabLinks.forEach(function (link) {
    link.addEventListener('click', function () {
      if (tabField) tabField.value = link.getAttribute('data-tab-key')
    })
  })

  tables.forEach(function (table) {
    var rows = table.querySelectorAll('[data-plugin-row]')

    rows.forEach(function (row) {
      if (row.getAttribute('data-plugin-type') === 'platform') return

      var active = row.querySelector('[data-col="active"]')
      if (!active) return

      var deps = row.querySelectorAll(
        '[data-col="enable_by_default"], [data-col="show_in_organizer_list"]'
      )

      function syncRow() {
        deps.forEach(function (dep) {
          dep.disabled = !active.checked
          if (!active.checked) dep.checked = false
        })
      }

      syncRow()
      active.addEventListener('change', syncRow)
    })
  })

  form.addEventListener('submit', function (event) {
    if (form.dataset.confirmBypass === '1') {
      form.dataset.confirmBypass = ''
      return
    }

    var warnings = []
    var rows = form.querySelectorAll('[data-plugin-row]')
    rows.forEach(function (row) {
      var active = row.querySelector('[data-col="active"]')
      if (!active) return
      var wasActive = active.getAttribute('data-was-active') === '1'
      if (wasActive && !active.checked) {
        var name = row.getAttribute('data-plugin-name') || active.name
        var count = parseInt(row.getAttribute('data-usage-count') || '0', 10)
        if (count > 0) {
          warnings.push(name + ' (used by ' + count + ' event' + (count !== 1 ? 's' : '') + ')')
        } else {
          warnings.push(name)
        }
      }
    })

    if (!warnings.length) return

    event.preventDefault()
    event.stopPropagation()

    var message = 'The following plugins will be deactivated and removed from all events:\n\n'
    message += warnings.join('\n')
    message += '\n\nDo you want to continue?'

    if (typeof window.showConfirmDialog === 'function') {
      window.showConfirmDialog({
        title: 'Deactivate plugins',
        message: message,
        confirmLabel: 'Deactivate',
        confirmClass: 'btn-danger'
      }).then(function (confirmed) {
        if (confirmed) {
          form.dataset.confirmBypass = '1'
          if (typeof form.requestSubmit === 'function') {
            form.requestSubmit()
          } else {
            form.submit()
          }
        }
      })
    } else if (window.confirm(message)) {
      form.dataset.confirmBypass = '1'
      form.submit()
    }
  }, true)
})
