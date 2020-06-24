<template lang="pug">
.c-app-bar
	bunt-icon-button(@click="$emit('toggleSidebar')", @touchend.native="$emit('toggleSidebar')") menu
	.logo
		img(:src="theme.logo.url", :alt="world.title")
</template>
<script>
import { mapState } from 'vuex'
import theme from 'theme'

export default {
	data () {
		return {
			theme
		}
	},
	computed: {
		...mapState(['world'])
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
		img
			height: 100%
			max-width: 100%
			object-fit: contain
</style>
