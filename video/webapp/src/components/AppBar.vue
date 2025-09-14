<template lang="pug">
.c-app-bar
	.left
		button.hamburger(v-if="showHamburger", type="button", @click="$emit('toggleSidebar')", @touchend="$emit('toggleSidebar')", aria-label="Toggle navigation", :aria-expanded="showHamburger ? String(false) : null")
			span.bar
			span.bar
			span.bar
		router-link.logo(:to="{name: 'home'}", :class="{anonymous: isAnonymous}")
			img(:src="theme.logo.url", :alt="world.title")
	router-link.user-profile(:to="{name: 'preferences'}")
		avatar(v-if="!isAnonymous", :user="user", :size="32")
		span.display-name(v-if="!isAnonymous") {{ user.profile.display_name }}
		span.display-name(v-else) {{ $t('AppBar:user-anonymous') }}
		span.user-caret(aria-hidden="true")
</template>
<script>
import { mapState } from 'vuex'
import theme from 'theme'
import Avatar from 'components/Avatar'

export default {
	components: { Avatar },
	props: {
		showHamburger: { type: Boolean, default: true }
	},
	emits: ['toggleSidebar'],
	data() {
		return {
			theme
		}
	},
	computed: {
		...mapState(['user', 'world']),
		isAnonymous() {
			return Object.keys(this.user.profile).length === 0
		},
	}
}
</script>
<style lang="stylus">
.c-app-bar
	height: 48px
	display: flex
	align-items: center
	justify-content: space-between
	padding: 0 8px
	background-color: var(--clr-sidebar)
	border-bottom: 2px solid rgba(25, 119, 191, 1)
	box-shadow: 0 2px 4px rgba(0,0,0,0.22), 0 3px 9px -2px rgba(0,0,0,0.35)
	white-space: nowrap
	overflow: hidden
	text-overflow: ellipsis
	z-index: 100
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
		.display-name
			font-size: 14px
			font-weight: 500
		.user-caret
			width: 0
			height: 0
			border-left: 5px solid transparent
			border-right: 5px solid transparent
			border-top: 6px solid var(--clr-sidebar-text-primary)
			margin-left: 2px
	@media (max-width: 560px)
		.user-profile .display-name
			display: none
		.logo img
			max-width: 120px
#app.override-sidebar-collapse .c-app-bar
	border-bottom: none // TODO find a better solution, but having a border between app-bar and rooms-sidebar looks ugly
	.bunt-icon-button
		visibility: hidden
</style>
