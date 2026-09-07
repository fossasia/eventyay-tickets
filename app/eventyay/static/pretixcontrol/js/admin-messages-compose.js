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
  radios.forEach(function (radio) {
    radio.addEventListener('change', function () {
      scheduleDiv.hidden = this.value !== 'later'
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

  var recipientsUrl = document.getElementById('show-recipient-list')
    ? document.getElementById('show-recipient-list').dataset.recipientsUrl
    : ''
  var countBadge = document.getElementById('recipient-count')
  var actionCount = document.getElementById('action-recipient-count')

  var FILTER_FIELDS = [
    'recipient_group', 'account_status', 'user_role', 'language',
    'event_status', 'created_after', 'created_before',
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

  ;['recipient_group', 'account_status', 'user_role', 'language',
    'event_status', 'exclude_admins', 'exclude_inactive', 'exclude_unconfirmed_email'
  ].forEach(function (name) {
    var el = document.querySelector('[name="' + name + '"]')
    if (el) el.addEventListener('change', updateRecipientCount)
  })

  updateRecipientCount()

  var showBtn = document.getElementById('show-recipient-list')
  var dialog = document.getElementById('recipient-list-dialog')
  var listBody = document.getElementById('recipient-list-body')
  var closeBtn = document.getElementById('close-recipient-dialog')
  var closeBtnBottom = document.getElementById('close-recipient-dialog-btn')

  if (showBtn && dialog) {
    showBtn.addEventListener('click', function () {
      dialog.showModal()
      listBody.innerHTML = '<p class="text-muted">' + listBody.dataset.loadingLabel + '</p>'
      var params = getFilterParams()
      params.set('show_list', '1')
      fetch(recipientsUrl + '?' + params.toString())
        .then(function (r) { return r.json() })
        .then(function (data) {
          if (!data.recipients || data.recipients.length === 0) {
            listBody.innerHTML = '<p class="text-muted">' + listBody.dataset.emptyLabel + '</p>'
            return
          }
          var html = '<p>' + data.count + ' ' + countBadge.dataset.labelRecipients
          if (data.skipped > 0) {
            html += ' <span class="text-warning">(' + data.skipped + ' ' + listBody.dataset.skippedLabel + ')</span>'
          }
          html += '</p>'
          html += '<div class="table-responsive"><table class="table table-sm table-condensed"><thead><tr>'
          html += '<th>' + listBody.dataset.colName + '</th>'
          html += '<th>' + listBody.dataset.colEmail + '</th>'
          html += '<th>' + listBody.dataset.colStatus + '</th>'
          html += '<th>' + listBody.dataset.colRole + '</th>'
          html += '<th>' + listBody.dataset.colReason + '</th>'
          html += '</tr></thead><tbody>'
          data.recipients.forEach(function (r) {
            html += '<tr><td>' + (r.name || '') + '</td><td>' + r.email + '</td>'
            html += '<td>' + (r.status || '') + '</td><td>' + (r.role || '') + '</td>'
            html += '<td>' + (r.reason || '') + '</td></tr>'
          })
          if (data.count > 100) {
            html += '<tr><td colspan="5" class="text-muted text-center">' + listBody.dataset.truncatedLabel + ' ' + data.count + '</td></tr>'
          }
          html += '</tbody></table></div>'
          listBody.innerHTML = html
        })
        .catch(function () {
          listBody.innerHTML = '<p class="text-danger">' + listBody.dataset.errorLabel + '</p>'
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
