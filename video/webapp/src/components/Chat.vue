<template lang="pug">
.c-chat
	template(v-if="channel")
		.timeline
			chat-message(v-for="message of filteredTimeline", :message="message", :key="message.event_id")
			infinite-scroll(:loading="fetchingMessages", @load="$store.dispatch('chat/fetchMessages')")
		.chat-input
			bunt-button(v-if="!hasJoined", @click="join", tooltip="to start writing, join this channel") join chat
			bunt-input(v-else, name="chat-composer", v-model="composingMessage", @keydown.native.enter="send")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState } from 'vuex'
import ChatMessage from './ChatMessage'
import InfiniteScroll from './InfiniteScroll'

export default {
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true
		}
	},
	components: { ChatMessage, InfiniteScroll },
	data () {
		return {
			composingMessage: ''
		}
	},
	computed: {
		...mapState('chat', ['channel', 'hasJoined', 'members', 'timeline', 'fetchingMessages']),
		filteredTimeline () {
			return this.timeline.filter(message => message.event_type === 'channel.message').reverse()
		}
	},
	created () {
		this.$store.dispatch('chat/subscribe', this.room.id)
	},
	destroyed () {
		this.$store.dispatch('chat/unsubscribe')
	},
	methods: {
		join () {
			this.$store.dispatch('chat/join')
		},
		send () {
			this.$store.dispatch('chat/sendMessage', {text: this.composingMessage})
			this.composingMessage = ''
		}
	}
}
</script>
<style lang="stylus">
.c-chat
	flex: auto
	background-color: $clr-white
	display: flex
	flex-direction: column
	.timeline
		flex: auto
		padding: 8px 0
		display: flex
		flex-direction: column-reverse
		justify-content: flex-start
		overflow-y: scroll
		.message
			padding-top: 8px
	.chat-input
		flex: none
		border-top: border-separator()
		height: 64px
		display: flex
		justify-content: center
		align-items: center
		.bunt-button
			button-style(color: $clr-primary)
			width: calc(100% - 32px)
		.bunt-input
			input-style(size: compact)
			flex: none
			padding: 0
			width: calc(100% - 32px)
</style>
