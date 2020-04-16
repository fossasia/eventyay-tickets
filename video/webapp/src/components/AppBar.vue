<template lang="pug">
.c-app-bar
	.logo {{ world.title }}
</template>
<script>
import { mapState } from 'vuex'

export default {
	components: {},
	data () {
		return {
		}
	},
	computed: {
		...mapState(['world'])
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-app-bar
	height: 48px
	display: flex
	align-items: center
	padding: 0 16px
	background-color: $clr-white
	box-shadow: 0px 2px 5px 0 rgba(0,0,0,0.16), 0px 2px 10px 0 rgba(0,0,0,0.12)
	z-index: 100
	.logo
		font-size: 24px
</style>
