<template lang="pug">
.c-chat(:class="[mode]")
	template(v-if="channel")
		scrollbars.timeline(y)
			template(v-for="message of filteredTimeline")
				chat-message(v-if="message.event_type === 'channel.message'", :message="message", :mode="mode", :key="message.event_id")
				.system-message(v-else)
					template(v-if="message.event_type === 'channel.member'")
						| {{ usersLookup[message.content.user.id] ? usersLookup[message.content.user.id].profile.display_name : message.content.user.profile.display_name }} {{ message.content.membership === 'join' ? 'joined' : 'left' }}
			infinite-scroll(:loading="fetchingMessages", @load="$store.dispatch('chat/fetchMessages')")
		.chat-input
			bunt-button(v-if="!hasJoined", @click="join", tooltip="to start writing, join this channel") join chat
			bunt-input(v-else, name="chat-composer", v-model="composingMessage", @keydown.native.enter="send")
		.user-list(v-if="mode === 'standalone'")
			.user(v-for="user of members")
				avatar(:user="user", :size="28")
				span.display-name {{ user ? user.profile.display_name : this.message.sender }}
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState } from 'vuex'
import ChatMessage from './ChatMessage'
import InfiniteScroll from './InfiniteScroll'
import Avatar from 'components/Avatar'

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
	components: { ChatMessage, Avatar, InfiniteScroll },
	data () {
		return {
			composingMessage: ''
		}
	},
	computed: {
		...mapState(['connected']),
		...mapState('chat', ['channel', 'hasJoined', 'members', 'usersLookup', 'timeline', 'fetchingMessages']),
		filteredTimeline () {
			if (this.mode === 'standalone') return this.timeline.slice().reverse()
			return this.timeline.filter(message => message.event_type === 'channel.message').reverse()
		}
	},
	watch: {
		connected (value) {
			if (value) {
				// resubscribe
				this.$store.dispatch('chat/subscribe', this.module.channel_id)
			}
		}
	},
	created () {
		this.$store.dispatch('chat/subscribe', this.module.channel_id)
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
	flex: auto
	.timeline .scroll-content
		flex: auto
		padding: 8px 0
		display: flex
		flex-direction: column-reverse
		justify-content: flex-start
		.message
			padding-top: 8px
		.system-message
			color: $clr-secondary-text-light
			padding: 4px 32px
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
	&:not(.standalone)
		justify-content: flex-end
	&.standalone
		display: grid
		grid-template-rows: auto 64px
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
			padding: 0 16px
			border-left: border-separator()
			.user
				display: flex
				align-items: center
				.display-name
					font-weight: 600
					color: $clr-secondary-text-light
					margin-left: 8px
</style>
