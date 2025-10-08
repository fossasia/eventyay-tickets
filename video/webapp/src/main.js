/* global RELEASE */
import { createApp } from 'vue'
import { RouterView } from 'vue-router'
import { jwtDecode } from 'jwt-decode'
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
import '@pretalx/schedule/style'
import 'styles/quill.styl'
import i18n, { init as i18nInit } from 'i18n'
import { emojiPlugin } from 'lib/emoji'
import features from 'features'
import config from 'config'
import theme, { computeForegroundSidebarColor, getThemeConfig, DEFAULT_COLORS, DEFAULT_LOGO, DEFAULT_IDENTICONS, themeVariables } from 'theme'

async function setThemeConfig() {
    const themeData = await getThemeConfig()
    theme.logo = themeData.logo
    theme.identicons = themeData.identicons
    theme.colors = themeData.colors
    theme.streamOfflineImage = themeData.streamOfflineImage
    computeForegroundSidebarColor(themeData.colors)
    // Inject theme variables into DOM
    if (typeof window !== 'undefined' && document && document.documentElement) {
      for (const [key, value] of Object.entries(themeVariables)) {
        document.documentElement.style.setProperty(key, value)
      }
    }
}

async function init({ token, inviteToken }) {
  await setThemeConfig()
  const app = createApp(RouterView)
  app.use(store)
  app.use(router)
  app.use(Buntpapier)
  app.use(VueVirtualScroller)
  // Avoid duplicate global registrations if init is called multiple times
  if (!app._context.components?.Scrollbars) app.component('Scrollbars', Scrollbars)
  if (!app._context.components?.['link-icon-button']) app.component('link-icon-button', LinkIconButton)
  app.use(MediaQueries)
  app.use(emojiPlugin)
  app.use(dynamicLineClamp)
  // Initialize i18n and theme
  await i18nInit(app)
  app.config.globalProperties.$features = features

  // Handle base path for routing early so RouterLink can resolve named routes
  const basePath = config.basePath || ''
  let relativePath = location.pathname.replace(basePath, '')
  if (!relativePath) {
    relativePath = '/'
  }

  // Ensure router's current route is set before mounting the app so that
  // named routes which depend on parent params (like `worldName`) can be
  // resolved when components (RouterLink) are rendered.
  await router.replace(relativePath).catch(() => {})

  const route = router.resolve(relativePath).route
  const anonymousRoomId = route?.name === 'standalone:anonymous' ? route?.params?.roomId : null

  window.vapp = app.mount('#app')

  app.config.errorHandler = (error, vm, info) => {
    console.error('[VUE] ', info, vm, error)
  }

  store.commit('setUserLocale', i18n.resolvedLanguage)
  store.dispatch('updateUserTimezone', localStorage.userTimezone || moment.tz.guess())

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
    console.warn('no token found, login in anonymously')
    let clientId = localStorage.clientId
    if (!clientId) {
      clientId = uuid()
      localStorage.clientId = clientId
    }
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

  window.addEventListener('beforeinstallprompt', function (event) {
    console.log('Install prompt', event)
  })
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
    registration.unregister()
  }
})
