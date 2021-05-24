<template lang="pug">
.v-presentation-chat
	template(v-for="(message, index) of filteredTimeline")
		chat-message(:message="message", :previousMessage="filteredTimeline[index - 1]", :nextMessage="filteredTimeline[index + 1]", mode="compact", :readonly="true", :key="message.event_id")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
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
			return this.timeline.filter(message => message.event_type !== 'channel.member' && message.content.type !== 'deleted' && !message.replaces)
		},
	},
	created () {
		this.$store.dispatch('chat/subscribe', {channel: this.module.channel_id, config: this.module.config})
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.v-presentation-chat
	display: flex
	flex-direction: column
	justify-content: flex-end
	min-height: 0
	max-width: 100%
</style>
