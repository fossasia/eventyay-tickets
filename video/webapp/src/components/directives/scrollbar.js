import { nextTick } from 'vue'
import Scrollbars from '../Scrollbars.vue'

// Usage: v-scrollbar.y or v-scrollbar.x or v-scrollbar.x.y
// This directive will mount the Scrollbars component as a wrapper around the element
export default {
  mounted(el, binding) {
    // Determine axes
    const x = binding.modifiers.x || false
    const y = binding.modifiers.y || false

    // Create a wrapper div for Scrollbars
    const wrapper = document.createElement('div')
    wrapper.className = 'c-scrollbars-directive-wrapper'
    el.parentNode.insertBefore(wrapper, el)
    wrapper.appendChild(el)

    // Create a Vue app instance for Scrollbars
    const app = el.__vueScrollbarsApp = Scrollbars.__createInstance({
      props: { x, y },
      slots: { default: () => el }
    })
    app.mount(wrapper)

    // Optionally, expose scrollbars instance for later use
    el.__vueScrollbars = app
  },
  unmounted(el) {
    if (el.__vueScrollbars) {
      el.__vueScrollbars.unmount()
      delete el.__vueScrollbars
    }
    if (el.__vueScrollbarsApp) {
      delete el.__vueScrollbarsApp
    }
  }
}

// Register globally in main.js:
// import scrollbarDirective from 'components/directives/scrollbar'
// app.directive('scrollbar', scrollbarDirective)
