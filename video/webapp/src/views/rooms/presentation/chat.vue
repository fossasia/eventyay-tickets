<template lang="pug">
.v-presentation-chat
	template(v-for="(message, index) of filteredTimeline")
		chat-message(:message="message", :nextMessage="filteredTimeline[index + 1]", mode="compact", :readonly="true", :key="message.event_id")
</template>
<script>
import { mapState } from 'vuex'
import ChatMessage from 'components/ChatMessage'

export default {
	components: { ChatMessage },
	props: {
		room: Object
	},
	computed: {
		...mapState('chat', ['channel', 'members', 'usersLookup', 'timeline', 'fetchingMessages']),
		module () {
			return this.room.modules.find(module => module.type === 'chat.native')
		},
		filteredTimeline () {
			return this.timeline.filter(message => message.event_type !== 'channel.member' && message.content.type !== 'deleted' && !message.replaces).reverse()
		},
	},
	created () {
		this.$store.dispatch('chat/subscribe', {channel: this.module.channel_id, config: this.module.config})
	}
}
</script>
<style lang="stylus">
.v-presentation-chat
	display: flex
	// reverse direction so we can wrap from top
	flex-direction: column-reverse
	justify-content: flex-start
	flex-wrap: wrap
	min-height: 0

	// sane presentation defaults for chat messages
	.c-chat-message
		width: 100%
		.timestamp, .preview-card
			display: none
</style>
