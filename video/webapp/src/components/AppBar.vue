<template lang="pug">
.c-app-bar
	bunt-icon-button(v-if="showActions", @click="$emit('toggleSidebar')", @touchend.native="$emit('toggleSidebar')") menu
	router-link.logo(to="/", :class="{anonymous: isAnonymous}")
		img(:src="theme.logo.url", :alt="world.title")
	.user(v-if="showUser")
		p(v-if="isAnonymous") {{ $t('AppBar:user-anonymous') }}
		avatar(v-else, :user="user", :size="36")
</template>
<script>
import { mapState } from 'vuex'
import theme from 'theme'
import Avatar from 'components/Avatar'

export default {
	components: { Avatar },
	props: {
		showActions: {
			type: Boolean,
			default: true
		},
		showUser: {
			type: Boolean,
			default: false
		}
	},
	data () {
		return {
			theme
		}
	},
	computed: {
		...mapState(['user', 'world']),
		isAnonymous () {
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
	border-bottom: 2px solid var(--clr-primary)
	// box-shadow: 0px 2px 5px 0 rgba(0,0,0,0.16), 0px 2px 10px 0 rgba(0,0,0,0.12)
	z-index: 100
	.bunt-icon-button
		icon-button-style(color: var(--clr-sidebar-text-primary), style: clear)
	.logo
		margin-left: 8px
		font-size: 24px
		height: 40px
		&.anonymous
			pointer-events: none
		img
			height: 100%
			max-width: 100%
			object-fit: contain
	.user
		color: var(--clr-sidebar-text-primary)
#app.override-sidebar-collapse .c-app-bar
	border-bottom: none // TODO find a better solution, but having a border between app-bar and rooms-sidebar looks ugly
	.bunt-icon-button
		visibility: hidden
</style>
