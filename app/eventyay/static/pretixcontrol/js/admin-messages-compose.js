document.addEventListener('DOMContentLoaded', function () {
  var radios = document.querySelectorAll('input[name="delivery_mode"][type="radio"]')
  var scheduleDiv = document.getElementById('delivery-schedule')

  function syncDeliverySchedule (value) {
    if (scheduleDiv) scheduleDiv.hidden = value !== 'later'
  }

  radios.forEach(function (radio) {
    radio.addEventListener('change', function () {
      syncDeliverySchedule(this.value)
    })
  })

  var checkedRadio = document.querySelector('input[name="delivery_mode"][type="radio"]:checked')
  if (checkedRadio) syncDeliverySchedule(checkedRadio.value)

  var sendImmediately = document.getElementById('id_send_immediately')
  var sendBtn = document.getElementById('send-btn')
  if (sendImmediately && sendBtn) {
    var sendLabelOutbox = sendBtn.dataset.labelOutbox || ''
    var sendLabelImmediate = sendBtn.dataset.labelImmediate || ''
    sendImmediately.addEventListener('change', function () {
      var label = sendBtn.querySelector('.send-label')
      if (label) {
        label.textContent = this.checked ? sendLabelImmediate : sendLabelOutbox
      }
    })
  }
})
