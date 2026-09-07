<template lang="pug">
.c-room-manager
	dashboard-layout
		panel.media
			.manage-room-header
				bunt-icon-button.btn-back(@click="$router.push({name: 'admin:rooms:index'})", :tooltip="$t('Back to Rooms & Stages')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
				.manage-room-title(v-if="room") {{ room.name }}
				router-link.btn-edit-settings(v-if="hasPermission('room:update')", :to="{name: 'admin:rooms:item', params: {roomId: room.id}}")
					i.mdi.mdi-cog-outline
					span {{ $t('Edit Settings') }}
			media-source-placeholder
		panel.schedule(v-if="$features.enabled('schedule-control')")
			.header
				h3 {{ $t('Schedule') }}
			SchedulePanel(:room="room")
		panel.polls(v-if="modules['poll']")
			.header
				h3 {{ $t('Polls') }}
				.actions
					bunt-button#btn-create-poll(@click="showCreatePollPrompt") {{ $t('Create Poll') }}
					bunt-icon-button(@click="showUrlPopup('poll', $event)") presentation
			polls(:module="modules['poll']", @edit="startEditingPoll")
		panel.questions(v-if="modules['question']")
			.header
				h3 {{ $t('Questions') }}
				.actions
					bunt-icon-button(@click="showUrlPopup('question', $event)") presentation
					menu-dropdown(v-if="hasPermission('room:question.moderate')", v-model="showingQuestionsMenu", strategy="fixed")
						template(#button="{toggle}")
							bunt-icon-button(@click="toggle") dots-vertical
						template(#menu)
							.archive-all(@click="$store.dispatch('question/archiveAll')") {{ $t('Archive All') }}
			questions(:module="modules['question']")
		panel.chat(v-if="modules['chat.native']")
			.header.chat-manage-header
				h3 {{ $t('Chat') }}
				.chat-toolbar
					bunt-switch(
						v-if="canModerateChat",
						name="chat-moderation",
						v-model="moderationEnabled",
						:label="$t('Moderation')"
					)
					label.delay-field(v-if="canModerateChat && moderationEnabled")
						span {{ $t('Delay') }}
						select(v-model.number="moderationDelay")
							option(:value="3") 3s
							option(:value="5") 5s
							option(:value="10") 10s
							option(:value="15") 15s
							option(:value="0") {{ $t('Off') }}
					bunt-icon-button(@click="showUrlPopup('chat', $event)", :title="$t('Presentation Link')") presentation

			.moderation-queue(v-if="canModerateChat && moderationEnabled && pendingQueue.length > 0")
				.queue-header
					i.mdi.mdi-shield-clock-outline
					span {{ $t('Pending Moderation Queue') }} ({{ pendingQueue.length }})
				.queue-items
					.queue-item(v-for="item in pendingQueue", :key="item.id")
						.item-top
							span.author {{ item.authorName }}
							span.timer-badge {{ item.remainingSeconds || 10 }}s
						.item-text {{ item.content }}
						.progress-track
							.progress-fill(:style="{ width: item.progressPercent + '%' }")
						.item-actions
							button.btn-mod-approve(@click="approveMessage(item)")
								i.mdi.mdi-check
								span {{ $t('Approve') }}
							button.btn-mod-reject(@click="rejectMessage(item)")
								i.mdi.mdi-close
								span {{ $t('Reject') }}

			chat(:room="room", :module="modules['chat.native']", mode="compact", :key="room.id", :hidden-message-ids="pendingMessageIds")
		panel.no-modules(v-if="Object.keys(modules).length === 1")
			p {{ $t('No modules to manage in this room') }}
	.ui-background-blocker(v-if="showingPresentationUrlFor", @click="showingPresentationUrlFor = null")
	transition(name="url-popup-anim")
		.url-popup(v-if="showingPresentationUrlFor", ref="urlPopup")
			.url-popup-content
				copyable-text(
					:url="getPresentationUrl(showingPresentationUrlFor)",
					:label="$t('Presentation Link')",
					:hint="$t('This URL contains your presentation access token. Keep it secure.')",
					:show-launch="true",
					:compact="true"
				)
	transition(name="prompt")
		// TODO less hacks
		prompt.create-poll-prompt(v-if="editedPoll", @close="editedPoll = null")
			.content
				h1 {{ editedPoll.id ? $t('Edit Poll') : $t('Create a Poll') }}
				.form-content
					bunt-input-outline-container(name="poll-question", :label="$t('Question')")
						template(#default="{focus, blur}")
							textarea(v-model="editedPoll.content", @focus="focus", @blur="blur")
					.option(v-for="(option, index) of editedPoll.options")
						bunt-input(:name="`poll-option-${index}`", :label="$t('Option {{n}}', {n: index + 1})", v-model="option.content")
						bunt-icon-button.btn-delete-poll-option(@click="editedPoll.options.splice(index, 1)") delete-outline
					bunt-button#btn-add-poll-option(@click="editedPoll.options.push({content: ''})") {{ $t('Add Option') }}
				bunt-button#btn-submit-poll(@click="submitPoll") {{ editedPoll.id ? $t('Save Poll') : $t('Create Poll') }}
</template>
<script>
// TODO
// - handle video better (pause, completely cancel? preserve bandwidth?)

import {mapGetters, mapState} from 'vuex'
import { createPopper } from '@popperjs/core'
import CopyableText from 'components/CopyableText'
import DashboardLayout from 'components/dashboard-layout'
import Panel from 'components/dashboard-layout/Panel'
import Chat from 'components/Chat'
import MediaSourcePlaceholder from 'components/MediaSourcePlaceholder'
import MenuDropdown from 'components/MenuDropdown'
import Polls from 'components/Polls'
import Prompt from 'components/Prompt'
import Questions from 'components/Questions'
import SchedulePanel from './ManagePanels/Schedule'

export default {
	name: 'RoomManager',
	components: { Chat, CopyableText, DashboardLayout, MediaSourcePlaceholder, MenuDropdown, Panel, Polls, Prompt, Questions, SchedulePanel },
	props: {
		room: Object,
		modules: Object
	},
	provide: {
		isManaging: true
	},
	data() {
		return {
			showingPresentationUrlFor: null,
			showingQuestionsMenu: false,
			editedPoll: null,
			moderationEnabled: true,
			moderationDelay: 10,
			pendingQueue: [],
			queueTimer: null,
			processedMessageIds: new Set(),
			moderationReady: false
		}
	},
	computed: {
		...mapState(['world', 'token']),
		...mapGetters(['hasPermission']),
		...mapGetters('schedule', ['sessions', 'sessionsScheduledNow']),
		canModerateChat() {
			return this.hasPermission('room:chat.moderate') || this.hasPermission('world:moderate')
		},
		hasOrganiserPermissions() {
			return (
				this.$store.getters.isAdminMode ||
				this.hasPermission('world:users.list') ||
				this.hasPermission('world:update') ||
				this.hasPermission('world:announce') ||
				this.hasPermission('room:update') ||
				this.hasPermission('room:chat.moderate') ||
				this.hasPermission('room:poll.manage') ||
				this.hasPermission('room:question.moderate') ||
				this.hasPermission('world:kiosks.manage')
			)
		},
		pendingMessageIds() {
			return this.pendingQueue.map(item => item.id)
		},
		chatTimeline() {
			return this.$store.state.chat?.timeline || []
		}
	},
	watch: {
		hasOrganiserPermissions(val) {
			if (!val) {
				this.checkPermissions()
			}
		},
		chatTimeline(newTimeline) {
			if (!this.moderationReady) return
			if (!this.moderationEnabled || this.moderationDelay <= 0 || !this.canModerateChat) return
			for (const msg of newTimeline) {
				if (!msg.event_id || this.processedMessageIds.has(msg.event_id)) continue
				this.processedMessageIds.add(msg.event_id)
				if (msg.event_type !== 'channel.message' || msg.content?.type === 'deleted' || msg.replaces) continue
				const delay = this.moderationDelay
				this.pendingQueue.push({
					id: msg.event_id,
					message: msg,
					authorName: msg.sender?.profile?.display_name || msg.sender?.name || 'Attendee',
					content: msg.content?.body || msg.content?.text || (typeof msg.content === 'string' ? msg.content : ''),
					remaining: delay,
					totalTime: delay,
					remainingSeconds: delay,
					progressPercent: 100
				})
			}
		},
		moderationEnabled(enabled) {
			if (!enabled) this.pendingQueue = []
		}
	},
	mounted() {
		this.checkPermissions()
		for (const message of this.chatTimeline) {
			if (message.event_id) this.processedMessageIds.add(message.event_id)
		}
		this.moderationReady = true
		this.queueTimer = setInterval(this.tickQueueTimers, 100)
	},
	beforeUnmount() {
		if (this.queueTimer) clearInterval(this.queueTimer)
		if (this._popperInstance) this._popperInstance.destroy()
	},
	methods: {
		checkPermissions() {
			if (!this.hasOrganiserPermissions) {
				const roomId = this.room?.id || this.$route.params.roomId
				if (roomId) {
					this.$router.replace({ name: 'room', params: { roomId } })
				} else {
					this.$router.replace({ name: 'about' })
				}
			}
		},
		async showUrlPopup(type, event) {
			if (this.showingPresentationUrlFor === type) {
				this.showingPresentationUrlFor = null
				return
			}
			this.showingPresentationUrlFor = type
			await this.$nextTick()
			if (this._popperInstance) {
				this._popperInstance.destroy()
			}
			if (this.$refs.urlPopup) {
				this._popperInstance = createPopper(event.currentTarget, this.$refs.urlPopup, {
					placement: 'bottom-end',
					modifiers: [
						{ name: 'offset', options: { offset: [0, 8] } },
						{ name: 'preventOverflow', options: { padding: 8 } }
					]
				})
			}
		},
		showCreatePollPrompt() {
			this.editedPoll = {
				content: '',
				options: [{
					content: ''
				}, {
					content: ''
				}]
			}
		},
		startEditingPoll(poll) {
			// only clone relevant parts of the poll to not update too much
			this.editedPoll = {
				id: poll.id,
				content: poll.content,
				options: poll.options.map(o => Object.assign({}, o))
			}
		},
		submitPoll() {
			if (this.editedPoll.id) {
				this.$store.dispatch('poll/updatePoll', {
					poll: this.editedPoll,
					update: {
						content: this.editedPoll.content,
						options: this.editedPoll.options
					}
				})
			} else {
				this.$store.dispatch('poll/createPoll', this.editedPoll)
			}
			this.editedPoll = null
		},
		getPresentationUrl(type) {
			if (!this.room) return ''
			const resolved = this.$router.resolve({
				name: `standalone:${type}`,
				params: { roomId: this.room.id }
			})
			return window.location.origin + resolved.href + '#token=' + this.token
		},
		tickQueueTimers() {
			if (this.pendingQueue.length === 0) return
			const delta = 0.1
			for (let i = this.pendingQueue.length - 1; i >= 0; i--) {
				const item = this.pendingQueue[i]
				item.remaining -= delta
				item.remainingSeconds = Math.max(0, Math.ceil(item.remaining))
				item.progressPercent = Math.max(0, (item.remaining / item.totalTime) * 100)
				if (item.remaining <= 0) {
					this.pendingQueue.splice(i, 1)
				}
			}
		},
		approveMessage(item) {
			const idx = this.pendingQueue.findIndex(q => q.id === item.id)
			if (idx !== -1) this.pendingQueue.splice(idx, 1)
		},
		rejectMessage(item) {
			const idx = this.pendingQueue.findIndex(q => q.id === item.id)
			if (idx !== -1) this.pendingQueue.splice(idx, 1)
			if (item.message) {
				this.$store.dispatch('chat/deleteMessage', item.message)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-room-manager
	display: flex
	min-height: 0
	flex: auto
	.schedule
		flex: auto
		// margin-top: 360px
		// padding: 16px
		h3
			margin: 0
	.c-dashboard-layout-panel
		display: flex
		flex-direction: column
		min-height: 0
		flex: 1 1 0px
		// width: var(--chatbar-width)
		// border-left: border-separator()
		.header
			display: flex
			justify-content: space-between
			align-items: center
			height: 56px
			border-bottom: border-separator()
			padding: 0 16px
			.actions
				display: flex
				gap: 8px
				align-items: center
			.bunt-icon-button
				icon-button-style(style: clear)
		.c-chat
			min-height: 0
	.media .c-media-source-placeholder
		height: 360px
	.media .manage-room-header
		display: flex
		align-items: center
		height: 56px
		min-height: 56px
		box-sizing: border-box
		padding: 0 16px
		gap: 8px
		border-bottom: border-separator()
		background-color: $clr-white
		.btn-back
			icon-button-style(style: clear)
			flex: none
			margin-right: 4px
		.manage-room-title
			font-size: 20px
			font-weight: 600
			flex: auto
			min-width: 0
			ellipsis()
		.btn-edit-settings
			display: flex
			align-items: center
			gap: 6px
			padding: 6px 12px
			border-radius: 4px
			font-size: 13px
			font-weight: 500
			color: $clr-primary
			text-decoration: none
			white-space: nowrap
			&:hover
				background-color: $clr-grey-100
			.mdi
				font-size: 16px
	.polls
		#btn-create-poll
			themed-button-primary()

	.no-modules
		align-items: center
		p
			color: $clr-secondary-text-light
			margin: 32px
	.url-popup
		z-index: 1000
		width: var(--chatbar-width, 360px)
		max-width: calc(100vw - 32px)
		.url-popup-content
			card()
			display: flex
			flex-direction: column
			justify-content: center
			align-items: stretch
			padding: 16px
			background: var(--clr-surface, #fff)
			border-radius: 8px
			box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15)
			transform-origin: top right
			transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.18s cubic-bezier(0.16, 1, 0.3, 1)

	.url-popup-anim-enter-active, .url-popup-anim-leave-active
		.url-popup-content
			transition: transform 0.18s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.18s cubic-bezier(0.16, 1, 0.3, 1)
	.url-popup-anim-enter-from, .url-popup-anim-leave-to
		.url-popup-content
			opacity: 0
			transform: scale(0.92)
	.create-poll-prompt .content
		display: flex
		flex-direction: column
		align-items: center
		h1
			margin: 16px 0 8px 0
		.form-content
			display: flex
			flex-direction: column
			width: 336px
		.bunt-input-outline-container
			// TODO decopypaste
			textarea
				font-family: $font-stack
				font-size: 16px
				background-color: transparent
				border: none
				outline: none
				resize: vertical
				min-height: 64px

				padding: 0 8px
		.option
			display: flex
			align-items: baseline
			.bunt-input
				flex: auto
				input-style(size: compact)
			.btn-delete-poll-option
				icon-button-style()
				margin-left: 4px

		#btn-add-poll-option
			align-self: flex-start
			themed-button-secondary()
			margin: 16px 0 0 0
		#btn-submit-poll
			align-self: flex-end
			themed-button-primary()
			margin: 16px
	+below(1800px) // total guess
		flex-direction: column
		.modules
			justify-content: flex-end


.c-room-manager .c-dashboard-layout-panel.chat > .header.chat-manage-header
	display: flex
	flex-direction: row
	justify-content: space-between
	align-items: center
	flex-wrap: nowrap
	gap: 12px
	height: 56px
	min-height: 56px
	box-sizing: border-box
	h3
		flex: none
		margin: 0
		line-height: 1
		font-size: 16px
	.chat-toolbar
		display: flex
		flex-direction: row
		align-items: center
		flex-wrap: nowrap
		gap: 14px
		margin-left: auto
		height: 32px
		> *
			display: inline-flex
			align-items: center
			margin: 0
			height: 32px
			box-sizing: border-box
		.bunt-switch
			flex: none
			height: 20px
			margin: 0
			margin-bottom: 0
			align-self: center
			white-space: nowrap
			label
				line-height: 20px
				display: inline-flex
				align-items: center
		.delay-field
			flex: none
			gap: 6px
			font-size: 12px
			font-weight: 500
			color: $clr-secondary-text-light
			white-space: nowrap
			line-height: 1
			span
				line-height: 32px
			select
				height: 28px
				padding: 0 8px
				border-radius: 4px
				border: 1px solid rgba(0, 0, 0, 0.15)
				background: #ffffff
				font-size: 12px
				line-height: 26px
				color: $clr-primary-text-light
				margin: 0
		.bunt-icon-button
			flex: none
			align-self: center
			width: 32px
			height: 32px

.panel.chat
	.moderation-queue
		background: #fff8f8
		border: 1px solid #fecaca
		border-radius: 8px
		padding: 10px
		margin: 8px 12px
		display: flex
		flex-direction: column
		gap: 8px
		.queue-header
			display: flex
			align-items: center
			gap: 6px
			font-size: 12px
			font-weight: 700
			color: #dc2626
		.queue-items
			display: flex
			flex-direction: column
			gap: 8px
			max-height: 180px
			overflow-y: auto
		.queue-item
			background: #ffffff
			border: 1px solid rgba(0, 0, 0, 0.08)
			border-radius: 6px
			padding: 8px 10px
			display: flex
			flex-direction: column
			gap: 4px
			box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04)
			.item-top
				display: flex
				justify-content: space-between
				font-size: 12px
				.author
					font-weight: 600
				.timer-badge
					background: #fee2e2
					color: #dc2626
					padding: 1px 6px
					border-radius: 10px
					font-weight: 700
			.item-text
				font-size: 13px
				color: #374151
				word-break: break-word
			.progress-track
				height: 4px
				background: #e5e7eb
				border-radius: 2px
				overflow: hidden
				.progress-fill
					height: 100%
					background: linear-gradient(90deg, #ef4444, #f59e0b)
					transition: width 0.1s linear
			.item-actions
				display: flex
				gap: 8px
				margin-top: 4px
				button
					display: inline-flex
					align-items: center
					gap: 4px
					padding: 3px 10px
					border-radius: 4px
					font-size: 12px
					font-weight: 600
					cursor: pointer
					border: none
					&.btn-mod-approve
						background: #10b981
						color: #ffffff
						&:hover
							background: #059669
					&.btn-mod-reject
						background: #ef4444
						color: #ffffff
						&:hover
							background: #dc2626

@media (max-width: 768px)
	.c-room-manager
		flex-direction: column
		.c-dashboard-layout-panel
			width: 100% !important
			flex: auto
</style>
