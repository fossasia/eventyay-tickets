document.addEventListener('DOMContentLoaded', function () {
  var toggleBtn = document.getElementById('toggle-placeholders')
  var drawer = document.getElementById('placeholder-drawer')
  if (toggleBtn && drawer) {
    toggleBtn.addEventListener('click', function () {
      drawer.hidden = !drawer.hidden
    })
  }

  var radios = document.querySelectorAll('input[name="delivery_mode"]')
  var scheduleDiv = document.getElementById('delivery-schedule')
  var deliveryModeHidden = document.querySelector('input[name="delivery_mode"][type="hidden"]')
  radios.forEach(function (radio) {
    radio.addEventListener('change', function () {
      scheduleDiv.hidden = this.value !== 'later'
      if (deliveryModeHidden) {
        deliveryModeHidden.value = this.value
      }
    })
  })

  var sendImmediately = document.getElementById('id_send_immediately')
  var sendBtn = document.getElementById('send-btn')
  var sendLabelOutbox = sendBtn ? sendBtn.dataset.labelOutbox : ''
  var sendLabelImmediate = sendBtn ? sendBtn.dataset.labelImmediate : ''
  if (sendImmediately && sendBtn) {
    sendImmediately.addEventListener('change', function () {
      sendBtn.querySelector('.send-label').textContent =
        this.checked ? sendLabelImmediate : sendLabelOutbox
    })
  }

  var showBtnEl = document.getElementById('show-recipient-list')
  var recipientsUrl = showBtnEl ? showBtnEl.dataset.recipientsUrl : ''
  var countBadge = document.getElementById('recipient-count')
  var actionCount = document.getElementById('action-recipient-count')

  var FILTER_FIELDS = [
    'recipient_group', 'account_status', 'user_role', 'language',
    'event_status', 'created_after', 'created_before',
    'last_active_after', 'last_active_before',
    'selected_organisers', 'selected_events', 'selected_users',
    'exclude_admins', 'exclude_inactive', 'exclude_unconfirmed_email'
  ]

  function getFilterParams () {
    var form = document.querySelector('form')
    var data = new FormData(form)
    var params = new URLSearchParams()
    for (var pair of data.entries()) {
      if (FILTER_FIELDS.indexOf(pair[0]) !== -1) {
        params.append(pair[0], pair[1])
      }
    }
    return params
  }

  function updateRecipientCount () {
    if (!recipientsUrl) return
    var params = getFilterParams()
    fetch(recipientsUrl + '?' + params.toString())
      .then(function (r) { return r.json() })
      .then(function (data) {
        if (countBadge) countBadge.textContent = data.count + ' ' + countBadge.dataset.labelRecipients
        if (actionCount) actionCount.textContent = data.count
      })
      .catch(function () {})
  }

  FILTER_FIELDS.forEach(function (name) {
    var el = document.querySelector('[name="' + name + '"]')
    if (el) el.addEventListener('change', updateRecipientCount)
  })

  updateRecipientCount()

  var dialog = document.getElementById('recipient-list-dialog')
  var listBody = document.getElementById('recipient-list-body')
  var closeBtn = document.getElementById('close-recipient-dialog')
  var closeBtnBottom = document.getElementById('close-recipient-dialog-btn')

  function buildRecipientRow (r) {
    var tr = document.createElement('tr')
    var fields = [r.name || '', r.email, r.status || '', r.role || '', r.reason || '']
    fields.forEach(function (text) {
      var td = document.createElement('td')
      td.textContent = text
      tr.appendChild(td)
    })
    return tr
  }

  if (showBtnEl && dialog) {
    showBtnEl.addEventListener('click', function () {
      dialog.showModal()
      listBody.innerHTML = ''
      var loadingP = document.createElement('p')
      loadingP.className = 'text-muted'
      loadingP.textContent = listBody.dataset.loadingLabel
      listBody.appendChild(loadingP)

      var params = getFilterParams()
      params.set('show_list', '1')
      fetch(recipientsUrl + '?' + params.toString())
        .then(function (r) { return r.json() })
        .then(function (data) {
          listBody.innerHTML = ''
          if (!data.recipients || data.recipients.length === 0) {
            var emptyP = document.createElement('p')
            emptyP.className = 'text-muted'
            emptyP.textContent = listBody.dataset.emptyLabel
            listBody.appendChild(emptyP)
            return
          }

          var summary = document.createElement('p')
          summary.textContent = data.count + ' ' + countBadge.dataset.labelRecipients
          if (data.skipped > 0) {
            var warn = document.createElement('span')
            warn.className = 'text-warning'
            warn.textContent = ' (' + data.skipped + ' ' + listBody.dataset.skippedLabel + ')'
            summary.appendChild(warn)
          }
          listBody.appendChild(summary)

          var wrapper = document.createElement('div')
          wrapper.className = 'table-responsive'
          var table = document.createElement('table')
          table.className = 'table table-sm table-condensed'
          var thead = document.createElement('thead')
          var headerRow = document.createElement('tr')
          var cols = [
            listBody.dataset.colName,
            listBody.dataset.colEmail,
            listBody.dataset.colStatus,
            listBody.dataset.colRole,
            listBody.dataset.colReason
          ]
          cols.forEach(function (label) {
            var th = document.createElement('th')
            th.textContent = label
            headerRow.appendChild(th)
          })
          thead.appendChild(headerRow)
          table.appendChild(thead)

          var tbody = document.createElement('tbody')
          data.recipients.forEach(function (r) {
            tbody.appendChild(buildRecipientRow(r))
          })
          if (data.count > 100) {
            var truncRow = document.createElement('tr')
            var truncTd = document.createElement('td')
            truncTd.setAttribute('colspan', '5')
            truncTd.className = 'text-muted text-center'
            truncTd.textContent = listBody.dataset.truncatedLabel + ' ' + data.count
            truncRow.appendChild(truncTd)
            tbody.appendChild(truncRow)
          }
          table.appendChild(tbody)
          wrapper.appendChild(table)
          listBody.appendChild(wrapper)
        })
        .catch(function () {
          listBody.innerHTML = ''
          var errP = document.createElement('p')
          errP.className = 'text-danger'
          errP.textContent = listBody.dataset.errorLabel
          listBody.appendChild(errP)
        })
    })
    if (closeBtn) closeBtn.addEventListener('click', function () { dialog.close() })
    if (closeBtnBottom) closeBtnBottom.addEventListener('click', function () { dialog.close() })
  }

  var clearBtn = document.getElementById('clear-filters')
  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      var form = document.querySelector('form')
      FILTER_FIELDS.forEach(function (name) {
        var el = form.querySelector('[name="' + name + '"]')
        if (el) {
          if (el.type === 'checkbox') { el.checked = false } else { el.value = '' }
        }
      })
      updateRecipientCount()
    })
  }
})
