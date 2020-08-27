<template lang="pug">
.c-channel
	.header
		h2 {{ otherUsers.map(user => user.profile.display_name).join(', ') }}
		bunt-icon-button(@click="startCall", tooltip="start video call", tooltipPlacement="left") phone_outline
	chat(mode="standalone", :module="{channel_id: channelId}", :showUserlist="false")
</template>
<script>
import { mapState } from 'vuex'
import Chat from 'components/Chat'

export default {
	components: { Chat },
	props: {
		channelId: String
	},
	computed: {
		...mapState(['user']),
		...mapState('chat', ['joinedChannels']),
		channel () {
			return this.joinedChannels?.find(channel => channel.id === this.channelId)
		},
		otherUsers () {
			return this.channel?.members.filter(member => member.id !== this.user.id)
		}
	},
	methods: {
		startCall () {
			const channel = this.channel
			this.$store.dispatch('chat/startCall', {channel})
		}
	}
}
</script>
<style lang="stylus">
.c-channel
	flex: auto
	display: flex
	flex-direction: column
	background-color: $clr-white
	min-height: 0
	.header
		flex: none
		display: flex
		padding: 8px 16px
		height: 56px
		box-sizing: border-box
		border-bottom: border-separator()
		justify-content: space-between
		align-items: center
		h2
			margin: 0
		.bunt-icon-button
			icon-button-style(style: clear)
</style>
