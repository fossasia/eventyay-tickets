<template lang="pug">
prompt.c-channel-browser(@close="$emit('close')", :scrollable="false")
	.content
		h2 Explore rooms
		p bleep blorp, #[a(href="#", @click="$emit('createChannel')") create a new channel]?
		.channels(v-scrollbar.y="")
			router-link.channel(v-for="channel of channels", :to="{name: 'room', params: {roomId: channel.room.id}}", @click.native="$emit('close')")
				.channel-info
					.name {{ channel.room.name }}
					.description {{ channel.room.description }}
				.actions
					template(v-if="channel.channelJoined")
						bunt-button#btn-view view
					template(v-else)
						bunt-button#btn-preview preview
						bunt-button#btn-join(@click="join(channel)") join
</template>
<script>
import { mapState } from 'vuex'
import Prompt from 'components/Prompt'

export default {
	components: { Prompt },
	data () {
		return {
		}
	},
	computed: {
		...mapState(['rooms']),
		...mapState('chat', ['joinedChannels']),
		channels () {
			return this.rooms
				.filter(room => room.modules.length === 1 && room.modules[0].type === 'chat.native')
				.map(room => ({room, channelJoined: this.joinedChannels.some(channel => channel.id === room.modules[0].channel_id)}))
		}
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
.c-channel-browser
	.prompt-wrapper
		width: 580px
	.content
		min-height: 0
		display: flex
		flex-direction: column
	h2
		margin: 16px 16px 8px 16px
	p
		margin: 0 16px 8px 16px
		a
			font-weight: 600
	.channels
		display: flex
		flex-direction: column
		.channel
			padding: 16px
			display: flex
			align-items: center
			border-bottom: border-separator()
			.channel-info
				flex: auto
				color: $clr-primary-text-light
				.name
					font-size: 16px
					font-weight: 500
				.description
					white-space: pre-wrap
			.actions
				flex: none
				#btn-view, #btn-preview
					themed-button-secondary()
				#btn-join
					themed-button-primary()
</style>
