function hideOptions (state) {
  if (!state.id || !state.element) return state.text
  if (state.element && state.element.classList.contains("hidden")) return
  return state.text
}
document.addEventListener("DOMContentLoaded", function() {
  document.querySelectorAll(".select2").forEach(select => {
    $(select).select2({
      placeholder: select.title,
      templateResult: hideOptions,
      allowClear: !select.required && !select.multiple,
    })
  })
})
