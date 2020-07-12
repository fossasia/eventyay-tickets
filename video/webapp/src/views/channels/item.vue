<template lang="pug">
.c-channel
	chat(mode="standalone", :module="{channel_id: channelId}")
</template>
<script>
import Chat from 'components/Chat'

export default {
	props: {
		channelId: String
	},
	components: { Chat },
	data () {
		return {
		}
	},
	computed: {
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
.c-channel
	flex: auto
	display: flex
	flex-direction: column
	background-color: $clr-white
	min-height: 0
</style>
