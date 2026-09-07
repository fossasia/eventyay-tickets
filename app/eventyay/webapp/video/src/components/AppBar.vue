<template lang="pug">
.c-app-bar
	.left
		button.navbar-toggle-sidebar.navbar-toggle(
			v-if="showActions",
			type="button",
			@click.stop="$emit('toggleSidebar')",
			:aria-label="toggleNavigationLabel"
		)
			i.fa.fa-bars.fa-lg(aria-hidden="true")
		a.navbar-brand(:href="platformHomeUrl", :class="{anonymous: isAnonymous}")
			img(src="/eventyay-logo.svg", alt="eventyay")
			span.brand-text eventyay
	.nav-actions
		.admin-session-actions(v-if="showAdminModeStart || showAdminModeEnd")
			button.admin-mode-btn(
				v-if="showAdminModeStart"
				type="button"
				@click="startAdminSession"
				:aria-label="$t('Admin mode')"
			)
				i.fa.fa-id-card(aria-hidden="true")
				span {{ $t('Admin mode') }}
			button.admin-mode-btn.admin-mode-btn--end(
				v-if="showAdminModeEnd"
				type="button"
				@click="endAdminSession"
				:aria-label="$t('End admin session')"
			)
				i.fa.fa-id-card(aria-hidden="true")
				span {{ $t('End admin session') }}
		.language-menu(v-if="languages.length", ref="languageMenuEl")
			button.language-toggle(
				type="button"
				:aria-label="languageToggleLabel"
				:aria-expanded="String(languageMenuOpen)"
				aria-haspopup="menu"
				:class="{open: languageMenuOpen}"
				@click.stop="toggleLanguageMenu"
			)
				i.fa.fa-globe(aria-hidden="true")
				span.current-locale(aria-hidden="true") {{ currentLanguageCode }}
				span.sr-only {{ currentLanguageLabel }}
				i.fa.fa-caret-down(aria-hidden="true")
			transition(name="dropdown-reveal")
				.language-dropdown(v-if="languageMenuOpen", role="menu")
					button.language-option(
						v-for="option in languages"
						:key="option.code"
						type="button"
						role="menuitem"
						:class="{active: option.code === currentLanguage}"
						@click="selectLanguage(option.code)"
					) {{ option.nativeLabel }}
		.user-section(v-if="showUser")
			.user-menu(ref="userMenuEl")
				div.user-profile(:class="{open: profileMenuOpen}", @click.stop="toggleProfileMenu")
					avatar(v-if="!isAnonymous", :user="user", :size="32")
					span.display-name(v-if="!isAnonymous") {{ user.profile.display_name }}
					span.display-name(v-else) {{ $t('anonymous') }}
					span.user-caret(role="button", :aria-expanded="String(profileMenuOpen)", aria-haspopup="true", tabindex="0", @click.stop="toggleProfileMenu", @keydown.enter.prevent="toggleProfileMenu", @keydown.space.prevent="toggleProfileMenu", :class="{open: profileMenuOpen}")
				transition(name="dropdown-reveal")
					.profile-dropdown(v-if="profileMenuOpen", role="menu", @click.stop)
						.visibility-row(v-if="!isAnonymous")
							span.visibility-label {{ $t('Profile visibility') }}
							span.visibility-badge(:class="isPublic ? 'badge-public' : 'badge-private'") {{ isPublic ? $t('Public') : $t('Private') }}
						div.menu-separator(v-if="!isAnonymous")
						template(v-for="item in menuItems", :key="item.key")
							div.menu-separator(v-if="item.separatorBefore")
							a.menu-item(:href="getItemHref(item)", role="menuitem", @click.prevent="onMenuItem(item)")
								span.menu-item-icon(v-if="item.icon" aria-hidden="true")
									i(:class="iconClasses[item.icon]")
								span.menu-item-label {{ item.label }}
</template>
<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { jwtDecode } from 'jwt-decode'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import Avatar from 'components/Avatar'
import config from 'config'
import i18n from 'i18n'
import { resolveLanguageOptions } from 'locales'

const props = defineProps({
	showActions: {
		type: Boolean,
		default: true
	},
	showUser: {
		type: Boolean,
		default: false
	}
})

const ICON_CLASSES = {
	dashboard: 'fa fa-tachometer',
	orders: 'fa fa-shopping-cart',
	events: 'fa fa-calendar',
	organizers: 'fa fa-users',
	account: 'fa fa-user',
	admin: 'fa fa-cog',
	logout: 'fa fa-sign-out',
	tickets: 'fa fa-ticket',
	control: 'fa fa-cogs',
	profile: 'fa fa-user-circle'
}

const PROFILE_MENU_ITEM_DEFS = [
	{ key: 'dashboard', icon: 'dashboard', externalPath: 'common/' },
	{ key: 'orders', externalPath: 'common/orders/', icon: 'orders' },
	{ key: 'sessions', externalPath: 'common/sessions/', icon: 'tickets' },
	{ key: 'events', externalPath: 'common/events/', icon: 'events' },
	{ key: 'organizers', externalPath: 'common/organizers/', icon: 'organizers' },
	{ key: 'profile', route: { name: 'preferences' }, separatorBefore: true, icon: 'profile' },
	{ key: 'account', externalPath: 'common/account/general', icon: 'account' },
	{ key: 'admin', externalPath: 'admin/', icon: 'admin', adminOnly: true },
	{ key: 'logout', action: 'logout', icon: 'logout', separatorBefore: true }
]

const emit = defineEmits(['toggleSidebar'])

const store = useStore()
const router = useRouter()

const user = computed(() => store.state.user)
const world = computed(() => store.state.world)
const token = computed(() => store.state.token)

const isPublic = computed(() => !!user.value?.show_publicly)

function decodeTokenPayload(rawToken) {
	if (!rawToken) return null
	try {
		return jwtDecode(rawToken)
	} catch (error) {
		if (process.env.NODE_ENV === 'development') {
			console.error('Failed to decode JWT token:', error)
		}
		return null
	}
}

const tokenPayload = computed(() => decodeTokenPayload(token.value || localStorage.getItem('token')))

const isAdminMode = computed(() => {
	if (typeof window !== 'undefined' && window.eventyay?.hasStaffSession != null) {
		return Boolean(window.eventyay.hasStaffSession)
	}
	const decoded = tokenPayload.value
	return Array.isArray(decoded?.traits) && decoded.traits.includes('admin')
})

const canStartStaffSession = computed(() => {
	if (typeof window !== 'undefined' && window.eventyay?.isStaff != null) {
		return Boolean(window.eventyay.isStaff)
	}
	const p = tokenPayload.value
	return p?.is_staff === true || p?.is_superuser === true
})

const isStaffSessionActive = isAdminMode

const isAdminRoute = computed(() => {
	const name = router.currentRoute.value?.name
	return typeof name === 'string' && (name.startsWith('admin') || name === 'organizer' || name === 'room:manage')
})

const hasOrganiserPermissions = computed(() => {
	return (
		isAdminMode.value ||
		store.getters.hasPermission('world:users.list') ||
		store.getters.hasPermission('world:update') ||
		store.getters.hasPermission('world:announce') ||
		store.getters.hasPermission('room:update') ||
		store.getters.hasPermission('world:kiosks.manage')
	)
})

const eventRouting = computed(() => store.getters.eventRouting)

const isOrganizerNavVisible = computed(() => {
	return isAdminRoute.value || Boolean(window.eventyay?.isOrganizerArea)
})

const platformHomeUrl = computed(() => window.eventyay?.platformHomeUrl || '/')
const homeUrl = computed(() => window.eventyay?.homeUrl || null)
const ticketUrl = computed(() => window.eventyay?.ticketUrl || null)
const talkUrl = computed(() => window.eventyay?.talkUrl || null)
const videoUrl = computed(() => window.eventyay?.videoUrl || router.resolve({ name: 'organizer' }).href)

const publicEventUrl = computed(() => {
	if (window.eventyay?.eventUrl) {
		return window.eventyay.eventUrl
	}
	const { organizer, event } = eventRouting.value || {}
	if (organizer && event) {
		const base = buildBaseSansVideo()
		return `${base}${organizer}/${event}/`
	}
	return buildBaseSansVideo()
})

const showAdminModeStart = computed(() => {
	return canStartStaffSession.value && !isStaffSessionActive.value
})

const showAdminModeEnd = computed(() => {
	return isStaffSessionActive.value
})

const isAnonymous = computed(() => Object.keys(user.value.profile || {}).length === 0)

function buildMenuExternalHref(item) {
	const base = buildBaseSansVideo()
	return base + item.externalPath
}

const brandLogoUrl = computed(() => {
	const basePath = config?.basePath ?? ''
	if (!basePath || basePath === '/') {
		return '/eventyay-video-logo.png'
	}
	const normalized = basePath.endsWith('/') ? basePath.slice(0, -1) : basePath
	return `${normalized}/eventyay-video-logo.png`
})

const profileMenuOpen = ref(false)
const languageMenuOpen = ref(false)
const userLocale = computed(() => store.state.userLocale)
const menuItems = computed(() => {
	userLocale.value
	const labels = {
		dashboard: i18n.t('Dashboard'),
		orders: i18n.t('My Orders'),
		sessions: i18n.t('My Sessions'),
		events: i18n.t('My Events'),
		organizers: i18n.t('Organizers'),
		profile: i18n.t('Profile'),
		account: i18n.t('Account'),
		admin: i18n.t('Admin'),
		logout: i18n.t('Logout'),
	}
	return PROFILE_MENU_ITEM_DEFS
		.filter(item => !item.adminOnly || isAdminMode.value)
		.map(item => ({
			...item,
			label: labels[item.key]
		}))
})
const languageToggleLabel = computed(() => {
	userLocale.value
	return i18n.t('Language')
})
const toggleNavigationLabel = computed(() => {
	userLocale.value
	return i18n.t('Toggle navigation')
})
const iconClasses = ICON_CLASSES
const userMenuEl = ref(null)
const languageMenuEl = ref(null)
const currentLanguage = computed(() => userLocale.value || i18n.resolvedLanguage || 'en')
const languages = computed(() => resolveLanguageOptions(config.locales))
const currentLanguageMeta = computed(() => {
	return languages.value.find(locale => locale.code === currentLanguage.value) || languages.value[0]
})
const currentLanguageCode = computed(() => (currentLanguage.value || 'en').slice(0, 2).toUpperCase())
const currentLanguageLabel = computed(() => currentLanguageMeta.value?.nativeLabel || currentLanguage.value)

function getCsrfToken() {
	if (typeof document === 'undefined') return null
	const match = document.cookie.match(/(?:eventyay_csrftoken|pretix_csrftoken|csrftoken)=([^;]+)/)
	return match ? decodeURIComponent(match[1]) : null
}

/** SPA path under config.basePath (e.g. rooms/foo or rooms/foo?tab=1) for video-access resume params */
function getVideoResumeParam() {
	const basePath = (config.basePath || '').replace(/\/$/, '')
	let full = router.currentRoute.value.fullPath || '/'
	const hashIdx = full.indexOf('#')
	if (hashIdx !== -1) full = full.slice(0, hashIdx)
	if (basePath && full.startsWith(basePath)) {
		full = full.slice(basePath.length) || '/'
	}
	if (full.startsWith('/')) full = full.slice(1)
	if (!full || full === '/') return ''
	return full
}

function videoAccessRefreshPath() {
	const { organizer, event } = eventRouting.value || {}
	if (!organizer || !event) return null
	const base = `/common/event/${encodeURIComponent(organizer)}/${encodeURIComponent(event)}/video-access/`
	const resume = getVideoResumeParam()
	if (!resume) return base
	const q = resume.indexOf('?')
	const pathPart = (q === -1 ? resume : resume.slice(0, q)).replace(/^\/+/, '')
	const queryPart = q === -1 ? '' : resume.slice(q + 1)
	const params = new URLSearchParams()
	if (pathPart) params.set('resume_path', pathPart)
	if (queryPart) params.set('resume_query', queryPart)
	const qs = params.toString()
	return qs ? `${base}?${qs}` : base
}

function getNextUrl() {
	if (window.eventyay?.isOrganizerArea) {
		return window.location.pathname + window.location.search + window.location.hash
	}
	return videoAccessRefreshPath() || (window.location.pathname + window.location.search + window.location.hash)
}

function startAdminSession() {
	const nextUrl = getNextUrl()
	const action = new URL('control/sudo/', buildBaseSansVideo()).href
	const form = document.createElement('form')
	form.method = 'POST'
	form.action = `${action}?next=${encodeURIComponent(nextUrl)}`
	const csrf = getCsrfToken()
	if (csrf) {
		const input = document.createElement('input')
		input.type = 'hidden'
		input.name = 'csrfmiddlewaretoken'
		input.value = csrf
		form.appendChild(input)
	}
	document.body.appendChild(form)
	form.submit()
}

function endAdminSession() {
	const nextUrl = getNextUrl()
	const action = new URL('control/sudo/stop/', buildBaseSansVideo()).href
	window.location.href = `${action}?next=${encodeURIComponent(nextUrl)}`
}

function buildBaseSansVideo() {
	const { protocol, host } = window.location
	const basePath = config?.basePath ?? ''
	if (!basePath) {
		return `${protocol}//${host}/`
	}
	const segments = basePath.split('/').filter(Boolean)
	const videoIndex = segments.lastIndexOf('video')
	if (videoIndex === -1) {
		return `${protocol}//${host}/`
	}
	const prefixEnd = Math.max(0, videoIndex - 2)
	const prefixSegments = segments.slice(0, prefixEnd)
	const prefix =
		prefixSegments.length > 0
			? `/${prefixSegments.join('/')}/`
			: '/'
	return `${protocol}//${host}${prefix}`
}
function toggleProfileMenu() {
	profileMenuOpen.value = !profileMenuOpen.value
	if (profileMenuOpen.value) languageMenuOpen.value = false
}
function closeProfileMenu() {
	profileMenuOpen.value = false
}
function toggleLanguageMenu() {
	languageMenuOpen.value = !languageMenuOpen.value
	if (languageMenuOpen.value) profileMenuOpen.value = false
}
function closeLanguageMenu() {
	languageMenuOpen.value = false
}
async function selectLanguage(locale) {
	closeLanguageMenu()
	if (locale === currentLanguage.value) return
	try {
		await store.dispatch('updateUserLocale', locale)
	} catch (error) {
		console.error('Failed to change interface language', error)
	}
}
function logout() {
	localStorage.removeItem('token')
	localStorage.removeItem('clientId')
	const logoutUrl = buildBaseSansVideo() + 'common/logout/'
	window.location.href = logoutUrl
}
function onMenuItem(item) {
	if (item.action === 'logout') {
		logout()
		closeProfileMenu()
		return
	}
	if (item.route) {
		router.push(item.route).catch(() => {})
		closeProfileMenu()
		return
	}
	if (item.externalPath) {
		try {
			window.location.assign(buildMenuExternalHref(item))
		} catch (e) {
			window.location.assign('/' + item.externalPath)
		}
		closeProfileMenu()
		return
	}
	try {
		const base = buildBaseSansVideo()
		window.location.assign(base)
	} catch (e) {
		router.push('/').catch(() => {})
	}
	closeProfileMenu()
}

function getItemHref(item) {
	if (item.action === 'logout') return '#logout'
	if (item.route) return router.resolve(item.route).href
	if (item.externalPath) {
		try {
			return buildMenuExternalHref(item)
		} catch (e) {
			return '/' + item.externalPath
		}
	}
	return '#'
}

function handleClickOutside(e) {
	if (profileMenuOpen.value) {
		const el = userMenuEl.value
		if (el && !el.contains(e.target)) closeProfileMenu()
	}
	if (languageMenuOpen.value) {
		const el = languageMenuEl.value
		if (el && !el.contains(e.target)) closeLanguageMenu()
	}
}
function handleGlobalKeydown(e) {
	if (e.key === 'Escape') {
		if (profileMenuOpen.value) closeProfileMenu()
		if (languageMenuOpen.value) closeLanguageMenu()
	}
}

onMounted(() => {
	if (!document.querySelector('link[href*="font-awesome"]')) {
		const link = document.createElement('link')
		link.rel = 'stylesheet'
		link.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css'
		document.head.appendChild(link)
	}
	document.addEventListener('click', handleClickOutside)
	document.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
	document.removeEventListener('click', handleClickOutside)
	document.removeEventListener('keydown', handleGlobalKeydown)
})
</script>
<style lang="stylus">
.c-app-bar
	--app-bar-background: var(--clr-navigation-background, var(--color-header-background, var(--clr-primary)))
	--app-bar-text: var(--clr-navigation-text-primary, var(--color-header-text, #fff))
	position: fixed
	top: 0
	left: 0
	right: 0
	height: 50px
	display: flex
	align-items: center
	justify-content: space-between
	padding: 0 12px 0 8px
	font-size: 14px
	font-weight: 400
	background-color: var(--app-bar-background)
	white-space: nowrap
	overflow: visible
	z-index: 120
	.bunt-icon-button
		icon-button-style(color: var(--app-bar-text), style: clear)
	.nav-actions
		display: flex
		align-items: center
		align-self: stretch
		gap: 4px
		margin-left: auto
	.language-menu
		position: relative
		align-self: stretch
		display: flex
		align-items: stretch
	.language-toggle
		appearance: none
		background: none
		border: none
		padding: 0 12px
		margin: 0
		min-height: 50px
		display: inline-flex
		align-items: center
		gap: 6px
		font: inherit
		font-size: 14px
		color: var(--app-bar-text)
		cursor: pointer
		&:hover
			background-color: rgba(0, 0, 0, 0.08)
		&:focus-visible
			outline: 2px solid var(--clr-primary)
			outline-offset: -2px
		&.open .fa-caret-down
			transform: rotate(180deg)
		.current-locale
			font-weight: 500
			letter-spacing: 0.02em
		.fa-caret-down
			font-size: 12px
			transition: transform 0.15s ease-in-out
	.language-dropdown
		position: absolute
		top: calc(100% + 2px)
		right: 0
		min-width: 180px
		max-height: 320px
		overflow-y: auto
		background: white
		color: #495057
		border: 1px solid #e9ecef
		border-radius: var(--size-border-radius, 0.25rem)
		box-shadow: var(--shadow-light, 0 0 6px 1px rgb(0 0 0 / 0.1))
		z-index: 120
		padding: 4px 0
	.language-option
		appearance: none
		background: none
		border: none
		display: block
		width: 100%
		text-align: left
		padding: 8px 16px
		font: inherit
		color: inherit
		cursor: pointer
		&:hover, &.active
			background-color: rgba(0, 0, 0, 0.06)
		&.active
			font-weight: 600
	.sr-only
		position: absolute
		width: 1px
		height: 1px
		padding: 0
		margin: -1px
		overflow: hidden
		clip: rect(0, 0, 0, 0)
		white-space: nowrap
		border: 0
	.admin-session-actions
		display: flex
		align-items: stretch
		align-self: stretch
		margin: 0 -2px
		min-height: 0
		.admin-mode-btn
			appearance: none
			background: none
			border: none
			padding: 0 12px
			margin: 0
			min-height: 50px
			height: 100%
			box-sizing: border-box
			display: inline-flex
			align-items: center
			justify-content: center
			gap: 8px
			font: inherit
			font-weight: 400
			font-size: 14px
			color: var(--app-bar-text)
			cursor: pointer
			white-space: nowrap
			border-radius: 0
			transition: background-color 0.15s ease-in-out, color 0.15s ease-in-out
			i.fa
				font-size: 15px
				opacity: 0.92
				line-height: 1
			&:hover
				background-color: rgba(0, 0, 0, 0.08)
				color: var(--app-bar-text)
			&:focus-visible
				outline: 2px solid var(--clr-primary)
				outline-offset: -2px
			&.admin-mode-btn--end
				background-color: var(--clr-danger, #d32f2f)
				color: #fff
				i.fa
					color: #fff
					opacity: 1
				&:hover
					background-color: #b71c1c
					color: #fff
				&:focus-visible
					outline: 2px solid #fff
					outline-offset: -2px
	.left
		display: flex
		align-items: center
		gap: 2px
		position: relative
		.navbar-toggle-sidebar
			appearance: none
			background: transparent !important
			background-color: transparent !important
			border: none !important
			padding: 7px 9px
			margin: 1px 0 0 0
			color: #fff
			font-size: 14px
			display: inline-flex
			align-items: center
			justify-content: center
			cursor: pointer
			-webkit-tap-highlight-color: transparent
			outline: none !important
			box-shadow: none !important
			border-radius: 0
			transition: color 0.15s ease
			&:hover, &:focus, &:active
				background: transparent !important
				background-color: transparent !important
				color: rgba(255, 255, 255, 0.8)
				outline: none !important
				box-shadow: none !important
			&:focus-visible
				outline: none !important
			.fa-bars
				font-size: 18px
				color: inherit
				line-height: 1
		.navbar-brand
			display: inline-flex
			align-items: center
			height: 50px
			padding: 5px 0
			margin-right: 16px
			margin-left: 2px
			font-size: 20px
			font-weight: 500
			line-height: inherit
			white-space: nowrap
			color: #f8f9fa
			text-decoration: none
			font-family: inherit
			&.anonymous
				pointer-events: none
			img
				display: inline-block
				vertical-align: middle
				height: 30px
				width: auto
				margin-top: 0
				margin-right: 0.2em
			.brand-text
				font-size: 20px
				font-weight: 500
				color: #f8f9fa
				line-height: 1
				letter-spacing: normal
			&:hover, &:focus
				color: #fff
				text-decoration: none
		.nav-view-event
			display: inline-flex
			align-items: center
			gap: 6px
			color: rgba(255, 255, 255, 0.9)
			font-size: 14px
			text-decoration: none
			padding: 0 12px
			height: 50px
			line-height: 50px
			margin-left: 8px
			font-weight: normal
			transition: color 0.15s ease
			.fa
				font-size: 14px
			&:hover, &:focus
				color: #ffffff
				text-decoration: none
	.user-section
		display: flex
		align-items: center
		gap: 8px
		position: relative
	.user-menu
		position: relative
	.user-profile
		display: flex
		align-items: center
		gap: 8px
		padding: 6px 10px
		border-radius: 4px
		color: var(--app-bar-text)
		text-decoration: none
		position: relative
		cursor: pointer
		transition: background-color 0.15s ease-in-out, color 0.15s ease-in-out
		&:hover
			background-color: transparent
		&:focus-visible
			outline: 2px solid var(--clr-primary)
			outline-offset: 2px
		&.open
			.user-caret
				transform: rotate(180deg)
		.display-name
			font-size: inherit
			font-weight: 400
			max-width: 140px
			overflow: hidden
			text-overflow: ellipsis
			white-space: nowrap
		.user-caret
			width: 0
			height: 0
			border-left: 5px solid transparent
			border-right: 5px solid transparent
			border-top: 6px solid currentColor
			margin-left: 2px
			cursor: pointer
	.logout-btn
		appearance: none
		background: none
		border: none
		padding: 8px 12px
		cursor: pointer
		color: var(--app-bar-text)
		display: flex
		align-items: center
		justify-content: center
		border-radius: 4px
		transition: background-color 0.2s, color 0.2s
		&:hover
			background-color: rgba(0, 0, 0, 0.1)
			color: var(--clr-danger)
		&:focus-visible
			outline: 2px solid var(--clr-primary)
		i
			font-size: 18px
	.user-section
		.profile-dropdown
			position: absolute
			top: calc(100% + 2px)
			right: 0
			min-width: 160px
			max-width: 400px
			width: auto
			max-height: 500px
			overflow: visible
			background: white
			color: #495057
			border: 1px solid #e9ecef
			border-radius: var(--size-border-radius, 0.25rem)
			box-shadow: var(--shadow-light, 0 0 6px 1px rgb(0 0 0 / 0.1))
			padding: 0
			z-index: 120
			font-size: 15px
			user-select: none
			&::before,
			&::after
				position: absolute
				display: inline-block
				content: " "
			&::before
				top: -16px
				right: 12px
				border: 8px solid transparent
				border-bottom-color: rgb(27 31 35 / 0.15)
			&::after
				top: -14px
				right: 13px
				border: 7px solid transparent
				border-bottom-color: white
			.menu-item
				appearance: none
				background: none
				border: none
				width: 100%
				box-sizing: border-box
				display: flex
				align-items: center
				gap: 8px
				text-align: left
				padding: 8px 18px
				min-height: 0
				line-height: 1.25
				cursor: pointer
				color: inherit
				font: inherit
				font-weight: 400
				text-decoration: none
				transition: color 0.15s ease-in-out, background-color 0.15s ease-in-out
				&:hover, &:focus-visible
					background: var(--clr-primary-alpha-18)
					color: var(--clr-primary-darken-15, var(--clr-primary))
					text-decoration: none
				&:focus-visible
					outline: none
				.menu-item-icon
					color: currentColor
					flex: 0 0 auto
					width: 18px
					height: 18px
					display: inline-flex
					align-items: center
					justify-content: center
					opacity: .9
					i
						font-size: 16px
						line-height: 1
						width: 16px
						height: 16px
						text-align: center
						color: currentColor
				.menu-item-label
					flex: 1 1 auto
					min-width: 0
					white-space: nowrap
					text-overflow: ellipsis
					overflow: hidden
			.menu-item-parent
				position: relative
			.submenu-caret
				margin-left: auto
				width: 0
				height: 0
				border-top: 5px solid transparent
				border-bottom: 5px solid transparent
				border-left: 6px solid currentColor
				opacity: 0.75
			.profile-submenu
				position: absolute
				top: 0
				right: 100%
				left: auto
				margin-right: 8px
				min-width: 160px
				max-width: 400px
				width: auto
				background: white
				color: #495057
				border: 1px solid #e9ecef
				border-radius: var(--size-border-radius, 0.25rem)
				box-shadow: var(--shadow-light, 0 0 6px 1px rgb(0 0 0 / 0.1))
				padding: 0
				z-index: 121
				&::before,
				&::after
					position: absolute
					display: inline-block
					content: " "
				&::before
					top: 10px
					right: -16px
					left: auto
					border: 8px solid transparent
					border-left-color: rgb(27 31 35 / 0.15)
				&::after
					top: 11px
					right: -14px
					left: auto
					border: 7px solid transparent
					border-left-color: white
			.menu-separator
				height: 1px
				background: rgba(0,0,0,0.08)
				margin: 6px 0
			.visibility-row
				display: flex
				align-items: center
				justify-content: space-between
				gap: 8px
				padding: 8px 18px
				.visibility-label
					font-size: 13px
					font-weight: 500
					color: #495057
					white-space: nowrap
				.visibility-badge
					display: inline-block
					padding: 2px 8px
					border-radius: 10px
					font-size: 11px
					font-weight: 600
					letter-spacing: 0.02em
					white-space: nowrap
					&.badge-public
						background: #d4edda
						color: #155724
					&.badge-private
						background: #f8d7da
						color: #721c24

.dropdown-reveal-enter-active,
.dropdown-reveal-leave-active
	transition: opacity 120ms ease-out, transform 120ms ease-out
.dropdown-reveal-enter-from,
.dropdown-reveal-leave-to
	opacity: 0
	transform: translateY(-4px)


@media (max-width: 991px)
	.c-app-bar
		padding: 0 10px 0 6px
		.nav-view-event
			padding: 0 8px
			margin-left: 4px
			span
				display: none
		.admin-session-actions .admin-mode-btn
			padding: 0 8px
			span
				display: none
		.user-profile .display-name
			max-width: 90px

@media (max-width: 767px)
	.c-app-bar
		height: 50px
		padding: 0 8px 0 4px
		.left
			gap: 0
			.navbar-brand
				margin-right: 6px
				margin-left: 0
				padding: 0
				img
					height: 28px
		.nav-actions
			gap: 2px
		.language-toggle
			padding: 0 6px
			gap: 3px
			font-size: 13px
		.user-profile
			padding: 4px
			gap: 4px
			.display-name
				display: none
			.user-caret
				margin-left: 0
		.language-dropdown
			right: 4px
			max-width: calc(100vw - 12px)
		.user-section
			.profile-dropdown
				right: 4px
				max-width: calc(100vw - 12px)
				&::before
					right: 14px
				&::after
					right: 15px
				.profile-submenu
					position: static
					right: auto
					top: auto
					margin: 4px 0 4px 12px
					box-shadow: none
					border: 1px solid #e9ecef
					border-left: 3px solid var(--clr-primary, #2185d0)
					&::before, &::after
						display: none

@media (max-width: 480px)
	.c-app-bar
		.left .navbar-brand .brand-text
			display: none

#app.override-sidebar-collapse .c-app-bar
	border-bottom: none
	.bunt-icon-button
		visibility: hidden
</style>
