<template lang="pug">
.c-room-manager
	dashboard-layout
		panel.media
			.manage-room-header
				bunt-icon-button.btn-back(@click="onBack", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
				.manage-room-title(v-if="room") {{ room.name }}
				router-link.btn-edit-settings(v-if="hasPermission('room:update')", :to="{name: 'admin:rooms:item', params: {roomId: room.id}}")
					i.mdi.mdi-cog-outline
					span {{ $t('Edit Settings') }}
			.server-stream-disabled-banner(v-if="isServerStreamRoom && isRoomDisabled")
				i.mdi.mdi-alert-circle-outline
				.banner-content
					.banner-title {{ $t('Feature Disabled') }}
					.banner-message {{ $t('This feature is no longer available. Please contact system administrator.') }}
			media-source-placeholder(v-else)
		panel.schedule(v-if="$features.enabled('schedule-control') && !isServerStreamRoom")
			.header
				h3 {{ $t('Schedule') }}
			SchedulePanel(:room="room")
		panel.polls(v-if="!isServerStreamRoom && !isEmbeddedSuiteRoom && modules['poll']")
			.header
				h3 {{ $t('Polls') }}
				.actions
					bunt-button#btn-create-poll(@click="showCreatePollPrompt") {{ $t('Create Poll') }}
					bunt-icon-button(@click="showUrlPopup('poll', $event)") presentation
			polls(:module="modules['poll']", @edit="startEditingPoll")
		panel.questions(v-if="!isServerStreamRoom && !isEmbeddedSuiteRoom && modules['question']")
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
		panel.chat(v-if="!isServerStreamRoom && !isEmbeddedSuiteRoom && modules['chat.native']")
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
		panel.server-stream(v-if="isServerStreamRoom")
			.header
				h3 {{ serverStreamInfo.title }}
				.status-badge(:class="isRoomDisabled ? 'badge-disabled' : 'badge-active'")
					i.mdi(:class="isRoomDisabled ? 'mdi-cancel' : 'mdi-check-circle'")
					span {{ isRoomDisabled ? $t('Disabled') : $t('Active') }}
			.server-stream-body
				.server-stream-notice(v-if="isRoomDisabled")
					i.mdi.mdi-alert-circle-outline
					.notice-body
						.notice-title {{ $t('This feature is no longer available. Please contact system administrator.') }}
						.notice-desc {{ $t('This server-based video provider has been disabled by administrators. Attendees cannot view or access this room.') }}
				.action-cards
					.action-card
						.action-icon(:class="serverStreamInfo.providerId")
							i.mdi(:class="serverStreamInfo.icon")
						.action-details
							h4 {{ $t('Join / Launch Meeting') }}
							p {{ $t('Launch the video conference with moderator privileges.') }}
						router-link.btn-action(
							v-if="!isRoomDisabled",
							:to="{name: 'room', params: {roomId: room.id}}"
						)
							i.mdi.mdi-open-in-new
							span {{ $t('Join as Host') }}
						span.btn-action.btn-action--disabled(v-else)
							i.mdi.mdi-cancel
							span {{ $t('Unavailable') }}
					.action-card
						.action-icon.share-icon
							i.mdi.mdi-share-variant-outline
						.action-details
							h4 {{ $t('Attendee Link') }}
							p {{ $t('Direct URL to share with attendees or speakers.') }}
						button.btn-action.btn-action--copy(type="button", @click="copyRoomLink")
							i.mdi(:class="copiedLink ? 'mdi-check' : 'mdi-content-copy'")
							span {{ copiedLink ? $t('Copied!') : $t('Copy Link') }}
				.metrics-grid
					.metric-card
						.metric-value {{ occupancyCount }}
						.metric-label
							i.mdi.mdi-account-group-outline
							span {{ occupancyCount === 1 ? $t('Participant') : $t('Participants') }}
					.metric-card
						.metric-value {{ serverStreamInfo.providerName }}
						.metric-label
							i.mdi.mdi-server-network
							span {{ $t('Provider') }}
					.metric-card
						.metric-value {{ roomServerInfo }}
						.metric-label
							i.mdi.mdi-router-wireless
							span {{ $t('Assigned Server') }}
				.minimal-schedule-section(v-if="$features.enabled('schedule-control')")
					.minimal-schedule-header(@click="scheduleExpanded = !scheduleExpanded")
						.header-left
							i.mdi.mdi-calendar-clock-outline
							span.section-title {{ $t('Room Schedule') }}
							span.minimal-badge {{ $t('Minimal') }}
						.header-right
							span.schedule-state {{ scheduleComputeSession ? $t('Auto-compute: On') : $t('Auto-compute: Off') }}
							i.mdi(:class="scheduleExpanded ? 'mdi-chevron-up' : 'mdi-chevron-down'")
					.minimal-schedule-body(v-show="scheduleExpanded")
						SchedulePanel(:room="room")
				.config-section(v-if="activeConfigList.length > 0")
					.config-section-header
						h4 {{ $t('Room Controls & Moderation Policies') }}
						.config-save-badge(v-if="configSaveSuccess")
							i.mdi.mdi-check-circle
							span {{ $t('Saved') }}
						.config-saving-spinner(v-else-if="isSavingConfig")
							i.mdi.mdi-loading.mdi-spin
							span {{ $t('Updating…') }}
					.config-grid
						.config-item(
							v-for="item in activeConfigList",
							:key="item.key",
							:class="{'is-interactive': canManageSettings, 'is-saving': savingKey === item.key}"
						)
							.config-item-main
								.config-label-group
									span.config-label {{ item.label }}
									span.config-desc(v-if="item.description") {{ item.description }}
								.config-action(v-if="canManageSettings")
									button.btn-config-toggle(
										type="button",
										:class="item.enabled ? 'toggle-on' : 'toggle-off'",
										:disabled="isSavingConfig",
										@click="toggleConfigSetting(item)"
									)
										span.toggle-slider
										span.toggle-text {{ item.value }}
								span.config-value(v-else, :class="item.enabled ? 'val-enabled' : 'val-disabled'")
									i.mdi(:class="item.enabled ? 'mdi-check' : 'mdi-close'")
									span {{ item.value }}
				.moderation-guidance
					i.mdi.mdi-information-outline
					.guidance-text
						strong {{ $t('In-Meeting Moderation') }}:&nbsp;
						span {{ $t('Audio muting, webcam controls, presentation sharing, and attendee moderation are managed in real time directly within the meeting window.') }}
		panel.no-modules(v-if="Object.keys(modules).length === 1 && !isServerStreamRoom")
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
import { hasEmbeddedSuite, isRoomVisibleToAttendee } from 'lib/video-providers'
import { getRoomOccupancyCount } from 'lib/room-occupancy'

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
			moderationReady: false,
			copiedLink: false,
			scheduleExpanded: false,
			isSavingConfig: false,
			savingKey: null,
			configSaveSuccess: false
		}
	},
	computed: {
		...mapState(['world', 'token']),
		...mapGetters(['hasPermission']),
		...mapGetters('schedule', ['sessions', 'sessionsScheduledNow']),
		isEmbeddedSuiteRoom() {
			return hasEmbeddedSuite(this.modules)
		},
		canModerateChat() {
			return this.hasPermission('room:chat.moderate') || this.hasPermission('world:moderate')
		},
		hasOrganiserPermissions() {
			if (!window.eventyay?.isOrganizerArea) return false
			return (
				this.$store.getters.isAdminMode ||
				this.hasPermission('world:users.list') ||
				this.hasPermission('world:update') ||
				this.hasPermission('world:announce') ||
				this.hasPermission('room:update') ||
				this.hasPermission('room:chat.moderate') ||
				this.hasPermission('room:poll.manage') ||
				this.hasPermission('room:question.moderate') ||
				this.hasPermission('world:kiosks.manage') ||
				this.hasPermission('room:januscall.moderate') ||
				this.hasPermission('room:jitsi.moderate') ||
				this.hasPermission('room:bbb.moderate') ||
				this.hasPermission('room:loungemesh.moderate')
			)
		},
		canManageSettings() {
			return (
				this.$store.getters.isAdminMode ||
				this.hasPermission('world:update') ||
				this.hasPermission('room:update') ||
				(this.modules?.['call.janus'] && this.hasPermission('room:januscall.moderate')) ||
				(this.modules?.['call.jitsi'] && this.hasPermission('room:jitsi.moderate')) ||
				(this.modules?.['call.bigbluebutton'] && this.hasPermission('room:bbb.moderate')) ||
				(this.modules?.['call.loungemesh'] && this.hasPermission('room:loungemesh.moderate')) ||
				(this.modules?.['call.zoom'] && (this.hasPermission('room:update') || this.$store.getters.isAdminMode))
			)
		},
		scheduleComputeSession() {
			return Boolean(this.room?.schedule_data?.computeSession)
		},
		pendingMessageIds() {
			return this.pendingQueue.map(item => item.id)
		},
		chatTimeline() {
			return this.$store.state.chat?.timeline || []
		},
		serverStreamModule() {
			if (!this.modules) return null
			return (
				this.modules['call.bigbluebutton'] ||
				this.modules['call.jitsi'] ||
				this.modules['call.janus'] ||
				this.modules['call.loungemesh'] ||
				this.modules['call.zoom'] ||
				null
			)
		},
		isServerStreamRoom() {
			return Boolean(this.serverStreamModule)
		},
		isRoomDisabled() {
			if (!this.room) return false
			if (this.room.is_disabled) return true
			return !isRoomVisibleToAttendee(this.room, this.world?.video_providers)
		},
		occupancyCount() {
			if (!this.room) return 0
			return getRoomOccupancyCount(this.room, {
				rooms: this.$store.state.rooms,
				activeRoomId: this.$store.state.activeRoom?.id,
				routeRoomId: this.$route.params.roomId,
				roomViewers: this.$store.state.roomViewers,
			})
		},
		serverStreamInfo() {
			if (this.modules['call.bigbluebutton']) {
				return {
					providerId: 'bbb',
					providerName: 'BigBlueButton',
					title: this.$t('BigBlueButton Video Conference'),
					icon: 'mdi-school',
					description: this.$t('Real-time collaborative conference with presentation slides, breakout rooms, and moderation.')
				}
			}
			if (this.modules['call.jitsi']) {
				return {
					providerId: 'jitsi',
					providerName: 'Jitsi Meet',
					title: this.$t('Jitsi Meet Video Conference'),
					icon: 'mdi-video',
					description: this.$t('Encrypted video meeting with JWT role-based access and screen sharing.')
				}
			}
			if (this.modules['call.loungemesh']) {
				return {
					providerId: 'loungemesh',
					providerName: 'LoungeMesh',
					title: this.$t('LoungeMesh Spatial Lounge'),
					icon: 'mdi-account-group',
					description: this.$t('Spatial proximity networking lounge with collaborative notes and interactive whiteboard.')
				}
			}
			if (this.modules['call.janus']) {
				return {
					providerId: 'janus',
					providerName: 'Janus',
					title: this.$t('Janus Video Channel'),
					icon: 'mdi-webcam',
					description: this.$t('High-performance WebRTC SFU video channel.')
				}
			}
			if (this.modules['call.zoom']) {
				return {
					providerId: 'zoom',
					providerName: 'Zoom',
					title: this.$t('Zoom Video Conference'),
					icon: 'mdi-video',
					description: this.$t('Embedded Zoom Web client or desktop app integration.')
				}
			}
			return {
				providerId: 'unknown',
				providerName: this.$t('Server Stream'),
				title: this.$t('Server Stream Conference'),
				icon: 'mdi-video',
				description: ''
			}
		},
		roomServerInfo() {
			const mod = this.serverStreamModule
			if (this.modules?.['call.zoom']) {
				const meetingNo = this.modules['call.zoom']?.config?.meeting_number
				return meetingNo ? `ID: ${meetingNo}` : this.$t('Cloud Direct')
			}
			if (mod?.config?.prefer_server) {
				return String(mod.config.prefer_server)
			}
			return this.$t('Cluster Default')
		},
		activeConfigList() {
			const mod = this.serverStreamModule
			const cfg = mod?.config || {}
			const list = []
			if (this.modules['call.bigbluebutton']) {
				list.push({
					key: 'waiting_room',
					label: this.$t('Waiting Room'),
					description: this.$t('Require moderator approval before attendees join'),
					value: cfg.waiting_room ? this.$t('Enabled') : this.$t('Disabled'),
					enabled: Boolean(cfg.waiting_room)
				})
				list.push({
					key: 'bbb_mute_on_start',
					label: this.$t('Auto-Mute on Join'),
					description: this.$t('Mute microphone by default on start'),
					value: cfg.bbb_mute_on_start ? this.$t('Enabled') : this.$t('Disabled'),
					enabled: Boolean(cfg.bbb_mute_on_start)
				})
				list.push({
					key: 'record',
					label: this.$t('Allow Recording'),
					description: this.$t('Permit conference recording'),
					value: cfg.record ? this.$t('Allowed') : this.$t('Disabled'),
					enabled: Boolean(cfg.record)
				})
				list.push({
					key: 'bbb_disable_cam',
					label: this.$t('Camera Restriction'),
					description: this.$t('Restrict cameras to moderators only'),
					value: cfg.bbb_disable_cam ? this.$t('Moderators Only') : this.$t('All Attendees'),
					enabled: !cfg.bbb_disable_cam
				})
				list.push({
					key: 'bbb_disable_chat',
					label: this.$t('Chat Restriction'),
					description: this.$t('Restrict public chat to moderators only'),
					value: cfg.bbb_disable_chat ? this.$t('Moderators Only') : this.$t('All Attendees'),
					enabled: !cfg.bbb_disable_chat
				})
				list.push({
					key: 'auto_microphone',
					label: this.$t('Auto-Microphone'),
					description: this.$t('Skip microphone confirmation dialog on join'),
					value: cfg.auto_microphone ? this.$t('Enabled') : this.$t('Disabled'),
					enabled: Boolean(cfg.auto_microphone)
				})
			} else if (this.modules['call.jitsi']) {
				list.push({
					key: 'waiting_room',
					label: this.$t('Waiting Room / Lobby'),
					description: this.$t('Require moderator admission before attendees join'),
					value: cfg.waiting_room ? this.$t('Enabled') : this.$t('Disabled'),
					enabled: Boolean(cfg.waiting_room)
				})
				list.push({
					key: 'start_with_audio_muted',
					label: this.$t('Start Audio Muted'),
					description: this.$t('Mute microphone automatically on join'),
					value: cfg.start_with_audio_muted ? this.$t('Yes') : this.$t('No'),
					enabled: Boolean(cfg.start_with_audio_muted)
				})
				list.push({
					key: 'start_with_video_muted',
					label: this.$t('Start Video Muted'),
					description: this.$t('Turn camera off automatically on join'),
					value: cfg.start_with_video_muted ? this.$t('Yes') : this.$t('No'),
					enabled: Boolean(cfg.start_with_video_muted)
				})
				list.push({
					key: 'record',
					label: this.$t('Allow Recording'),
					description: this.$t('Permit meeting recordings for moderators'),
					value: cfg.record ? this.$t('Allowed') : this.$t('Disabled'),
					enabled: Boolean(cfg.record)
				})
				list.push({
					key: 'livestreaming',
					label: this.$t('Allow Live Streaming'),
					description: this.$t('Permit streaming to YouTube/RTMP'),
					value: cfg.livestreaming ? this.$t('Allowed') : this.$t('Disabled'),
					enabled: Boolean(cfg.livestreaming)
				})
				list.push({
					key: 'disable_cam',
					label: this.$t('Camera Restriction'),
					description: this.$t('Restrict video feeds to moderators only'),
					value: cfg.disable_cam ? this.$t('Moderators Only') : this.$t('All Attendees'),
					enabled: !cfg.disable_cam
				})
				list.push({
					key: 'disable_chat',
					label: this.$t('Chat Restriction'),
					description: this.$t('Restrict in-call text chat to moderators only'),
					value: cfg.disable_chat ? this.$t('Moderators Only') : this.$t('All Attendees'),
					enabled: !cfg.disable_chat
				})
				list.push({
					key: 'require_display_name',
					label: this.$t('Require Display Name'),
					description: this.$t('Prompt for attendee name before entering call'),
					value: cfg.require_display_name ? this.$t('Yes') : this.$t('No'),
					enabled: Boolean(cfg.require_display_name)
				})
			} else if (this.modules['call.janus']) {
				list.push({
					key: 'waiting_room',
					label: this.$t('Waiting Room'),
					description: this.$t('Require moderator admission before attendees join'),
					value: cfg.waiting_room ? this.$t('Enabled') : this.$t('Disabled'),
					enabled: Boolean(cfg.waiting_room)
				})
				list.push({
					key: 'start_with_audio_muted',
					label: this.$t('Auto-Mute on Join'),
					description: this.$t('Mute microphone automatically on join'),
					value: cfg.start_with_audio_muted ? this.$t('Enabled') : this.$t('Disabled'),
					enabled: Boolean(cfg.start_with_audio_muted)
				})
				list.push({
					key: 'start_with_video_muted',
					label: this.$t('Start Video Muted'),
					description: this.$t('Turn camera off automatically on join'),
					value: cfg.start_with_video_muted ? this.$t('Yes') : this.$t('No'),
					enabled: Boolean(cfg.start_with_video_muted)
				})
				list.push({
					key: 'disable_cam',
					label: this.$t('Camera Restriction'),
					description: this.$t('Restrict cameras to moderators only'),
					value: cfg.disable_cam ? this.$t('Moderators Only') : this.$t('All Attendees'),
					enabled: !cfg.disable_cam
				})
				list.push({
					key: 'disable_chat',
					label: this.$t('Chat Restriction'),
					description: this.$t('Restrict chat to moderators only'),
					value: cfg.disable_chat ? this.$t('Moderators Only') : this.$t('All Attendees'),
					enabled: !cfg.disable_chat
				})
			} else if (this.modules['call.loungemesh']) {
				list.push({
					key: 'enable_spatial_chat',
					label: this.$t('Spatial Audio & Chat'),
					description: this.$t('Directional audio and proximity-based chat'),
					value: cfg.enable_spatial_chat !== false ? this.$t('Enabled') : this.$t('Disabled'),
					enabled: cfg.enable_spatial_chat !== false
				})
				list.push({
					key: 'enable_notes',
					label: this.$t('Collaborative Notes'),
					description: this.$t('Shared real-time notepad for tables'),
					value: cfg.enable_notes !== false ? this.$t('Enabled') : this.$t('Disabled'),
					enabled: cfg.enable_notes !== false
				})
				list.push({
					key: 'enable_whiteboard',
					label: this.$t('Interactive Whiteboard'),
					description: this.$t('Shared whiteboard and drawing canvas'),
					value: cfg.enable_whiteboard !== false ? this.$t('Enabled') : this.$t('Disabled'),
					enabled: cfg.enable_whiteboard !== false
				})
			} else if (this.modules['call.zoom']) {
				list.push({
					key: 'disable_chat',
					label: this.$t('Chat Restriction'),
					description: this.$t('Disable Zoom in-meeting chat'),
					value: cfg.disable_chat ? this.$t('Chat Disabled') : this.$t('All Attendees'),
					enabled: !cfg.disable_chat
				})
				list.push({
					key: 'has_password',
					label: this.$t('Passcode Protection'),
					description: this.$t('Require meeting passcode for entry'),
					value: cfg.password ? this.$t('Protected') : this.$t('Open Access'),
					enabled: Boolean(cfg.password),
					readOnly: true
				})
			}
			return list
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
		onBack() {
			if (this.room?.id) {
				this.$router.push({ name: 'room', params: { roomId: this.room.id } })
			} else {
				this.$router.push({ name: 'admin:rooms:index' })
			}
		},
		copyRoomLink() {
			if (!this.room) return
			let url
			if (window.eventyay?.publicVideoUrl) {
				const publicBase = window.eventyay.publicVideoUrl.replace(/\/+$/, '')
				url = window.location.origin + publicBase + '/rooms/' + this.room.id
			} else {
				const path = this.$router.resolve({ name: 'room', params: { roomId: this.room.id } }).href
				url = window.location.origin + path
			}
			if (navigator?.clipboard?.writeText) {
				navigator.clipboard.writeText(url).then(() => {
					this.copiedLink = true
					setTimeout(() => { this.copiedLink = false }, 2500)
				}).catch(() => {
					this.copiedLink = false
				})
			}
		},
		async toggleConfigSetting(item) {
			if (!this.canManageSettings || this.isSavingConfig) return
			const mod = this.serverStreamModule
			if (!mod) return
			this.isSavingConfig = true
			this.savingKey = item.key
			try {
				const currentConfig = { ...(mod.config || {}) }
				let newVal
				if (item.key === 'disable_cam' || item.key === 'disable_chat' || item.key === 'bbb_disable_cam' || item.key === 'bbb_disable_chat') {
					newVal = !Boolean(currentConfig[item.key])
				} else if (item.key.startsWith('enable_')) {
					newVal = currentConfig[item.key] === false ? true : false
				} else {
					newVal = !Boolean(currentConfig[item.key])
				}
				currentConfig[item.key] = newVal

				const updatedModules = (this.room.modules || []).map(m => {
					if (m.type === mod.type) {
						return { ...m, config: currentConfig }
					}
					return m
				})

				await api.call('room.config.patch', {
					room: this.room.id,
					module_config: updatedModules
				})
				mod.config = currentConfig
				this.configSaveSuccess = true
				setTimeout(() => {
					this.configSaveSuccess = false
				}, 2500)
			} catch (err) {
				console.error('Failed to update room config:', err)
			} finally {
				this.isSavingConfig = false
				this.savingKey = null
			}
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
	min-width: 0
	max-width: 100%
	flex: auto
	overflow-x: hidden
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

	.server-stream-disabled-banner
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		padding: 48px 24px
		text-align: center
		background-color: #fff8f8
		border-radius: 8px
		margin: 16px
		border: 1px solid #fecaca
		gap: 12px

		> i.mdi
			font-size: 48px
			color: #dc2626

		.banner-content
			.banner-title
				font-size: 18px
				font-weight: 700
				color: #991b1b
				margin-bottom: 6px

			.banner-message
				font-size: 14px
				color: #b91c1c
				max-width: 440px
				line-height: 1.5

	.server-stream
		display: flex
		flex-direction: column
		min-width: 320px
		flex: 1 1 420px

		.header
			display: flex
			justify-content: space-between
			align-items: center
			padding: 12px 16px
			border-bottom: 1px solid rgba(0, 0, 0, 0.08)

			h3
				margin: 0
				font-size: 16px
				font-weight: 700
				color: $clr-primary-text-light

			.status-badge
				display: inline-flex
				align-items: center
				gap: 5px
				padding: 3px 10px
				border-radius: 12px
				font-size: 12px
				font-weight: 600

				&.badge-active
					background: #ecfdf5
					color: #059669
					border: 1px solid #a7f3d0

				&.badge-disabled
					background: #fef2f2
					color: #dc2626
					border: 1px solid #fecaca

		.server-stream-body
			display: flex
			flex-direction: column
			gap: 16px
			padding: 16px
			overflow-y: auto

		.server-stream-notice
			display: flex
			gap: 12px
			align-items: flex-start
			padding: 14px 16px
			background: #fff8f8
			border: 1px solid #fecaca
			border-radius: 8px

			> i.mdi
				font-size: 22px
				color: #dc2626
				flex-shrink: 0
				margin-top: 1px

			.notice-body
				.notice-title
					font-size: 14px
					font-weight: 700
					color: #991b1b
					margin-bottom: 4px
					line-height: 1.4

				.notice-desc
					font-size: 12px
					color: #b91c1c
					line-height: 1.4

		.action-cards
			display: grid
			grid-template-columns: repeat(auto-fit, minmax(200px, 1fr))
			gap: 12px

			.action-card
				display: flex
				flex-direction: column
				gap: 10px
				padding: 14px
				background: #ffffff
				border: 1px solid #e2e8f0
				border-radius: 8px
				box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03)

				.action-icon
					display: flex
					align-items: center
					justify-content: center
					width: 36px
					height: 36px
					border-radius: 8px
					font-size: 20px

					&.bbb
						background: #fef2f2
						color: #dc2626
					&.jitsi
						background: #f0f9ff
						color: #0284c7
					&.loungemesh
						background: #f5f3ff
						color: #7c3aed
					&.janus
						background: #eef2ff
						color: #4f46e5
					&.share-icon
						background: #f8fafc
						color: #475569

				.action-details
					h4
						font-size: 14px
						font-weight: 600
						color: #1e293b
						margin: 0 0 4px 0
					p
						font-size: 12px
						color: #64748b
						margin: 0
						line-height: 1.4

				.btn-action
					display: inline-flex
					align-items: center
					justify-content: center
					gap: 6px
					padding: 8px 12px
					border-radius: 6px
					font-size: 13px
					font-weight: 600
					text-decoration: none
					cursor: pointer
					border: none
					background: $clr-primary
					color: #ffffff
					margin-top: auto
					transition: background 0.15s ease

					&:hover
						background: darken($clr-primary, 10%)

					&.btn-action--disabled
						background: #f1f5f9
						color: #94a3b8
						cursor: not-allowed

					&.btn-action--copy
						background: #f8fafc
						color: #334155
						border: 1px solid #cbd5e1
						&:hover
							background: #e2e8f0

		.metrics-grid
			display: grid
			grid-template-columns: repeat(3, 1fr)
			gap: 10px

			.metric-card
				display: flex
				flex-direction: column
				align-items: center
				justify-content: center
				padding: 12px 8px
				background: #f8fafc
				border: 1px solid #e2e8f0
				border-radius: 8px
				text-align: center

				.metric-value
					font-size: 18px
					font-weight: 700
					color: #0f172a
					margin-bottom: 4px
					white-space: nowrap
					overflow: hidden
					text-overflow: ellipsis
					max-width: 100%

				.metric-label
					display: flex
					align-items: center
					gap: 4px
					font-size: 11px
					font-weight: 600
					color: #64748b
					i
						font-size: 13px

		.minimal-schedule-section
			background: #ffffff
			border: 1px solid #e2e8f0
			border-radius: 8px
			overflow: hidden

			.minimal-schedule-header
				display: flex
				justify-content: space-between
				align-items: center
				padding: 10px 14px
				background: #f8fafc
				cursor: pointer
				user-select: none
				transition: background 0.15s ease

				&:hover
					background: #f1f5f9

				.header-left
					display: flex
					align-items: center
					gap: 8px

					i.mdi
						font-size: 18px
						color: $clr-primary

					.section-title
						font-size: 13px
						font-weight: 700
						color: #1e293b

					.minimal-badge
						display: inline-block
						padding: 2px 6px
						background: #e2e8f0
						color: #475569
						border-radius: 4px
						font-size: 10px
						font-weight: 600
						text-transform: uppercase

				.header-right
					display: flex
					align-items: center
					gap: 8px
					font-size: 12px
					color: #64748b

					i.mdi
						font-size: 18px

			.minimal-schedule-body
				padding: 8px 14px
				border-top: 1px solid #e2e8f0

		.config-section
			background: #ffffff
			border: 1px solid #e2e8f0
			border-radius: 8px
			padding: 14px

			.config-section-header
				display: flex
				justify-content: space-between
				align-items: center
				margin-bottom: 12px

				h4
					font-size: 13px
					font-weight: 700
					color: #334155
					margin: 0
					text-transform: uppercase
					letter-spacing: 0.5px

				.config-save-badge
					display: inline-flex
					align-items: center
					gap: 4px
					font-size: 12px
					color: #059669
					font-weight: 600

				.config-saving-spinner
					display: inline-flex
					align-items: center
					gap: 4px
					font-size: 12px
					color: $clr-primary
					font-weight: 500

			.config-grid
				display: grid
				grid-template-columns: repeat(auto-fit, minmax(220px, 1fr))
				gap: 10px

				.config-item
					display: flex
					justify-content: space-between
					align-items: center
					padding: 10px 12px
					background: #f8fafc
					border: 1px solid #e2e8f0
					border-radius: 6px
					gap: 8px
					transition: border-color 0.15s ease, background 0.15s ease

					&.is-interactive:hover
						background: #f1f5f9
						border-color: #cbd5e1

					&.is-saving
						opacity: 0.6
						pointer-events: none

					.config-item-main
						display: flex
						justify-content: space-between
						align-items: center
						width: 100%
						gap: 10px

					.config-label-group
						display: flex
						flex-direction: column
						gap: 2px

						.config-label
							color: #1e293b
							font-weight: 600
							font-size: 13px

						.config-desc
							color: #64748b
							font-size: 11px
							line-height: 1.3

					.config-action
						flex-shrink: 0

					.btn-config-toggle
						display: inline-flex
						align-items: center
						gap: 6px
						padding: 4px 10px
						border-radius: 14px
						font-size: 12px
						font-weight: 600
						cursor: pointer
						border: 1px solid transparent
						transition: all 0.2s ease

						&.toggle-on
							background: #ecfdf5
							color: #059669
							border-color: #a7f3d0
							&:hover
								background: #d1fae5

						&.toggle-off
							background: #f1f5f9
							color: #64748b
							border-color: #cbd5e1
							&:hover
								background: #e2e8f0

					.config-value
						display: inline-flex
						align-items: center
						gap: 4px
						font-weight: 600
						font-size: 12px

						&.val-enabled
							color: #059669
							i
								font-size: 14px
						&.val-disabled
							color: #94a3b8
							i
								font-size: 14px

		.moderation-guidance
			display: flex
			gap: 10px
			align-items: flex-start
			padding: 12px
			background: #f0f9ff
			border: 1px solid #bae6fd
			border-radius: 8px
			font-size: 12px
			color: #0369a1
			line-height: 1.5

			> i.mdi
				font-size: 18px
				flex-shrink: 0
				margin-top: 1px
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
