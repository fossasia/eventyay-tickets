<template lang="pug">
.c-chat
	template(v-if="channel")
		.timeline
			chat-message(v-for="message of timeline", :message="message")
		.chat-input
			bunt-button(v-if="!hasJoined", @click="join", tooltip="to start writing, join this channel") join chat
			bunt-input(v-else, name="chat-composer", v-model="composingMessage", @keydown.native.enter="send")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState } from 'vuex'
import ChatMessage from './ChatMessage'

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
	components: { ChatMessage },
	data () {
		return {
			composingMessage: ''
		}
	},
	computed: {
		...mapState('chat', ['channel', 'hasJoined', 'members', 'timeline']),
	},
	created () {
		this.$store.dispatch('chat/subscribe', this.room.id)
	},
	mounted () {
		this.$nextTick(() => {
		})
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
		margin: 8px 0
		display: flex
		flex-direction: column
		justify-content: flex-end
		.message
			padding-top: 8px
	.chat-input
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
