<template lang="pug">
.c-app-bar
	bunt-icon-button(@click="$emit('toggleSidebar')", @touchend.native="$emit('toggleSidebar')") menu
	.logo {{ world.title }}
</template>
<script>
import { mapState } from 'vuex'

export default {
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
	padding: 0 8px
	background-color: $clr-white
	border-bottom: 2px solid var(--clr-primary)
	// box-shadow: 0px 2px 5px 0 rgba(0,0,0,0.16), 0px 2px 10px 0 rgba(0,0,0,0.12)
	z-index: 100
	.logo
		margin-left: 8px
		font-size: 24px
</style>
