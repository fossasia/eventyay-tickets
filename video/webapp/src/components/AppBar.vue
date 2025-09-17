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
				div.menu-item-wrapper(:class="{'has-children': item.children}")
					button.menu-item(:class="{danger: item.action === 'logout'}", type="button", role="menuitem", @click="item.children ? toggleSubmenu(item) : onMenuItem(item)", @mouseenter="item.children && openSubmenu(item)", @mouseleave="item.children && scheduleSubmenuClose()", @keydown.right.prevent="item.children && openSubmenu(item)", @keydown.left.prevent="item.children && forceCloseSubmenu()")
						span.menu-item-icon(v-if="item.icon", v-html="iconSvgs[item.icon]", aria-hidden="true")
						span.menu-item-label {{ item.label }}
						span.submenu-caret(v-if="item.children") ‹
					transition(name="submenu-fade")
						div.submenu-box(v-if="item.children && openSubmenuKey === item.key" role="menu" @mouseenter="clearSubmenuClose()" @mouseleave="scheduleSubmenuClose()")
							button.submenu-item(v-for="child in item.children" :key="child.key" type="button" role="menuitem" @click="onMenuItem(child)") {{ child.label }}
</template>
<script>
import { mapState } from 'vuex'
import theme from 'theme'
import Avatar from 'components/Avatar'

// Central inline SVG icon set (stroke icons, inherit currentColor)
const ICON_SVGS = {
	dashboard: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
	orders: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6h15l-1.5 9h-13z"/><path d="M6 6L5 3H2"/><circle cx="9" cy="20" r="1"/><circle cx="18" cy="20" r="1"/></svg>',
	events: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="16" rx="2"/><line x1="16" y1="3" x2="16" y2="7"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="3" y1="11" x2="21" y2="11"/></svg>',
	organizers: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="3"/><circle cx="16" cy="8" r="3"/><path d="M2 19c0-3.313 2.687-6 6-6"/><path d="M22 19c0-3.313-2.687-6-6-6"/></svg>',
	account: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c1.5-3.5 4.5-5 8-5s6.5 1.5 8 5"/></svg>',
	admin: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9 4v6c0 5-4 8-9 8s-9-3-9-8V7z"/><circle cx="12" cy="11" r="3"/></svg>',
	logout: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h-6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h6"/><path d="M10 12h11l-3-3"/><path d="M21 12l-3 3"/></svg>'
}

// Configuration for profile dropdown links (order matters)
// Each item may have: key, label, route (vue-router location object), action (custom string), separatorBefore (boolean)
const PROFILE_MENU_ITEMS = [
	{ key: 'dashboard', label: 'Dashboard', icon: 'dashboard', children: [
		{ key: 'db-overview', label: 'Overview', route: { name: 'home' } },
		{ key: 'db-stats', label: 'Stats', externalPath: 'tickets/common/stats/' },
		{ key: 'db-reports', label: 'Reports', externalPath: 'tickets/common/reports/' }
	] },
	{ key: 'orders', label: 'My Orders', externalPath: 'tickets/common/orders/', icon: 'orders' },
	{ key: 'events', label: 'My Events', externalPath: 'tickets/common/events/', icon: 'events' },
	{ key: 'organizers', label: 'Organizers', externalPath: 'tickets/common/organizers/', icon: 'organizers' },
	{ key: 'account', label: 'Account', route: { name: 'preferences' }, separatorBefore: true, icon: 'account' },
	{ key: 'admin', label: 'Admin', route: { name: 'admin' }, separatorBefore: true, icon: 'admin' },
	{ key: 'logout', label: 'Logout', action: 'logout', separatorBefore: true, icon: 'logout' }
]

export default {
	components: { Avatar },
	emits: ['toggleSidebar'],
	data() {
		return {
			theme,
			profileMenuOpen: false,
			menuItems: PROFILE_MENU_ITEMS,
			iconSvgs: ICON_SVGS,
			openSubmenuKey: null,
			submenuCloseTimer: null
		}
	},
	computed: {
		...mapState(['user', 'world']),
		isAnonymous() {
			return Object.keys(this.user.profile).length === 0
		},
	},
	mounted() {
		document.addEventListener('click', this.handleClickOutside)
		document.addEventListener('keydown', this.handleGlobalKeydown)
	},
	beforeUnmount() {
		document.removeEventListener('click', this.handleClickOutside)
		document.removeEventListener('keydown', this.handleGlobalKeydown)
	},
	methods: {
		buildBaseSansVideo() {
			const { protocol, host } = window.location
			const pathname = window.location.pathname
			const idx = pathname.indexOf('/video')
			let basePath = '/'
			if (idx > -1) {
				const pre = pathname.substring(0, idx) || '/'
				basePath = pre.endsWith('/') ? pre : pre + '/'
			} else {
				// ensure trailing slash
				basePath = pathname.endsWith('/') ? pathname : pathname + '/'
			}
			return protocol + '//' + host + basePath
		},
		toggleProfileMenu() {
			this.profileMenuOpen = !this.profileMenuOpen
		},
		closeProfileMenu() {
			this.profileMenuOpen = false
		},
		// Generic navigation handler for configured menu items
		onMenuItem(item) {
			if (item.action === 'logout') {
				if (this.$store?.dispatch) {
					this.$store.dispatch('logout').catch(() => {})
				}
				this.closeProfileMenu()
				return
			}
			// If the item defines a route, use SPA navigation
			if (item.route) {
				this.$router.push(item.route).catch(() => {})
				this.closeProfileMenu()
				return
			}
			// External path handling (relative to stripped base)
			if (item.externalPath) {
				try {
					const base = this.buildBaseSansVideo()
					window.location.assign(base + item.externalPath)
				} catch (e) {
					// fallback to root then append external path
					window.location.assign('/' + item.externalPath)
				}
				this.closeProfileMenu()
				return
			}
			// Otherwise strip '/video' and everything after it from current URL
			try {
				const base = this.buildBaseSansVideo()
				window.location.assign(base)
			} catch (e) {
				this.$router.push('/').catch(() => {})
			}
			this.closeProfileMenu()
		},
		openSubmenu(item) {
			if (!item?.children) return
			this.openSubmenuKey = item.key
		},
		toggleSubmenu(item) {
			if (!item?.children) return
			this.openSubmenuKey = this.openSubmenuKey === item.key ? null : item.key
		},
		forceCloseSubmenu() {
			this.openSubmenuKey = null
		},
		scheduleSubmenuClose() {
			this.clearSubmenuClose()
			this.submenuCloseTimer = setTimeout(() => {
				this.openSubmenuKey = null
			}, 250)
		},
		clearSubmenuClose() {
			if (this.submenuCloseTimer) {
				clearTimeout(this.submenuCloseTimer)
				this.submenuCloseTimer = null
			}
		},
		handleClickOutside(e) {
			if (!this.profileMenuOpen) return
			const el = this.$refs.userProfileEl
			if (el && !el.contains(e.target)) {
				this.closeProfileMenu()
			}
		},
		handleGlobalKeydown(e) {
			if (e.key === 'Escape' && this.profileMenuOpen) {
				this.closeProfileMenu()
			}
		}
	}
}
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
	border-bottom: 2px solid rgba(25, 119, 191, 1)
	box-shadow: 0 2px 4px rgba(0,0,0,0.22), 0 3px 9px -2px rgba(0,0,0,0.35)
	white-space: nowrap
	// allow dropdowns to overflow visually
	overflow: visible
	// Ensure AppBar and its dropdowns sit above content overlays like exporter buttons
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
			overflow-y: auto
			background: var(--clr-surface, #fff)
			color: var(--clr-text, #111)
			border: 1px solid rgba(0,0,0,0.2)
			border-radius: 2px
			box-shadow: 0 4px 12px rgba(0,0,0,0.25), 0 2px 4px rgba(0,0,0,0.15)
			padding: 6px 0
			z-index: 500
			font-size: 14px
			.menu-item
				appearance: none
				background: none
				border: none
				width: 100%
				display: flex
				align-items: center
				gap: 8px
				text-align: left
				padding: 6px 10px
				cursor: pointer
				color: inherit
				font: inherit
				&:hover, &:focus-visible
					background: rgba(0,0,0,0.06)
				&.danger
					color: #b00020
				.menu-item-wrapper
					position: relative
					&.has-children > .menu-item
						padding-right: 28px
					.submenu-caret
						margin-left: auto
						font-size: 12px
						opacity: .7
						pointer-events: none
						transition: opacity .15s
				.menu-item-wrapper:hover .submenu-caret
					opacity: 1
					.submenu-box
						position: absolute
						top: 0
						right: calc(100% + 10px)
						width: 200px
						background: var(--clr-surface, #fff)
						border: 1px solid rgba(0,0,0,0.20)
						border-radius: 4px
						box-shadow: 0 6px 18px -2px rgba(0,0,0,0.28), 0 2px 6px rgba(0,0,0,0.18)
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
							padding: 8px 12px
							cursor: pointer
							font: inherit
							color: inherit
							display: block
							white-space: nowrap
							&:hover, &:focus-visible
								background: rgba(0,0,0,0.06)
				&:hover > .menu-item
					background: rgba(0,0,0,0.04)
				&:hover > .menu-item.danger
					background: rgba(176,0,32,0.08)

				.submenu-fade-enter-active, .submenu-fade-leave-active
					transition: opacity .12s ease, transform .12s ease
				.submenu-fade-enter-from, .submenu-fade-leave-to
					opacity: 0
					transform: translateX(4px)
				.menu-item-icon
					flex: 0 0 auto
					width: 18px
					height: 18px
					display: inline-flex
					align-items: center
					justify-content: center
					opacity: .9
					svg
						display: block
						width: 16px
						height: 16px
				.menu-item-label
					flex: 1 1 auto
					min-width: 0
					white-space: nowrap
					text-overflow: ellipsis
					overflow: hidden
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
