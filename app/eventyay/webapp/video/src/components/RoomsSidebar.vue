<template lang="pug">
aside.c-rooms-sidebar(
	:class="{'sidebar-collapsed': collapsed, 'sidebar-mobile-open': showMobile && !snapBack}",
	:style="style",
	role="navigation",
	:aria-label="$t('Video Navigation')",
	@pointerdown="onPointerdown",
	@pointermove="onPointermove",
	@pointerup="onPointerup",
	@pointercancel="onPointercancel"
)
		.startpage-sidebar-inner
			.startpage-sidebar-context
				router-link.dropdown-toggle(:to="{name: 'about'}", @click="onNavClick")
					span.fa-stack.context-icon-badge
						i.mdi.mdi-video-vintage
					.context-indicator
						span.context-name(v-if="world && world.title", v-html="$emojify(world.title)")
						span.context-name(v-else) {{ $t('Live Video') }}
						span.context-meta(v-if="eventDateSubtitle") {{ eventDateSubtitle }}
						span.context-meta(v-else) {{ $t('Live Video') }}
				bunt-icon-button.btn-close-mobile(
					v-if="$mq.below.m",
					icon="close",
					:aria-label="$t('Close sidebar')",
					@click="$emit('close')"
				)

			ul.startpage-sidebar-nav(role="group", :aria-label="$t('Attendee Navigation')")
				//- Overview
				li
					router-link.nav-link(:to="{name: 'about'}", exact, @click="onNavClick")
						span.fa.mdi.mdi-information-outline(aria-hidden="true")
						span.sidebar-text {{ $t('Overview') }}

				//- Schedule
				li
					router-link.nav-link(:to="{name: 'schedule'}", @click="onNavClick")
						span.fa.mdi.mdi-calendar-blank-outline(aria-hidden="true")
						span.sidebar-text {{ $t('Schedule') }}

				//- Speakers
				li
					router-link.nav-link(:to="{name: 'schedule:speakers'}", @click="onNavClick")
						span.fa.mdi.mdi-account-voice(aria-hidden="true")
						span.sidebar-text {{ $t('Speakers') }}

				//- Custom Pages
				li(v-for="page of roomsByType.page", :key="page.id")
					router-link.nav-link(:to="{name: 'room', params: {roomId: page.id}}", @click="onNavClick")
						span.fa.mdi.mdi-file-document-outline(aria-hidden="true")
						span.sidebar-text(v-html="$emojify(page.name)")

				//- Stages & Streams (collapsible, expanded by default)
				li.nav-fold(v-if="hasStagesOrRooms")
					.has-children
						span.nav-link.nav-link-inner(@click="toggleFold('stages')")
							span.fa.mdi.mdi-video-vintage(aria-hidden="true")
							span.sidebar-text {{ $t('Stages & Rooms') }}
						button.arrow-btn(type="button", :aria-expanded="String(openFolds.stages)", @click.stop="toggleFold('stages')")
							i.fa(:class="openFolds.stages ? 'fa-angle-down' : 'fa-angle-left'", aria-hidden="true")
					transition(name="fold")
						.nav-sub-list(v-show="openFolds.stages")
							router-link.nav-sub-link(
								v-for="stage of roomsByType.stage",
								:key="stage.room.id",
								:to="{name: 'room', params: {roomId: stage.room.id}}",
								:class="{active: stage.room.id === $route.params.roomId}",
								@click="onNavClick"
							)
								span.room-name(v-html="$emojify(stage.room.name)")
								span.viewer-count-badge(:title="getOccupancyTitle(stage.room)", :aria-label="getOccupancyTitle(stage.room)")
									i.mdi.mdi-account-outline(aria-hidden="true")
									span {{ getOccupancyCount(stage.room) }}
								span.notifications(v-if="stage.notifications") {{ stage.notifications }}
							router-link.nav-sub-link(
								v-for="room of roomsByType.networking",
								:key="room.id",
								:to="{name: 'room', params: {roomId: room.id}}",
								:class="{active: room.id === $route.params.roomId}",
								@click="onNavClick"
							)
								span.room-name(v-html="$emojify(room.name)")
								span.viewer-count-badge(:title="getOccupancyTitle(room)", :aria-label="getOccupancyTitle(room)")
									i.mdi.mdi-account-outline(aria-hidden="true")
									span {{ getOccupancyCount(room) }}

				//- Chat Channels (collapsible, expanded by default)
				li.nav-fold(v-if="hasChatChannels")
					.has-children
						span.nav-link.nav-link-inner(@click="toggleFold('channels')")
							span.fa.mdi.mdi-chat-processing-outline(aria-hidden="true")
							span.sidebar-text {{ $t('Chat Channels') }}
						button.arrow-btn(type="button", :aria-expanded="String(openFolds.channels)", @click.stop="toggleFold('channels')")
							i.fa(:class="openFolds.channels ? 'fa-angle-down' : 'fa-angle-left'", aria-hidden="true")
					transition(name="fold")
						.nav-sub-list(v-show="openFolds.channels")
							router-link.nav-sub-link(
								v-for="chat of roomsByType.textChat",
								:key="chat.room.id",
								:to="{name: 'room', params: {roomId: chat.room.id}}",
								:class="{active: chat.room.id === $route.params.roomId, unread: hasUnreadMessages(chat.room.modules[0].channel_id)}",
								@click="onNavClick"
							)
								span.room-name(v-html="$emojify(chat.room.name)")
								span.viewer-count-badge(:title="getOccupancyTitle(chat.room)", :aria-label="getOccupancyTitle(chat.room)")
									i.mdi.mdi-account-outline(aria-hidden="true")
									span {{ getOccupancyCount(chat.room) }}
								span.notifications(v-if="chat.notifications") {{ chat.notifications }}
							router-link.nav-sub-link(
								v-for="chat of roomsByType.videoChat",
								:key="chat.id",
								:to="{name: 'room', params: {roomId: chat.id}}",
								:class="{active: chat.id === $route.params.roomId}",
								@click="onNavClick"
							)
								span.room-name(v-html="$emojify(chat.name)")
								span.viewer-count-badge(:title="getOccupancyTitle(chat)", :aria-label="getOccupancyTitle(chat)")
									i.mdi.mdi-account-outline(aria-hidden="true")
									span {{ getOccupancyCount(chat) }}
							button.nav-sub-link.nav-sub-link--action(type="button", v-if="worldHasTextChannels", @click.prevent="showChannelBrowser = true; onNavClick()")
								span.mdi.mdi-compass-outline(aria-hidden="true")
								span {{ $t('Browse Channels') }}

				//- Direct Messages (distinct collapsible section, expanded by default)
				li.nav-fold(v-if="hasPermission('world:chat.direct') && liveFeatures.direct_messaging")
					.has-children
						span.nav-link.nav-link-inner(@click="toggleFold('dms')")
							span.fa.mdi.mdi-account-multiple-outline(aria-hidden="true")
							span.sidebar-text {{ $t('Direct Messages') }}
						button.arrow-btn(type="button", :aria-expanded="String(openFolds.dms)", @click.stop="toggleFold('dms')")
							i.fa(:class="openFolds.dms ? 'fa-angle-down' : 'fa-angle-left'", aria-hidden="true")
					transition(name="fold")
						.nav-sub-list(v-show="openFolds.dms")
							router-link.nav-sub-link(
								v-for="channel of directMessageChannels",
								:key="channel.id",
								:to="{name: 'channel', params: {channelId: channel.id}}",
								:class="{active: channel.id === $route.params.channelId, unread: hasUnreadMessages(channel.id)}",
								@click="onNavClick"
							)
								span.mdi(aria-hidden="true", :class="call && call.channel === channel.id ? 'mdi-phone' : 'mdi-account-outline'")
								span {{ getDMChannelName(channel) }}
							button.nav-sub-link.nav-sub-link--add(type="button", @click.prevent="showDMCreationPrompt = true; onNavClick()")
								span.mdi.mdi-plus(aria-hidden="true")
								span {{ $t('New Message') }}

			.buffer

			.sidebar-footer-action(v-if="hasOrganiserPermissions")
				a.btn-manage-video(:href="manageVideoUrl", @click="onNavClick")
					i.fa.fa-cog(aria-hidden="true")
					span {{ $t('Manage') }}

		teleport(to="body")
			transition(name="prompt")
				channel-browser(v-if="showChannelBrowser && liveFeatures.chat_rooms", @close="showChannelBrowser = false")
				create-dm-prompt(v-else-if="showDMCreationPrompt && hasPermission('world:chat.direct') && liveFeatures.direct_messaging", @close="showDMCreationPrompt = false")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'
import theme from 'theme'
import ROOM_TYPES, { NETWORKING_MODULE_TYPES, VIDEO_CHANNEL_MODULE_TYPES, inferRoomType, inferType } from 'lib/room-types'
import { getRoomOccupancyCount, usesParticipantOccupancy } from 'lib/room-occupancy'
import Avatar from 'components/Avatar'
import ChannelBrowser from 'components/ChannelBrowser'
import CreateDmPrompt from 'components/CreateDmPrompt'
import { hasOrganizerTraits } from 'lib/traitGrants'

export default {
	name: 'RoomsSidebar',
	components: { Avatar, ChannelBrowser, CreateDmPrompt },
	props: {
		collapsed: {
			type: Boolean,
			default: false
		},
		showMobile: {
			type: Boolean,
			default: false
		}
	},
	emits: ['close'],
	data() {
		return {
			theme,
			lastPointer: null,
			pointerMovementX: 0,
			snapBack: false,
			showChannelBrowser: false,
			showDMCreationPrompt: false,
			openFolds: {
				stages: true,
				channels: true,
				dms: true
			}
		}
	},
	computed: {
		...mapState(['world', 'rooms', 'activeRoom', 'call']),
		...mapGetters(['hasPermission', 'isAdminMode']),
		...mapGetters('chat', ['joinedChannels', 'directMessageChannels', 'notificationCount']),
		...mapGetters('schedule', ['currentSessionPerRoom']),
		eventDateSubtitle() {
			const dateFrom = this.world?.date_from || window.eventyay?.eventDates?.date_from
			const dateTo = this.world?.date_to || window.eventyay?.eventDates?.date_to
			if (!dateFrom) return ''
			const fromMoment = moment(dateFrom)
			if (!dateTo || fromMoment.isSame(moment(dateTo), 'day')) {
				return fromMoment.format('ll')
			}
			const toMoment = moment(dateTo)
			if (fromMoment.isSame(toMoment, 'month')) {
				return `${fromMoment.format('MMM D')} – ${toMoment.format('D, YYYY')}`
			}
			if (fromMoment.isSame(toMoment, 'year')) {
				return `${fromMoment.format('MMM D')} – ${toMoment.format('MMM D, YYYY')}`
			}
			return `${fromMoment.format('ll')} – ${toMoment.format('ll')}`
		},
		networkingTitle() {
			return this.networkingRoomType?.name || this.$t('Networking')
		},
		browseChannelsTooltip() {
			return this.$t('Browse all channels')
		},
		openDirectMessageTooltip() {
			return this.$t('open a direct message')
		},
		networkingRoomType() {
			return ROOM_TYPES.find(type => type.sidebarGroup === 'networking')
		},
		hasStagesOrRooms() {
			return (this.roomsByType.stage?.length > 0 || this.roomsByType.networking?.length > 0)
		},
		liveFeatures() {
			return Object.assign({
				chat_rooms: false,
				kiosks: false,
				direct_messaging: false,
				announcements: true
			}, this.world?.live_features || window.eventyay?.liveFeatures || {})
		},
		hasChatChannels() {
			if (!this.liveFeatures.chat_rooms) return false
			return (this.roomsByType.textChat?.length > 0 || this.roomsByType.videoChat?.length > 0 || this.worldHasTextChannels)
		},
		manageVideoUrl() {
			if (window.eventyay?.videoUrl) return window.eventyay.videoUrl
			return this.$router.resolve({ name: 'organizer' }).href
		},
		hasOrganiserPermissions() {
			if (window.eventyay?.isOrganizerArea) return true
			const hasToken = Boolean(this.$store.state.token)
			if (hasToken) {
				const tokenPayload = this.$store.getters.tokenPayload
				const traits = Array.isArray(tokenPayload?.traits) ? tokenPayload.traits : []
				return Boolean(
					hasOrganizerTraits(traits) ||
					this.hasPermission('world:update') ||
					this.hasPermission('world:users.list') ||
					this.hasPermission('world:announce') ||
					this.hasPermission('world:rooms.create.stage') ||
					this.hasPermission('world:rooms.create.bbb') ||
					this.hasPermission('world:kiosks.manage')
				)
			}
			return Boolean(
				window.eventyay?.hasOrganiserPermissions ||
				this.isAdminMode ||
				(Array.isArray(this.$store.state.user?.traits) && this.$store.state.user.traits.includes('admin')) ||
				this.hasPermission('world:update') ||
				this.hasPermission('world:users.list') ||
				this.hasPermission('world:announce') ||
				this.hasPermission('world:rooms.create.stage') ||
				this.hasPermission('world:rooms.create.bbb') ||
				this.hasPermission('world:kiosks.manage')
			)
		},
		style() {
			if (this.$mq?.above?.m) return null
			if (this.pointerMovementX === 0) return null
			return {
				transform: `translateX(${this.pointerMovementX}px)`
			}
		},
		roomsByType() {
			const rooms = {
				page: [],
				stage: [],
				networking: [],
				textChat: [],
				videoChat: []
			}
			if (!this.rooms) return rooms

			for (const room of this.rooms) {
				const inferred = Array.isArray(room.module_config)
					? inferType({ module_config: room.module_config })
					: inferRoomType(room)
				if (!inferred) continue

				if (room.modules.length === 1 && room.modules[0].type === 'chat.native') {
					if (!this.liveFeatures.chat_rooms) continue
					if (this.joinedChannels && !this.joinedChannels.some(channel => channel.id === room.modules[0].channel_id)) continue
					const notifications = this.notificationCount ? this.notificationCount(room.modules[0].channel_id) : 0
					rooms.textChat.push({
						room,
						notifications: notifications > 99 ? '99+' : notifications
					})
				} else if (room.modules.some(module => NETWORKING_MODULE_TYPES.has(module.type))) {
					rooms.networking.push(room)
				} else if (room.modules.some(module => VIDEO_CHANNEL_MODULE_TYPES.has(module.type))) {
					if (!this.liveFeatures.chat_rooms) continue
					rooms.videoChat.push(room)
				} else if (room.modules.some(module => ['livestream.native', 'livestream.youtube'].includes(module.type))) {
					let session
					if (this.$features?.enabled?.('schedule-control')) {
						session = this.currentSessionPerRoom?.[room.id]?.session
					}
					const notifications = this.notificationCount ? this.notificationCount(room.modules.find(m => m.type === 'chat.native')?.channel_id) : 0
					rooms.stage.push({
						room,
						session,
						notifications: notifications > 99 ? '99+' : notifications
					})
				} else {
					rooms.page.push(room)
				}
			}
			return rooms
		},
		directMessageChannels() {
			if (!this.hasPermission('world:chat.direct') || !this.liveFeatures.direct_messaging) {
				return []
			}
			return this.$store.getters['chat/directMessageChannels'] || []
		},
		worldHasTextChannels() {
			if (!this.liveFeatures.chat_rooms) return false
			return (this.rooms || []).some(room => room.modules?.length === 1 && room.modules[0].type === 'chat.native')
		}
	},
	methods: {
		getOccupancyCount(room) {
			return getRoomOccupancyCount(room, {
				rooms: this.rooms,
				activeRoomId: this.$store.state.activeRoom?.id,
				routeRoomId: this.$route.params.roomId,
				roomViewers: this.$store.state.roomViewers,
			})
		},
		getOccupancyTitle(room) {
			const count = this.getOccupancyCount(room)
			if (usesParticipantOccupancy(room)) {
				return `${count} ${count === 1 ? this.$t('participant') : this.$t('participants')}`
			}
			return `${count} ${count === 1 ? this.$t('active viewer') : this.$t('active viewers')}`
		},
		toggleFold(key) {
			this.openFolds[key] = !this.openFolds[key]
		},
		onNavClick() {
			if (this.$mq?.below?.m) {
				this.$emit('close')
			}
		},
		hasUnreadMessages(channelId) {
			return this.notificationCount ? this.notificationCount(channelId) > 0 : false
		},
		getDMChannelName(channel) {
			const otherUser = channel?.users?.find(u => u?.id !== this.$store?.state?.user?.id)
			return otherUser?.profile?.display_name || otherUser?.profile?.name || this.$t('Unknown User')
		},
		onPointerdown(event) {
			if (this.$mq?.above?.m) return
			this.lastPointer = event.clientX
		},
		onPointermove(event) {
			if (this.$mq?.above?.m || this.lastPointer === null) return
			const diff = event.clientX - this.lastPointer
			this.pointerMovementX = Math.min(0, this.pointerMovementX + diff)
			this.lastPointer = event.clientX
		},
		onPointerup() {
			if (this.$mq?.above?.m || this.lastPointer === null) return
			this.lastPointer = null
			if (this.pointerMovementX < -80) {
				this.$emit('close')
				this.pointerMovementX = 0
			} else {
				this.snapBack = true
				this.$nextTick(() => {
					this.pointerMovementX = 0
					this.snapBack = false
				})
			}
		},
		onPointercancel() {
			this.lastPointer = null
			this.pointerMovementX = 0
		}
	}
}
</script>
<style lang="stylus">
.c-rooms-sidebar
	background-color: #f8f8f8
	border-right: 1px solid #e7e7e7
	bottom: 0
	box-sizing: border-box
	display: flex
	flex-direction: column
	left: 0
	position: fixed
	top: 50px
	width: 250px
	z-index: 100
	user-select: none
	font-family: inherit
	font-size: 14px
	overflow-y: auto
	overflow-x: hidden
	transition: width 0.2s cubic-bezier(0.4, 0, 0.2, 1), transform 0.2s cubic-bezier(0.4, 0, 0.2, 1)

	+above('m')
		transform: translateX(0)
		box-shadow: none

		&.sidebar-collapsed:not(:hover)
			width: 45px !important

			.startpage-sidebar-context
				.context-indicator
					display: none !important
				.context-icon-badge
					margin-right: 0 !important

			.sidebar-text,
			.arrow-btn,
			.notifications,
			.nav-sub-list,
			.sidebar-footer-action
				display: none !important

		&.sidebar-collapsed:hover
			width: 250px
			box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15)
			z-index: 160

			.startpage-sidebar-context
				.context-indicator
					display: flex
				.context-icon-badge
					margin-right: 12px

			.sidebar-text
				display: inline-block

			.arrow-btn
				display: flex

			.nav-sub-list
				display: flex

			.sidebar-footer-action
				display: block

	+below('m')
		z-index: 150
		width: min(260px, 85vw)
		box-shadow: 2px 0 5px rgba(0, 0, 0, 0.2)
		transform: translateX(-100%)
		&.sidebar-mobile-open
			transform: translateX(0)

	.startpage-sidebar-inner
		display: flex
		flex-direction: column
		min-height: 100%
		padding: 0
		color: #334155

	.startpage-sidebar-context
		border-bottom: 1px solid #e7e7e7
		position: relative
		background: transparent

		.dropdown-toggle
			align-items: center
			background-color: transparent
			color: #428bca
			display: flex
			flex-direction: row
			min-height: 56px
			padding: 8px 6px
			text-decoration: none
			box-sizing: border-box
			white-space: nowrap
			overflow: hidden

			&:hover, &:focus
				background-color: #eeeeee
				color: #23527c
				text-decoration: none

		.context-icon-badge
			width: 32px
			height: 32px
			border-radius: 50%
			background-color: #2185d0
			color: #ffffff
			display: flex
			align-items: center
			justify-content: center
			flex-shrink: 0
			margin-right: 12px
			font-size: 18px

		.context-indicator
			display: flex
			flex-direction: column
			flex-grow: 1
			min-width: 0
			overflow: hidden
			white-space: nowrap

		.context-name
			color: #428bca
			display: block
			font-size: 15px
			font-weight: 600
			line-height: 17px
			margin-bottom: 2px
			overflow: hidden
			text-overflow: ellipsis
			white-space: nowrap

		.context-meta
			font-size: 11px
			color: #777777
			line-height: 14px

		.btn-close-mobile
			position: absolute
			top: 10px
			right: 8px
			icon-button-style(color: #777777, style: clear)

	.startpage-sidebar-nav
		list-style: none
		margin: 0
		padding: 0
		display: flex
		flex-direction: column

		li
			border-top: 1px solid #e7e7e7
			position: relative

			&:last-child
				border-bottom: 1px solid #e7e7e7

		.nav-link
			align-items: center
			box-sizing: border-box
			color: #337ab7
			display: flex
			font-size: 14px
			font-weight: normal
			min-height: 41px
			height: 41px
			line-height: 20px
			padding: 10px 15px
			text-decoration: none
			cursor: pointer
			white-space: nowrap
			overflow: hidden
			transition: background-color 0.15s ease, color 0.15s ease

			.fa, .mdi
				align-items: center
				box-sizing: content-box
				display: inline-flex
				flex-shrink: 0
				font-size: 14px
				height: 16px
				justify-content: center
				line-height: 1
				margin: 0 8px 0 0
				text-align: center
				width: 16px
				color: #337ab7

			.sidebar-text
				display: inline-block
				ellipsis()
				flex: auto

			.notifications
				margin-left: 6px
				background-color: #2185d0
				color: #ffffff
				border-radius: 9999px
				padding: 1px 7px
				font-size: 11px
				font-weight: 600

			&:hover, &:focus
				background-color: #eeeeee
				color: #23527c
				text-decoration: none

				.fa, .mdi
					color: #23527c

			&.active, &.router-link-exact-active
				background-color: #eeeeee
				color: #23527c
				font-weight: 600

				.fa, .mdi
					color: #23527c

		.nav-fold
			display: flex
			flex-direction: column

			.has-children
				display: flex
				flex-direction: row
				align-items: stretch
				width: 100%

				.nav-link-inner
					flex: 1 1 auto
					min-width: 0
					border: none

				.arrow-btn
					appearance: none
					background: transparent
					border: none
					color: #337ab7
					cursor: pointer
					display: flex
					align-items: center
					justify-content: center
					width: 36px
					min-height: 41px
					height: 41px
					padding: 0
					margin: 0
					outline: none
					flex-shrink: 0
					transition: background-color 0.15s ease, color 0.15s ease

					.fa
						font-size: 12px
						color: #337ab7
						transition: color 0.15s ease

					&:hover, &:focus
						color: #23527c
						background-color: #eeeeee
						.fa
							color: #23527c

			.nav-sub-list
				display: flex
				flex-direction: column
				background: transparent

				.nav-sub-link
					align-items: center
					box-sizing: border-box
					color: #337ab7
					display: flex
					font-size: 14px
					font-weight: normal
					min-height: 41px
					height: 41px
					line-height: 20px
					padding: 10px 15px
					text-decoration: none
					border: none
					background: none
					cursor: pointer
					font-family: inherit
					text-align: left
					width: 100%
					transition: background-color 0.15s ease, color 0.15s ease

					> .room-name, > span:first-child
						padding-left: 1.6em
						ellipsis()
						flex: auto
						min-width: 0

					.viewer-count-badge
						display: inline-flex
						align-items: center
						gap: 3px
						padding: 1px 6px
						background-color: rgba(0, 0, 0, 0.06)
						border-radius: 10px
						font-size: 11px
						font-weight: 600
						color: #555555
						margin-left: auto
						margin-right: 0
						flex-shrink: 0
						span
							padding: 0 !important
							flex: none !important
						i
							font-size: 12px
							color: $clr-primary

					.notifications
						margin-left: 6px
						background-color: #2185d0
						color: #ffffff
						border-radius: 9999px
						padding: 1px 7px
						font-size: 11px
						font-weight: 600
						flex-shrink: 0

					&.nav-sub-link--action, &.nav-sub-link--add
						font-style: italic
						color: #337ab7
						gap: 6px

						> span:first-child
							padding-left: 0 !important
							flex: none !important

						.mdi
							font-size: 14px
							margin-left: 1.6em
							flex: none !important

						&.nav-sub-link--nested
							> span:first-child
								padding-left: 0 !important
							.mdi
								margin-left: 2.6em

						> span:last-child
							flex: auto
							min-width: 0
							ellipsis()

					&:hover, &:focus
						background-color: #eeeeee
						color: #23527c
						text-decoration: none

					&.router-link-exact-active, &.active
						background-color: #eeeeee
						color: #23527c
						font-weight: 600

	.buffer
		flex: auto
		min-height: 20px

	.sidebar-footer-action
		border-top: 1px solid #e7e7e7
		padding: 12px 15px
		background: #f8f8f8

		.btn-manage-video
			align-items: center
			background-color: #ffffff
			border: 1px solid #337ab7
			border-radius: 4px
			box-sizing: border-box
			color: #337ab7
			display: flex
			font-size: 13.5px
			font-weight: 600
			justify-content: center
			padding: 8px 12px
			text-decoration: none
			gap: 6px
			transition: background-color 0.15s ease, color 0.15s ease

			.fa, .mdi
				font-size: 15px

			&:hover, &:focus
				background-color: #337ab7
				color: #ffffff
				text-decoration: none
</style>
