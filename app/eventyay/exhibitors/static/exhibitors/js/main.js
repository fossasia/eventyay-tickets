import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import axios from 'axios'

// Import components
import ExhibitorDirectory from './views/ExhibitorDirectory.vue'
import ExhibitorDetail from './views/ExhibitorDetail.vue'
import ExhibitorList from './components/ExhibitorList.vue'

// Import store
import { useExhibitorStore } from './store/exhibitors'

// Import styles
import '../css/exhibitors.css'

// Configure axios defaults
axios.defaults.xsrfCookieName = 'csrftoken'
axios.defaults.xsrfHeaderName = 'X-CSRFToken'
axios.defaults.withCredentials = true

// Router configuration
const routes = [
  {
    path: '/',
    name: 'exhibitors:directory',
    component: ExhibitorDirectory,
    meta: { title: 'Exhibitor Directory' }
  },
  {
    path: '/:booth_id',
    name: 'exhibitors:detail',
    component: ExhibitorDetail,
    props: true,
    meta: { title: 'Exhibitor Details' }
  }
]

const router = createRouter({
  history: createWebHistory('/exhibitors/'),
  routes
})

// Update page title on route change
router.beforeEach((to, from, next) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - ENext`
  }
  next()
})

// Create Pinia store
const pinia = createPinia()

// Global error handler
const handleGlobalError = (error) => {
  console.error('Global error:', error)
  
  // Show user-friendly error message
  const store = useExhibitorStore()
  store.showNotification({
    type: 'error',
    message: 'An unexpected error occurred. Please try again.'
  })
}

// Initialize Vue app when DOM is ready
function initializeExhibitorApp() {
  // Check if we're on an exhibitor page
  const exhibitorContainer = document.getElementById('exhibitor-vue-app')
  if (!exhibitorContainer) {
    return
  }

  // Create Vue app
  const app = createApp({
    template: '<router-view />'
  })

  // Install plugins
  app.use(pinia)
  app.use(router)

  // Global error handling
  app.config.errorHandler = handleGlobalError
  window.addEventListener('unhandledrejection', (event) => {
    handleGlobalError(event.reason)
  })

  // Global properties
  app.config.globalProperties.$http = axios
  app.config.globalProperties.$t = window.$t || ((key) => key)

  // Global components (if needed)
  app.component('ExhibitorList', ExhibitorList)

  // Mount the app
  app.mount('#exhibitor-vue-app')

  console.log('Exhibitor Vue app initialized')
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeExhibitorApp)
} else {
  initializeExhibitorApp()
}

// Export for potential external use
export { router, pinia, useExhibitorStore }

// Initialize standalone components for non-SPA pages
function initializeStandaloneComponents() {
  // Initialize ExhibitorList components on regular Django pages
  const exhibitorLists = document.querySelectorAll('[data-exhibitor-list]')
  
  exhibitorLists.forEach((element) => {
    const props = {
      eventId: element.dataset.eventId,
      featured: element.dataset.featured === 'true',
      limit: element.dataset.limit ? parseInt(element.dataset.limit) : null
    }
    
    const app = createApp(ExhibitorList, props)
    app.use(pinia)
    app.config.globalProperties.$http = axios
    app.mount(element)
  })
}

// Initialize standalone components
initializeStandaloneComponents()

// Make components available globally for Django templates
window.ExhibitorComponents = {
  ExhibitorList,
  ExhibitorDirectory,
  ExhibitorDetail,
  initializeStandaloneComponents
}