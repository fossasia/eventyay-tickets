<template lang="pug">
.c-chat(:class="[mode]")
	template(v-if="channel")
		.main-chat
			scrollbars.timeline(y, ref="timeline", @scroll="timelineScrolled", v-resize-observer="onResize", @resize="onResize")
				infinite-scroll(v-if="syncedScroll", :loading="fetchingMessages", @load="fetchMessages")
					div
				chat-message(v-for="(message, index) of filteredTimeline", :key="message.event_id", :message="message", :previousMessage="filteredTimeline[index - 1]", :nextMessage="filteredTimeline[index + 1]", :mode="mode", @showUserCard="showUserCard")
			.warning(v-if="mergedWarning")
				.content
					ChatContent(:content="$t('Chat:warning:missed-users', {count: mergedWarning.missed_users.length, missedUsers: mergedWarning.missed_users})", @clickMention="showUserCard")
				bunt-icon-button(@click="$store.dispatch('chat/dismissWarnings')") close
			.chat-input
				.no-permission(v-if="room && !room.permissions.includes('room:chat.join')") {{ $t('Chat:permission-block:room:chat.join') }}
				bunt-button(v-else-if="!activeJoinedChannel", @click="join", :tooltip="$t('Chat:join-button:tooltip')") {{ $t('Chat:join-button:label') }}
				.no-permission(v-else-if="room && !room.permissions.includes('room:chat.send')") {{ $t('Chat:permission-block:room:chat.send') }}
				chat-input(v-else, @send="send")
		.user-list(v-if="mode === 'standalone' && showUserlist && $mq.above['m']")
			.user-list-info(v-if="sortedMembers.length > 2")
				span Channel members
				.user-count
					| {{ sortedMembers.length }}
			scrollbars(y)
				.user(v-for="user of sortedMembers", @click="showUserCard($event, user)")
					avatar(:user="user", :size="28")
					span.display-name
						| {{ user.profile.display_name }}
						span.ui-badge(v-for="badge in user.badges") {{ badge }}
		chat-user-card(v-if="userCardUser", ref="avatarCard", :user="userCardUser", @close="userCardUser = false")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import { createPopper } from '@popperjs/core'

import ChatContent from 'components/ChatContent'
import Avatar from 'components/Avatar'
import ChatInput from 'components/ChatInput'
import ChatUserCard from 'components/ChatUserCard'
import ChatMessage from './ChatMessage'
import InfiniteScroll from './InfiniteScroll'

export default {
	components: { ChatMessage, ChatUserCard, Avatar, InfiniteScroll, ChatInput, ChatContent },
	emits: ['change'],
	props: {
		room: Object,
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
	data() {
		return {
			userCardUser: null,
			scrollPosition: 0,
			syncedScroll: true
		}
	},
	computed: {
		...mapState(['connected']),
		...mapState('chat', ['channel', 'members', 'usersLookup', 'timeline', 'fetchingMessages', 'warnings']),
		...mapGetters('chat', ['activeJoinedChannel']),
		...mapState('poll', ['polls']),
		filteredTimeline() {
			// We want to hide join/leave event (a) in rooms with force join (b) in stage chats (c) in direct messages
			const showJoinleave = this.mode === 'standalone' && this.room && !this.room.force_join
			return this.timeline.filter(message =>
				(showJoinleave || message.event_type !== 'channel.member') &&
				message.content.type !== 'deleted' &&
				!message.replaces &&
				(!message.content.poll_id || this.polls?.find(poll => poll.id === message.content.poll_id))
			)
		},
		sortedMembers() {
			return [...this.members].sort((a, b) => {
				const aBadges = a.badges?.length || 0
				const bBadges = b.badges?.length || 0
				if (aBadges === bBadges) {
					return (a.profile?.display_name || '').localeCompare(b.profile?.display_name || '')
				}
				return bBadges - aBadges
			})
		},
		mergedWarning() {
			if (!this.warnings.length) return null
			return { 
				missed_users: this.warnings.flatMap(warning => 
					warning.missed_users.map(user => '@' + user.id))
			}
		}
	},
	watch: {
		connected(value) {
			if (value) {
				// resubscribe
				this.$store.dispatch('chat/subscribe', {channel: this.module.channel_id, config: this.module.config})
			}
		},
		async filteredTimeline() {
			await this.$nextTick()
			// TODO scroll to bottom when resizing
			// restore scrollPosition after load
			this.refreshScrollbar()
			this.syncedScroll = true
			this.$emit('change')
		}
	},
	created() {
		this.$store.dispatch('chat/subscribe', {channel: this.module.channel_id, config: this.module.config})
	},
	beforeUnmount() {
		this.$store.dispatch('chat/unsubscribe')
	},
	methods: {
		fetchMessages() {
			this.syncedScroll = false
			this.$store.dispatch('chat/fetchMessages')
		},
		timelineScrolled(event) {
			const scrollEl = this.$refs.timeline.$refs.content
			this.scrollPosition = scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight
		},
		onResize() {
			this.refreshScrollbar()
		},
		refreshScrollbar() {
			const scrollEl = this.$refs.timeline.$refs.content
			this.$refs.timeline.scrollTop(scrollEl.scrollHeight - this.scrollPosition - scrollEl.clientHeight)
		},
		join() {
			this.$store.dispatch('chat/join')
		},
		send(content) {
			this.$store.dispatch('chat/sendMessage', {content})
		},
		async showUserCard(event, user, placement = 'left-start') {
			console.log(user.id)
			this.userCardUser = user
			await this.$nextTick()
			const target = event.target.closest('.user') || event.target
			createPopper(target, this.$refs.avatarCard.$refs.card, {
				placement,
				strategy: 'fixed',
				modifiers: [{
					name: 'flip',
					options: {
						flipVariations: false
					},
				}, {
					name: 'preventOverflow',
					options: {
						padding: 8
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
		min-width: 0
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
	.warning
		display: flex
		align-items: center
		justify-content: space-between
		padding: 0 0 0 16px
		background-color: $clr-orange-100
		border-radius: 8px
		margin: 8px 14px 0 14px
		.bunt-icon-button
			icon-button-style(style: clear)
	.content .mention
		display: inline-block
		background-color: var(--clr-primary)
		color: var(--clr-input-primary-fg)
		font-weight: 500
		border-radius: 4px
		padding: 0 2px
		cursor: pointer
		&::before
			content: '@'
			font-family: monospace
	.chat-input
		flex: none
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
		min-width: 0
		.timeline
			grid-area: timeline
		.chat-input
			grid-area: input
		.user-list
			flex: none
			display: flex
			flex-direction: column
			width: 240px
			grid-area: sidebar
			border-left: border-separator()
			.c-scrollbars
				flex: auto
				.scroll-content
					padding: 16px 0
			.user
				flex: none
				display: flex
				align-items: center
				cursor: pointer
				padding: 2px 16px
				&:hover
					background-color: $clr-grey-100
				.display-name
					margin-left: 8px
			.user-list-info
				flex: none
				display: flex
				justify-content: space-between
				padding: 16px
				background-color: $clr-grey-100
				text-align: right
				.user-count
					font-weight: 600
					color: $clr-secondary-text-light
</style>
