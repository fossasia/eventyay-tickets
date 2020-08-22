<template lang="pug">
.c-chat(:class="[mode]")
	template(v-if="channel")
		.main-chat
			scrollbars.timeline(y, ref="timeline", @scroll="timelineScrolled", v-resize-observer="onResize")
				infinite-scroll(v-if="syncedScroll", :loading="fetchingMessages", @load="fetchMessages")
					div
				template(v-for="message of filteredTimeline")
					chat-message(:message="message", :mode="mode", :key="message.event_id")
			.chat-input
				.no-permission(v-if="room && !room.permissions.includes('room:chat.join')") {{ $t('Chat:permission-block:room:chat.join') }}
				bunt-button(v-else-if="!activeJoinedChannel", @click="join", :tooltip="$t('Chat:join-button:tooltip')") {{ $t('Chat:join-button:label') }}
				.no-permission(v-else-if="room && !room.permissions.includes('room:chat.send')") {{ $t('Chat:permission-block:room:chat.send') }}
				chat-input(v-else, @send="send")
		scrollbars.user-list(v-if="mode === 'standalone' && showUserlist && $mq.above['m']", y)
			.user(v-for="user of members", @click="showUserCard($event, user)")
				avatar(:user="user", :size="28")
				span.display-name {{ user ? user.profile.display_name : this.message.sender }}
		chat-user-card(v-if="selectedUser", ref="avatarCard", :sender="selectedUser", @close="selectedUser = null")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import { createPopper } from '@popperjs/core'
import ChatMessage from './ChatMessage'
import InfiniteScroll from './InfiniteScroll'
import Avatar from 'components/Avatar'
import ChatInput from 'components/ChatInput'
import ChatUserCard from 'components/ChatUserCard'

export default {
	components: { ChatMessage, ChatUserCard, Avatar, InfiniteScroll, ChatInput },
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
		},
		showUserlist: {
			type: Boolean,
			default: true
		}
	},
	data () {
		return {
			selectedUser: null,
			scrollPosition: 0,
			syncedScroll: true
		}
	},
	computed: {
		...mapState(['connected']),
		...mapState('chat', ['channel', 'members', 'usersLookup', 'timeline', 'fetchingMessages']),
		...mapGetters('chat', ['activeJoinedChannel']),
		filteredTimeline () {
			// We want to hide join/leave event (a) in rooms with force join (b) in stage chats (c) in direct messages
			const showJoinleave = this.mode === 'standalone' && this.room && !this.room.force_join
			return this.timeline.filter(message => (showJoinleave || message.event_type !== 'channel.member') && message.content.type !== 'deleted' && !message.replaces)
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
			await this.$nextTick()
			// TODO scroll to bottom when resizing
			// restore scrollPosition after load
			this.refreshScrollbar()
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
		onResize () {
			this.refreshScrollbar()
		},
		refreshScrollbar () {
			const scrollEl = this.$refs.timeline.$refs.content
			this.$refs.timeline.scrollTop(scrollEl.scrollHeight - this.scrollPosition - scrollEl.clientHeight)
		},
		join () {
			this.$store.dispatch('chat/join')
		},
		send (message) {
			this.$store.dispatch('chat/sendMessage', {text: message})
		},
		async showUserCard (event, user) {
			this.selectedUser = user
			await this.$nextTick()
			const target = event.target.closest('.user')
			createPopper(target, this.$refs.avatarCard.$refs.card, {
				placement: 'left-start',
				modifiers: [{
					name: 'flip',
					options: {
						flipVariations: false
					}
				}]
			})
		}
	}
}
</script>
<style lang="stylus">
.c-chat
	flex: auto
	background-color: $clr-white
	display: flex
	.main-chat
		flex: auto
		display: flex
		flex-direction: column
	.timeline
		flex: 1
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
		min-height: 56px
		padding: 8px 0
		box-sizing: border-box
		display: flex
		justify-content: center
		align-items: center
		.bunt-button
			themed-button-primary()
			width: calc(100% - 16px)
	&:not(.standalone)
		justify-content: flex-end
	&.standalone
		min-height: 0
		.timeline
			grid-area: timeline
		.chat-input
			grid-area: input
		.user-list
			flex: none
			width: 240px
			grid-area: sidebar
			border-left: border-separator()
			.scroll-content
				padding: 16px 0
			.user
				display: flex
				align-items: center
				cursor: pointer
				padding: 2px 16px
				&:hover
					background-color: $clr-grey-100
				.display-name
					font-weight: 600
					color: $clr-secondary-text-light
					margin-left: 8px
</style>
