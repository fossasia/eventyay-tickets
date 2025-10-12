export default {
  install(app) {
    // v-scrollbar.x.y -> set overflow-x/y = auto on the element
    app.directive('scrollbar', {
      // Vue 3 hooks: beforeMount + updated
      beforeMount(el, binding) {
        apply(el, binding)
      },
      updated(el, binding) {
        apply(el, binding)
      }
    })

    function apply(el, binding) {
      const modifiers = binding.modifiers || {}
      const hasX = !!modifiers.x
      const hasY = !!modifiers.y
      if (hasX) el.style.overflowX = 'auto'
      if (hasY) el.style.overflowY = 'auto'
      if (!hasX && !hasY) {
        // default: both axes
        el.style.overflow = 'auto'
      }
      // add class to enable any styling hooks
      el.classList.add('bunt-scrollbar')
    }
  }
}
