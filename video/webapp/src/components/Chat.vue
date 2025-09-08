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
<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { createPopper } from '@popperjs/core'

import ChatContent from 'components/ChatContent'
import Avatar from 'components/Avatar'
import ChatInput from 'components/ChatInput'
import ChatUserCard from 'components/ChatUserCard'
import ChatMessage from './ChatMessage'
import InfiniteScroll from './InfiniteScroll'

// Props & Emits
const props = defineProps({
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
})
const emit = defineEmits(['change'])

// Store
const store = useStore()

// Local state
const userCardUser = ref(null)
const scrollPosition = ref(0)
const syncedScroll = ref(true)

// Refs to child components
const timeline = ref(null)
const avatarCard = ref(null)

// Store-derived state
const connected = computed(() => store.state.connected)
const channel = computed(() => store.state.chat.channel)
const members = computed(() => store.state.chat.members)
const usersLookup = computed(() => store.state.chat.usersLookup)
const timelineState = computed(() => store.state.chat.timeline)
const fetchingMessages = computed(() => store.state.chat.fetchingMessages)
const warnings = computed(() => store.state.chat.warnings || [])
const activeJoinedChannel = computed(() => store.getters['chat/activeJoinedChannel'])
const polls = computed(() => store.state.poll?.polls)

// Computed values
const filteredTimeline = computed(() => {
	// We want to hide join/leave event (a) in rooms with force join (b) in stage chats (c) in direct messages
	const showJoinleave = props.mode === 'standalone' && props.room && !props.room.force_join
	return (timelineState.value || []).filter(message =>
		(showJoinleave || message.event_type !== 'channel.member') &&
		message.content.type !== 'deleted' &&
		!message.replaces &&
		(!message.content.poll_id || polls.value?.find(poll => poll.id === message.content.poll_id))
	)
})

const sortedMembers = computed(() => {
	return [...(members.value || [])].sort((a, b) => {
		const aBadges = a.badges?.length || 0
		const bBadges = b.badges?.length || 0
		if (aBadges === bBadges) {
			return (a.profile?.display_name || '').localeCompare(b.profile?.display_name || '')
		}
		return bBadges - aBadges
	})
})

const mergedWarning = computed(() => {
	if (!warnings.value?.length) return null
	return {
		missed_users: warnings.value.flatMap(warning =>
			warning.missed_users.map(user => '@' + user.id)
		)
	}
})

// Watchers
watch(connected, (value) => {
	if (value) {
		// resubscribe
		store.dispatch('chat/subscribe', { channel: props.module.channel_id, config: props.module.config })
	}
})

watch(filteredTimeline, async () => {
	await nextTick()
	// TODO scroll to bottom when resizing
	// restore scrollPosition after load
	refreshScrollbar()
	syncedScroll.value = true
	emit('change')
})

// Lifecycle
onMounted(() => {
	store.dispatch('chat/subscribe', { channel: props.module.channel_id, config: props.module.config })
})

onBeforeUnmount(() => {
	store.dispatch('chat/unsubscribe')
})

// Methods
function fetchMessages() {
	syncedScroll.value = false
	store.dispatch('chat/fetchMessages')
}

function timelineScrolled() {
	const scrollEl = timeline.value?.$refs?.content
	if (!scrollEl) return
	scrollPosition.value = scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight
}

function onResize() {
	refreshScrollbar()
}

function refreshScrollbar() {
	const scrollEl = timeline.value?.$refs?.content
	if (!scrollEl || !timeline.value?.scrollTop) return
	timeline.value.scrollTop(scrollEl.scrollHeight - scrollPosition.value - scrollEl.clientHeight)
}

function join() {
	store.dispatch('chat/join')
}

function send(content) {
	store.dispatch('chat/sendMessage', { content })
}

async function showUserCard(event, user, placement = 'left-start') {
	console.log(user.id)
	userCardUser.value = user
	await nextTick()
	const target = event.target.closest('.user') || event.target
	if (!avatarCard.value?.$refs?.card) return
	createPopper(target, avatarCard.value.$refs.card, {
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
