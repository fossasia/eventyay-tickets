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
import scrollbarDirective from './components/directives/scrollbar'
import 'styles/global.styl'
import '@mdi/font/css/materialdesignicons.css'
// import '@pretalx/schedule/style'
import i18n, { init as i18nInit } from 'i18n'
import { emojiPlugin } from 'lib/emoji'
import features from 'features'
import config from 'config'
import { hasOrganizerTraits } from 'lib/traitGrants'
import { loadThemeConfig } from 'theme'
import 'webrtc-adapter'

function ensureWebsiteFontsLoaded() {
  if (document.head.querySelector('link[data-eventyay-fonts]')) {
    return
  }

  const fontsLink = document.createElement('link')
  fontsLink.rel = 'stylesheet'
  fontsLink.href = '/static/common/css/_fonts.css'
  fontsLink.dataset.eventyayFonts = '1'
  document.head.appendChild(fontsLink)
}

function ensureEventSettingsCssLoaded() {
  const url = config.theme?.typography?.settings_css_url
  if (!url) return
  if (document.head.querySelector(`link[data-eventyay-settings-css="${url}"]`)) {
    return
  }

  const settingsCssLink = document.createElement('link')
  settingsCssLink.rel = 'stylesheet'
  settingsCssLink.href = url
  settingsCssLink.dataset.eventyaySettingsCss = url
  document.head.appendChild(settingsCssLink)
}

async function init({ token, inviteToken }) {
  ensureWebsiteFontsLoaded()
  ensureEventSettingsCssLoaded()
  await loadThemeConfig()
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
  app.use(scrollbarDirective)
  // Initialize i18n and theme
  await i18nInit(app)
  app.config.globalProperties.$features = features

  // Handle base path for routing early so RouterLink can resolve named routes
  const basePath = config.basePath || ''
  let relativePath = location.pathname.replace(basePath, '')
  const isOrganizerArea = Boolean(window.eventyay?.isOrganizerArea)
  if (isOrganizerArea) {
    try {
      sessionStorage.setItem('video_auth_mode', 'organizer')
      localStorage.removeItem('token')
    } catch (e) {}
  } else if (token) {
    try {
      sessionStorage.setItem('video_auth_mode', 'jwt')
      localStorage.token = token
    } catch (e) {}
  }

  const isJwtAuthMode = sessionStorage.getItem('video_auth_mode') === 'jwt'
  const isOrganizerAuthMode = sessionStorage.getItem('video_auth_mode') === 'organizer'

  const activeToken = token || (
    !isOrganizerArea && !isOrganizerAuthMode && (isJwtAuthMode || !window.eventyay?.hasOrganiserPermissions) && localStorage.token
      ? localStorage.token
      : null
  )

  let tokenTraits = []
  if (activeToken) {
    try {
      tokenTraits = jwtDecode(activeToken)?.traits || []
    } catch (e) { /* ignore */ }
  }

  const hasToken = Boolean(activeToken)
  const isOrganizer = isOrganizerArea || (hasToken ? hasOrganizerTraits(tokenTraits) : Boolean(window.eventyay?.hasOrganiserPermissions))

  if (!relativePath || relativePath === '/') {
    if (isOrganizerArea) {
      relativePath = '/event'
    } else {
      relativePath = '/'
    }
  } else if (!isOrganizer) {
    if (relativePath.startsWith('/event') || relativePath === 'event') {
      relativePath = '/'
    } else if (relativePath.includes('/manage')) {
      relativePath = relativePath.replace(/\/manage$/, '') || '/'
    }
  }

  // Ensure router's current route is set before mounting the app so that
  // named routes which depend on parent params (like `worldName`) can be
  // resolved when components (RouterLink) are rendered.
  await router.replace(relativePath).catch(() => {})

  const route = router.resolve(relativePath)
  const anonymousRoomId = route?.name === 'standalone:anonymous' ? route?.params?.roomId : null

  window.vapp = app.mount('#app')

  app.config.errorHandler = (error, vm, info) => {
    console.error('[VUE] ', info, vm, error)
  }

  store.commit('setUserLocale', i18n.resolvedLanguage)
  store.dispatch('updateUserTimezone', localStorage.userTimezone || moment.tz.guess())

  if (activeToken) {
    localStorage.token = activeToken
    if (token) {
      router.replace(relativePath)
    }
    store.dispatch('login', { token: activeToken })
  } else if (isOrganizerArea || window.eventyay?.hasOrganiserPermissions) {
    localStorage.removeItem('token')
    router.replace(relativePath)
    store.dispatch('login', {})
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
  if (store.state.token && jwtDecode(store.state.token).traits?.includes?.('-kiosk')) {
    store.watch(
      state => state.user,
      (user) => {
        const roomId = user?.profile?.room_id
        if (!roomId) return
        router.replace({ name: 'standalone:kiosk', params: { roomId: String(roomId) } })
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

  store.dispatch('notifications/startExternalPolling')
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
if ('serviceWorker' in navigator) {
	// Do not aggressively unregister all, just skip if none (avoid InvalidStateError)
	try {
		navigator.serviceWorker.getRegistrations().then((registrations) => {
			for (const registration of registrations) {
				// only unregister legacy registrations whose scope does not match current basePath
				if (registration.scope && !registration.scope.includes(config.basePath)) {
					registration.unregister()
				}
			}
		}).catch(() => {})
	} catch (e) { /* ignore */ }
}
