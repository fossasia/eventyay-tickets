export default {
  install(app) {
    const apply = (el) => {
      const rect = el.getBoundingClientRect()
      el.style.setProperty('--dynamic-line-clamp', Math.floor(rect.height / (14 * 1.4)))
    }

    app.directive('dynamic-line-clamp', {
      mounted(el) {
        apply(el)
      },
      updated(el) {
        apply(el)
      }
    })
  }
}
