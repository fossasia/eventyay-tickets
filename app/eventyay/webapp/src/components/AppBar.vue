<template lang="pug">
.c-app-bar
	.left
		button.hamburger(type="button", @click="$emit('toggleSidebar')", @touchend="$emit('toggleSidebar')", aria-label="Toggle navigation")
			span.bar
			span.bar
			span.bar
		router-link.logo(:to="{name: 'home'}", :class="{anonymous: isAnonymous}")
			img(:src="theme.logo.url", :alt="world.title")
	div.user-profile(:class="{open: profileMenuOpen}", ref="userProfileEl", @click.self="toggleProfileMenu")
		avatar(v-if="!isAnonymous", :user="user", :size="32")
		span.display-name(v-if="!isAnonymous") {{ user.profile.display_name }}
		span.display-name(v-else) {{ $t('AppBar:user-anonymous') }}
		span.user-caret(role="button", :aria-expanded="String(profileMenuOpen)", aria-haspopup="true", tabindex="0", @click.stop="toggleProfileMenu", @keydown.enter.prevent="toggleProfileMenu", @keydown.space.prevent="toggleProfileMenu", :class="{open: profileMenuOpen}")
		.profile-dropdown(v-if="profileMenuOpen", role="menu")
			template(v-for="item in menuItems", :key="item.key")
				div.menu-separator(v-if="item.separatorBefore")
				div.menu-item-wrapper(:class="{'has-children': item.children, 'submenu-open': openSubmenuKey === item.key}")
					a.menu-item(:class="{danger: item.action === 'logout'}", :href="item.children ? '#' : getItemHref(item)", role="menuitem", :aria-haspopup="item.children ? 'true' : 'false'", :aria-expanded="item.children ? String(openSubmenuKey === item.key) : undefined", @click.prevent="item.children ? toggleSubmenu(item) : onMenuItem(item)", @keydown.right.prevent="item.children && openSubmenu(item)", @keydown.left.prevent="item.children && forceCloseSubmenu()")
						span.menu-item-icon(v-if="item.icon" aria-hidden="true")
							i(:class="iconClasses[item.icon]")
						span.menu-item-label {{ item.label }}
						span.submenu-caret(v-if="item.children" :class="{open: openSubmenuKey === item.key}") ▸
					transition(name="submenu-fade")
						div.submenu-box(v-if="item.children && openSubmenuKey === item.key" role="menu")
							a.submenu-item(v-for="child in item.children" :key="child.key" role="menuitem" :href="getItemHref(child)" @click.prevent="onMenuItem(child)")
								span.menu-item-icon(v-if="child.icon" aria-hidden="true")
									i(:class="iconClasses[child.icon]")
								span.menu-item-label {{ child.label }}
</template>
<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import theme from 'theme'
import Avatar from 'components/Avatar'

const ICON_CLASSES = {
	dashboard: 'fa fa-tachometer',
	orders: 'fa fa-shopping-cart',
	events: 'fa fa-calendar',
	organizers: 'fa fa-users',
	account: 'fa fa-user',
	admin: 'fa fa-cog',
	logout: 'fa fa-sign-out',
	tickets: 'fa fa-ticket',
	talks: 'fa fa-microphone'
}

const PROFILE_MENU_ITEMS = [
	{
		key: 'dashboard',
		label: 'Dashboard',
		icon: 'dashboard',
		children: [
			{ key: 'db-main', label: 'Main dashboard', icon: 'dashboard', externalPath: 'common/' },
			{ key: 'db-tickets', label: 'Tickets', icon: 'tickets', externalPath: 'tickets/control' },
			{ key: 'db-talks', label: 'Talks', icon: 'talks', externalPath: 'talk/orga/event/' }
		]
	},
	{ key: 'orders', label: 'My Orders', externalPath: 'tickets/common/orders/', icon: 'orders' },
	{ key: 'events', label: 'My Events', externalPath: 'tickets/common/events/', icon: 'events' },
	{ key: 'organizers', label: 'Organizers', externalPath: 'tickets/common/organizers/', icon: 'organizers' },
	{ key: 'account', label: 'Account', route: { name: 'preferences' }, separatorBefore: true, icon: 'account' },
	{ key: 'admin', label: 'Admin', route: { name: 'admin' }, separatorBefore: true, icon: 'admin' },
	{ key: 'logout', label: 'Logout', action: 'logout', separatorBefore: true, icon: 'logout' }
]

defineEmits(['toggleSidebar'])

const store = useStore()
const router = useRouter()

const user = computed(() => store.state.user)
const world = computed(() => store.state.world)

const isAnonymous = computed(() => Object.keys(user.value.profile || {}).length === 0)

const profileMenuOpen = ref(false)
const menuItems = ref(PROFILE_MENU_ITEMS)
const iconClasses = ICON_CLASSES
const openSubmenuKey = ref(null)
const submenuCloseTimer = ref(null)
const userProfileEl = ref(null)

function buildBaseSansVideo() {
	const { protocol, host } = window.location
	const pathname = window.location.pathname
	const idx = pathname.indexOf('/video')
	let basePath = '/'
	if (idx > -1) {
		const pre = pathname.substring(0, idx) || '/'
		basePath = pre.endsWith('/') ? pre : pre + '/'
	} else {
		basePath = '/'
	}
	return protocol + '//' + host + basePath
}
function toggleProfileMenu() {
	profileMenuOpen.value = !profileMenuOpen.value
}
function closeProfileMenu() {
	profileMenuOpen.value = false
	openSubmenuKey.value = null
}
function onMenuItem(item) {
	if (item.action === 'logout') {
		localStorage.removeItem('token')
		localStorage.removeItem('clientId')
		window.location.reload()
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
			const base = buildBaseSansVideo()
			window.location.assign(base + item.externalPath)
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
			const base = buildBaseSansVideo()
			return base + item.externalPath
		} catch (e) {
			return '/' + item.externalPath
		}
	}
	return '#'
}

function openSubmenu(item) {
	if (!item?.children) return
	openSubmenuKey.value = item.key
}
function toggleSubmenu(item) {
	if (!item?.children) return
	openSubmenuKey.value = openSubmenuKey.value === item.key ? null : item.key
}
function forceCloseSubmenu() {
	openSubmenuKey.value = null
}
function scheduleSubmenuClose() {
	clearSubmenuClose()
	submenuCloseTimer.value = setTimeout(() => {
		openSubmenuKey.value = null
	}, 250)
}
function clearSubmenuClose() {
	if (submenuCloseTimer.value) {
		clearTimeout(submenuCloseTimer.value)
		submenuCloseTimer.value = null
	}
}
function handleClickOutside(e) {
	if (!profileMenuOpen.value) return
	const el = userProfileEl.value
	if (el && !el.contains(e.target)) closeProfileMenu()
}
function handleGlobalKeydown(e) {
	if (e.key === 'Escape' && profileMenuOpen.value) closeProfileMenu()
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
	if (submenuCloseTimer.value) clearTimeout(submenuCloseTimer.value)
})
</script>
<style lang="stylus">
.c-app-bar
	position: relative
	height: 48px
	display: flex
	align-items: center
	justify-content: space-between
	padding: 0 8px
	background-color: var(--clr-sidebar)
	border-bottom: 2px solid var(--clr-primary)
	box-shadow: 0 2px 4px rgba(0,0,0,0.22), 0 3px 9px -2px rgba(0,0,0,0.35)
	white-space: nowrap
	overflow: visible
	z-index: 120
	.bunt-icon-button
		icon-button-style(color: var(--clr-sidebar-text-primary), style: clear)
	.left
		display: flex
		align-items: center
		gap: 4px
		.hamburger
			appearance: none
			background: none
			border: none
			padding: 0.5rem
			margin: 0
			width: auto
			height: auto
			display: flex
			flex-direction: column
			justify-content: center
			align-items: flex-start
			cursor: pointer
			&:focus-visible
				outline: 2px solid var(--clr-primary)
				outline-offset: 2px
			.bar
				display: block
				width: 22px
				height: 3px
				background: var(--clr-sidebar-text-primary)
				border-radius: 2px
				transition: background .2s
				&:not(:last-child)
					margin-bottom: 5px
			&:hover .bar
				background: var(--clr-sidebar-text-secondary)
	.logo
		margin-left: 0
		font-size: 24px
		height: 40px
		&.anonymous
			pointer-events: none
		img
			height: 100%
			max-width: 100%
			object-fit: contain
			margin: 0
			padding: 0
	.user-profile
		display: flex
		align-items: center
		gap: 8px
		padding: 4px 8px
		color: var(--clr-sidebar-text-primary)
		text-decoration: none
		max-width: 50%
		position: relative
		cursor: pointer
		&.open
			.user-caret
				transform: rotate(180deg)
		.display-name
			font-size: 14px
			font-weight: 500
			max-width: 140px
			overflow: hidden
			text-overflow: ellipsis
			white-space: nowrap
		.user-caret
			width: 0
			height: 0
			border-left: 5px solid transparent
			border-right: 5px solid transparent
			border-top: 6px solid var(--clr-sidebar-text-primary)
			margin-left: 2px
			cursor: pointer
			transition: transform .2s
			outline: none
			&:focus-visible
				outline: 2px solid var(--clr-primary)
		.profile-dropdown
			position: absolute
			top: calc(100% + 6px)
			right: 0
			width: 220px
			max-height: 500px
			overflow: visible
			background: var(--clr-surface, #fff)
			color: var(--clr-text, #111)
			border: 1px solid rgba(0,0,0,0.2)
			border-radius: 2px
			box-shadow: 0 3px 8px rgba(0,0,0,0.175), 0 1px 3px rgba(0,0,0,0.105)
			padding: 6px 0
			z-index: 500
			font-size: 14px
			user-select: none
			.menu-item-wrapper
				position: relative
				&.has-children > .menu-item
					padding-right: 18px
				.submenu-caret
					position: absolute
					right: 10px
					top: 50%
					transform: translateY(-50%) rotate(180deg)
					font-size: 12px
					opacity: .7
					pointer-events: none
					transition: transform .18s ease, opacity .15s
				
				.submenu-caret.open
					transform: translateY(-50%) rotate(0deg)
				&:hover .submenu-caret
					opacity: 1
				.submenu-box
					position: absolute
					top: 0
					right: calc(100% + 8px)
					width: 200px
					background: var(--clr-surface, #fff)
					border: 1px solid rgba(0,0,0,0.20)
					border-radius: 4px
					box-shadow: 0 1px 4px rgba(0,0,0,0.12), 0 1px 3px -1px rgba(0,0,0,0.1)
					padding: 6px 0
					z-index: 650
					&:before
						content: ''
						position: absolute
						top: 10px
						left: 100%
						width: 8px
						height: 8px
						background: var(--clr-surface, #fff)
						border-top: 1px solid rgba(0,0,0,0.20)
						border-right: 1px solid rgba(0,0,0,0.20)
						transform: translateX(-4px) rotate(45deg)
						box-shadow: 2px -2px 4px rgba(0,0,0,0.08)
					.submenu-item
						appearance: none
						background: none
						border: none
						width: 100%
						text-align: left
						padding: 8px 10px
						cursor: pointer
						font: inherit
						color: inherit
						display: flex
						align-items: center
						gap: 8px
						white-space: nowrap
						text-decoration: none
						& + .submenu-item
							border-top: 1px solid rgba(0,0,0,0.08)
						&:hover, &:focus-visible
							background: rgba(0,0,0,0.06)
						.menu-item-icon
							color: var(--clr-primary)
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
			.menu-item
				appearance: none
				background: none
				border: none
				width: 100%
				display: flex
				align-items: center
				gap: 8px
				text-align: left
				padding: 8px 10px
				cursor: pointer
				color: inherit
				font: inherit
				text-decoration: none
				&:hover, &:focus-visible
					background: rgba(0,0,0,0.06)
				&.danger
					color: #b00020
				.menu-item-icon
					color: var(--clr-primary)
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
			.menu-item.danger .menu-item-icon,
			.menu-item.danger .menu-item-icon i
				color: inherit
			.menu-item-wrapper:hover > .menu-item
				background: rgba(0,0,0,0.04)
			.menu-item-wrapper:hover > .menu-item.danger
				background: rgba(176,0,32,0.08)
			.submenu-fade-enter-active, .submenu-fade-leave-active
				transition: opacity .12s ease, transform .12s ease
			.submenu-fade-enter-from, .submenu-fade-leave-to
				opacity: 0
				transform: translateX(4px)
			.menu-separator
				height: 1px
				background: rgba(0,0,0,0.08)
				margin: 6px 0


@media (max-width: 560px)
	.user-profile .display-name
		display: none
	.logo img
		max-width: 120px

#app.override-sidebar-collapse .c-app-bar
	border-bottom: none
	.bunt-icon-button
		visibility: hidden
</style>
