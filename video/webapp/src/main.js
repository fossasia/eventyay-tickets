/* global RELEASE */
import { createApp } from 'vue'
import { RouterView } from 'vue-router'
import jwtDecode from 'jwt-decode'
import Buntpapier from 'buntpapier'
import VueVirtualScroller from 'vue-virtual-scroller'
import 'vue-virtual-scroller/dist/vue-virtual-scroller.css'
import { v4 as uuid } from 'uuid'
import moment from 'lib/timetravelMoment'
import router from 'router'
import store from 'store'
import Scrollbars from 'components/Scrollbars'
import LinkIconButton from 'components/link-icon-button'
import MediaQueries from 'components/mixins/media-queries'
import dynamicLineClamp from './components/directives/dynamic-line-clamp'
import 'styles/global.styl'
import 'roboto-fontface'
import 'roboto-fontface/css/roboto-condensed/roboto-condensed-fontface.css'
import '@mdi/font/css/materialdesignicons.css'
import 'quill/dist/quill.core.css'
import '@pretalx/schedule/dist/schedule.css'
import 'styles/quill.styl'
import i18n, { init as i18nInit } from 'i18n'
import { emojiPlugin } from 'lib/emoji'
import features from 'features'
import config from 'config'
import theme, { computeForegroundSidebarColor, getThemeConfig } from 'theme'

async function init({ token, inviteToken }) {
  const app = createApp(RouterView)
  
  // Register plugins and components
  app.use(store)
  app.use(router)
  app.use(Buntpapier)
  app.use(VueVirtualScroller)
  app.component('scrollbars', Scrollbars)
  app.component('link-icon-button', LinkIconButton)
  app.use(MediaQueries)
  app.use(emojiPlugin)
  app.use(dynamicLineClamp)
  
  // Initialize i18n and theme
  await i18nInit(app)
  app.config.globalProperties.$features = features
  
  try {
    await setThemeConfig()
  } catch (error) {
    console.error('Error loading theme config: ', error)
  }

  // Set error handler before mounting
  app.config.errorHandler = (error, vm, info) => {
    console.error('[VUE] ', info, vm, error)
  }
  // Mount app
  window.vapp = app.mount('#app')

  // Set locale and timezone
  store.commit('setUserLocale', i18n.resolvedLanguage)
  store.dispatch('updateUserTimezone', localStorage.userTimezone || moment.tz.guess())

  // Handle base path for routing
  const basePath = config.basePath || ''
  let relativePath = location.pathname.replace(basePath, '') || '/'

  // Handle authentication
  // Vue Router 4: resolve returns the route directly
  const route = router.resolve(relativePath)
  const anonymousRoomId = route.name === 'standalone:anonymous' ? route.params.roomId : null

  if (token) {
    localStorage.token = token
    router.replace(relativePath)
    store.dispatch('login', { token })
  } else if (localStorage.token) {
    store.dispatch('login', { token: localStorage.token })
  } else if (inviteToken && anonymousRoomId) {
    const clientId = uuid()
    localStorage[`clientId:room:${anonymousRoomId}`] = clientId
    router.replace(relativePath)
    store.dispatch('login', { clientId, inviteToken })
  } else if (anonymousRoomId && localStorage[`clientId:room:${anonymousRoomId}`]) {
    const clientId = localStorage[`clientId:room:${anonymousRoomId}`]
    store.dispatch('login', { clientId })
  } else {
    console.warn('No token found, logging in anonymously')
    let clientId = localStorage.clientId || uuid()
    localStorage.clientId = clientId
    store.dispatch('login', { clientId })
  }

  // Handle kiosk mode
  if (store.state.token && jwtDecode(store.state.token).traits.includes('-kiosk')) {
    store.watch(
      state => state.user,
      ({ profile }) => {
        router.replace({ name: 'standalone:kiosk', params: { roomId: profile.room_id } })
      },
      { deep: true }
    )
  }

  // Connect to store and set up intervals
  store.dispatch('connect')
  setTimeout(() => {
    store.commit('updateNow')
    setInterval(() => store.commit('updateNow'), 60000)
  }, 60000 - (Date.now() % 60000))
  
  setInterval(() => store.dispatch('notifications/pollExternals'), 1000)
  window.__venueless__release = RELEASE

  // Handle PWA installation
  window.addEventListener('beforeinstallprompt', (event) => {
    console.log('Install prompt', event)
  })
}

// Theme configuration
async function setThemeConfig() {
  const themeData = await getThemeConfig()
  theme.logo = themeData.logo
  theme.identicons = themeData.identicons
  theme.colors = themeData.colors
  theme.streamOfflineImage = themeData.streamOfflineImage
  computeForegroundSidebarColor(themeData.colors)
}

// Extract token from URL
const hashParams = new URLSearchParams(window.location.hash.substring(1))
const token = hashParams.get('token')
const inviteToken = hashParams.get('invite')

// Handle external auth
if (config.externalAuthUrl && !token) {
  window.location = config.externalAuthUrl
} else {
  init({ token, inviteToken })
}

// Clean up old service workers
navigator.serviceWorker?.getRegistrations().then((registrations) => {
  for (const registration of registrations) {
    console.warn('Removed old service worker')
    registration.unregister()
  }
})