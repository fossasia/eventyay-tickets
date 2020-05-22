<template lang="pug">
.c-chat(:class="[mode]")
	template(v-if="channel")
		scrollbars.timeline(y)
			template(v-for="message of filteredTimeline")
				chat-message(:message="message", :mode="mode", :key="message.event_id")
			infinite-scroll(:loading="fetchingMessages", @load="$store.dispatch('chat/fetchMessages')")
		.chat-input
			bunt-button(v-if="!hasJoinedChannel", @click="join", tooltip="to start writing, join this channel") join chat
			chat-input(v-else, @send="send")
		scrollbars.user-list(v-if="mode === 'standalone' && $mq.above['s']", y)
			.user(v-for="user of members")
				avatar(:user="user", :size="28")
				span.display-name {{ user ? user.profile.display_name : this.message.sender }}
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import ChatMessage from './ChatMessage'
import InfiniteScroll from './InfiniteScroll'
import Avatar from 'components/Avatar'
import ChatInput from 'components/ChatInput'

export default {
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true
		},
		mode: {
			type: String, // 'standalone', 'compact'
			default: 'compact'
		}
	},
	components: { ChatMessage, Avatar, InfiniteScroll, ChatInput },
	data () {
		return {
		}
	},
	computed: {
		...mapState(['connected']),
		...mapState('chat', ['channel', 'members', 'usersLookup', 'timeline', 'fetchingMessages']),
		...mapGetters('chat', ['hasJoinedChannel']),
		filteredTimeline () {
			if (this.mode === 'standalone') return this.timeline.slice().reverse()
			return this.timeline.filter(message => message.event_type === 'channel.message').reverse()
		}
	},
	watch: {
		connected (value) {
			if (value) {
				// resubscribe
				this.$store.dispatch('chat/subscribe', {channel: this.module.channel_id, config: this.module.config})
			}
		}
	},
	created () {
		this.$store.dispatch('chat/subscribe', {channel: this.module.channel_id, config: this.module.config})
	},
	beforeDestroy () {
		this.$store.dispatch('chat/unsubscribe')
	},
	methods: {
		join () {
			this.$store.dispatch('chat/join')
		},
		send (message) {
			this.$store.dispatch('chat/sendMessage', {text: message})
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
	flex: auto
	.timeline .scroll-content
		flex: auto
		padding: 8px 0
		display: flex
		flex-direction: column-reverse
		justify-content: flex-start
		.message
			padding-top: 8px
	.chat-input
		flex: none
		border-top: border-separator()
		height: 56px
		display: flex
		justify-content: center
		align-items: center
		.bunt-button
			button-style(color: $clr-primary)
			width: calc(100% - 16px)
	&:not(.standalone)
		justify-content: flex-end
	&.standalone
		display: grid
		grid-template-rows: auto 56px
		grid-template-columns: auto 240px
		grid-template-areas: "timeline sidebar" \
			"input input"
		min-height: 0
		.timeline
			grid-area: timeline
		.chat-input
			grid-area: input
		.user-list
			grid-area: sidebar
			padding: 0 0 0 16px
			border-left: border-separator()
			.user
				display: flex
				align-items: center
				.display-name
					font-weight: 600
					color: $clr-secondary-text-light
					margin-left: 8px
		+below('s')
			grid-template-rows: auto 56px
			grid-template-columns: auto
			grid-template-areas: "timeline" "input"
</style>
