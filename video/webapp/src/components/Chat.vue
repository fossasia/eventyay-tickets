<template lang="pug">
.c-chat(:class="[mode]")
	template(v-if="channel")
		scrollbars.timeline(y, ref="timeline", @scroll="timelineScrolled")
			infinite-scroll(v-if="syncedScroll", :loading="fetchingMessages", @load="fetchMessages")
			template(v-for="message of filteredTimeline")
				chat-message(:message="message", :mode="mode", :key="message.event_id")
		.chat-input
			bunt-button(v-if="!hasJoinedChannel", @click="join", :tooltip="$t('Chat:join-button:tooltip')") {{ $t('Chat:join-button:label') }}
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
			scrollPosition: 0,
			syncedScroll: true
		}
	},
	computed: {
		...mapState(['connected']),
		...mapState('chat', ['channel', 'members', 'usersLookup', 'timeline', 'fetchingMessages']),
		...mapGetters('chat', ['hasJoinedChannel']),
		filteredTimeline () {
			if (this.mode === 'standalone') return this.timeline
			return this.timeline.filter(message => message.event_type === 'channel.message')
		}
	},
	watch: {
		connected (value) {
			if (value) {
				// resubscribe
				this.$store.dispatch('chat/subscribe', {channel: this.module.channel_id, config: this.module.config})
			}
		},
		async filteredTimeline () {
			// TODO scroll to bottom when resizing
			if (this.scrollPosition === 0) {
				await this.$nextTick()
				this.$refs.timeline.scrollTop(Infinity)
			} else {
				// restore scrollPosition after load
				await this.$nextTick()
				const scrollEl = this.$refs.timeline.$refs.content
				this.$refs.timeline.scrollTop(scrollEl.scrollHeight - this.scrollPosition - scrollEl.clientHeight)
			}
			this.syncedScroll = true
		}
	},
	created () {
		this.$store.dispatch('chat/subscribe', {channel: this.module.channel_id, config: this.module.config})
	},
	beforeDestroy () {
		this.$store.dispatch('chat/unsubscribe')
	},
	methods: {
		fetchMessages () {
			this.syncedScroll = false
			this.$store.dispatch('chat/fetchMessages')
		},
		timelineScrolled (event) {
			const scrollEl = this.$refs.timeline.$refs.content
			this.scrollPosition = scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight
		},
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
		display: flex
		overflow-anchor: none
		.message
			padding-top: 8px
		> :first-child
			margin-top: auto
	.chat-input
		flex: none
		border-top: border-separator()
		height: 56px
		display: flex
		justify-content: center
		align-items: center
		.bunt-button
			themed-button-primary()
			width: calc(100% - 16px)
	&:not(.standalone)
		justify-content: flex-end
	&.standalone
		display: grid
		grid-template-rows: calc(100% - 56px) 56px // because safari can't even do "auto" right
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
			grid-template-rows: calc(100% - 56px) 56px
			grid-template-columns: auto
			grid-template-areas: "timeline" "input"
</style>
