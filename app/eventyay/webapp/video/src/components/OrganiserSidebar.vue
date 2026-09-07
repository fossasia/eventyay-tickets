<template lang="pug">
aside.c-organiser-sidebar(
	:class="{'sidebar-collapsed': collapsed, 'sidebar-mobile-open': showMobile && !snapBack}",
	:style="sidebarStyle",
	role="navigation",
	:aria-label="$t('Video Organiser Navigation')",
	@pointerdown="onPointerdown",
	@pointermove="onPointermove",
	@pointerup="onPointerup",
	@pointercancel="onPointercancel"
)
		.startpage-sidebar-inner
			.startpage-sidebar-context
				a.dropdown-toggle(:href="commonAccountUrl", @click="onNavClick")
					span.fa-stack.context-icon-badge
						i.mdi.mdi-video-vintage
					.context-indicator
						span.context-name(v-if="world && world.title", v-html="$emojify(world.title)")
						span.context-name(v-else) {{ $t('Video Management') }}
						span.context-meta {{ eventDateSubtitle }}
				bunt-icon-button.btn-close-mobile(
					v-if="$mq.below.m",
					icon="close",
					:aria-label="$t('Close sidebar')",
					@click="$emit('close')"
				)

			ul.startpage-sidebar-nav(role="group", :aria-label="$t('Organiser Navigation')")
				//- 1. Overview
				li
					router-link.nav-link(:to="{name: 'organizer'}", exact, @click="onNavClick")
						span.fa.mdi.mdi-view-dashboard-outline(aria-hidden="true")
						span.sidebar-text {{ $t('Overview') }}

				//- 2. Rooms & Stages (collapsible)
				li.nav-fold(v-if="hasPermission('room:update') || hasPermission('world:rooms.create.stage') || isAdminMode")
					.has-children
						router-link.nav-link.nav-link-inner(:to="{name: 'admin:rooms:index'}", :class="{active: isRoomsActive}", @click="onNavClick")
							span.fa.mdi.mdi-door-open(aria-hidden="true")
							span.sidebar-text {{ $t('Rooms & Stages') }}
						button.arrow-btn(type="button", :aria-expanded="String(openFolds.rooms)", @click.stop="toggleFold('rooms')")
							i.fa(:class="openFolds.rooms ? 'fa-angle-down' : 'fa-angle-left'", aria-hidden="true")
					transition(name="fold")
						.nav-sub-list(v-show="openFolds.rooms")
							router-link.nav-sub-link(
								:to="{name: 'admin:rooms:index'}",
								:class="{active: $route.name === 'admin:rooms:index'}",
								@click="onNavClick"
							)
								span {{ $t('All Rooms') }}
							router-link.nav-sub-link.nav-sub-link--nested(
								v-for="room of individualRooms",
								:key="room.id",
								:to="getRoomTargetRoute(room)",
								:class="{active: ($route.name === 'room:manage' || $route.name === 'admin:rooms:item') && String($route.params.roomId) === String(room.id)}",
								@click="onNavClick"
							)
								span.room-name(v-html="$emojify(room.name)")
								span.viewer-count-badge(:title="getOccupancyTitle(room)", :aria-label="getOccupancyTitle(room)")
									i.mdi.mdi-account-outline(aria-hidden="true")
									span {{ getOccupancyCount(room) }}
							router-link.nav-sub-link.nav-sub-link--add.nav-sub-link--nested(:to="{name: 'admin:rooms:new'}", @click="onNavClick")
								span.mdi.mdi-plus(aria-hidden="true")
								span {{ $t('New Room') }}

				//- 3. Chat rooms (collapsible, hidden if chat_rooms is disabled)
				li.nav-fold(v-if="(hasPermission('room:update') || hasPermission('world:rooms.create.chat') || isAdminMode) && liveFeatures.chat_rooms")
					.has-children
						router-link.nav-link.nav-link-inner(:to="{name: 'admin:chat:index'}", :class="{active: isChatActive}", @click="onNavClick")
							span.fa.mdi.mdi-chat-processing-outline(aria-hidden="true")
							span.sidebar-text {{ $t('Chat rooms') }}
						button.arrow-btn(type="button", :aria-expanded="String(openFolds.chat)", @click.stop="toggleFold('chat')")
							i.fa(:class="openFolds.chat ? 'fa-angle-down' : 'fa-angle-left'", aria-hidden="true")
					transition(name="fold")
						.nav-sub-list(v-show="openFolds.chat")
							router-link.nav-sub-link(
								:to="{name: 'admin:chat:index'}",
								:class="{active: $route.name === 'admin:chat:index'}",
								@click="onNavClick"
							)
								span {{ $t('All Channels') }}
							router-link.nav-sub-link.nav-sub-link--nested(
								v-for="channel of individualChannels",
								:key="channel.id",
								:to="{name: 'admin:chat:item', params: {roomId: channel.id}}",
								:class="{active: $route.name === 'admin:chat:item' && $route.params.roomId === channel.id}",
								@click="onNavClick"
							)
								span.room-name(v-html="$emojify(channel.name)")
								span.viewer-count-badge(:title="getOccupancyTitle(channel)", :aria-label="getOccupancyTitle(channel)")
									i.mdi.mdi-account-outline(aria-hidden="true")
									span {{ getOccupancyCount(channel) }}
							router-link.nav-sub-link.nav-sub-link--add.nav-sub-link--nested(:to="{name: 'admin:chat:new'}", @click="onNavClick")
								span.mdi.mdi-plus(aria-hidden="true")
								span {{ $t('New Channel') }}

				//- 4. Kiosks (collapsible, hidden if kiosks is disabled)
				li.nav-fold(v-if="(hasPermission('world:kiosks.manage') || isAdminMode) && liveFeatures.kiosks")
					.has-children
						router-link.nav-link.nav-link-inner(:to="{name: 'admin:kiosks:index'}", :class="{active: isKiosksActive}", @click="onNavClick")
							span.fa.mdi.mdi-monitor-dashboard(aria-hidden="true")
							span.sidebar-text {{ $t('Kiosks') }}
						button.arrow-btn(type="button", :aria-expanded="String(openFolds.kiosks)", @click.stop="toggleFold('kiosks')")
							i.fa(:class="openFolds.kiosks ? 'fa-angle-down' : 'fa-angle-left'", aria-hidden="true")
					transition(name="fold")
						.nav-sub-list(v-show="openFolds.kiosks")
							router-link.nav-sub-link(
								:to="{name: 'admin:kiosks:index'}",
								:class="{active: $route.name === 'admin:kiosks:index'}",
								@click="onNavClick"
							)
								span {{ $t('All Kiosks') }}
							router-link.nav-sub-link.nav-sub-link--nested(
								v-for="kiosk of individualKiosks",
								:key="kiosk.id",
								:to="{name: 'admin:kiosks:item', params: {kioskId: kiosk.id}}",
								:class="{active: $route.name === 'admin:kiosks:item' && $route.params.kioskId === kiosk.id}",
								@click="onNavClick"
							)
								span(v-html="$emojify(kiosk.profile?.display_name || kiosk.profile?.name || kiosk.id)")
							router-link.nav-sub-link.nav-sub-link--add.nav-sub-link--nested(:to="{name: 'admin:kiosks:new'}", @click="onNavClick")
								span.mdi.mdi-plus(aria-hidden="true")
								span {{ $t('New Kiosk') }}

				//- 5. Direct Messages (collapsible, hidden if direct_messaging is disabled)
				li.nav-fold(v-if="(hasPermission('world:chat.direct') || isAdminMode) && liveFeatures.direct_messaging")
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

				//- 6. Users
				li(v-if="hasPermission('world:users.list') || isAdminMode")
					router-link.nav-link(:to="{name: 'admin:users'}", @click="onNavClick")
						span.fa.mdi.mdi-account-multiple-outline(aria-hidden="true")
						span.sidebar-text {{ $t('Users') }}

				//- 7. Announcements
				li(v-if="(hasPermission('world:announce') || isAdminMode) && liveFeatures.announcements !== false")
					router-link.nav-link(:to="{name: 'admin:announcements'}", @click="onNavClick")
						span.fa.mdi.mdi-bullhorn-outline(aria-hidden="true")
						span.sidebar-text {{ $t('Announcements') }}

				//- 8. Reports
				li(v-if="hasPermission('world:graphs') || isAdminMode")
					router-link.nav-link(:to="{name: 'admin:reports'}", :class="{active: isReportsActive}", @click="onNavClick")
						span.fa.mdi.mdi-file-chart-outline(aria-hidden="true")
						span.sidebar-text {{ $t('Reports') }}

				//- 9. Logs
				li(v-if="hasPermission('world:update') || isAdminMode")
					router-link.nav-link(:to="{name: 'admin:logs'}", :class="{active: isLogsActive}", @click="onNavClick")
						span.fa.mdi.mdi-history(aria-hidden="true")
						span.sidebar-text {{ $t('Logs') }}

				//- 10. Settings (formerly Video settings, now below Logs)
				li(v-if="hasPermission('world:update') || hasPermission('world:rooms.create.stage') || hasPermission('world:rooms.create.bbb') || isAdminMode")
					router-link.nav-link(:to="{name: 'admin:config'}", :class="{active: isConfigActive}", @click="onNavClick")
						span.fa.mdi.mdi-cog-outline(aria-hidden="true")
						span.sidebar-text {{ $t('Settings') }}

			.buffer

			.sidebar-footer-action
				a.btn-public-view(:href="publicVideoUrl", @click="onViewPublicVideo")
					i.fa.fa-eye(aria-hidden="true")
					span {{ $t('View Public Video') }}

		teleport(to="body")
			transition(name="prompt")
				create-dm-prompt(v-if="showDMCreationPrompt && (hasPermission('world:chat.direct') || isAdminMode) && liveFeatures.direct_messaging", @close="showDMCreationPrompt = false")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'
import theme from 'theme'
import api from 'lib/api'
import { inferRoomType, isChatManagedRoom } from 'lib/room-types'
import { getRoomOccupancyCount, usesParticipantOccupancy } from 'lib/room-occupancy'
import CreateDmPrompt from 'components/CreateDmPrompt'

export default {
	name: 'OrganiserSidebar',
	components: { CreateDmPrompt },
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
			kiosks: [],
			showDMCreationPrompt: false,
			openFolds: {
				rooms: false,
				chat: false,
				kiosks: false,
				dms: false,
				config: false
			}
		}
	},
	computed: {
		...mapState(['world', 'rooms']),
		...mapGetters(['hasPermission', 'isAdminMode']),
		commonAccountUrl() {
			return window.eventyay?.commonAccountUrl || window.eventyay?.homeUrl || '/'
		},
		publicVideoUrl() {
			return window.eventyay?.publicVideoUrl || '/'
		},
		liveFeatures() {
			return Object.assign({
				chat_rooms: false,
				kiosks: false,
				direct_messaging: false,
				announcements: true
			}, this.world?.live_features || window.eventyay?.liveFeatures || {})
		},
		eventDateSubtitle() {
			const dateFrom = this.world?.date_from || window.eventyay?.eventDates?.date_from
			const dateTo = this.world?.date_to || window.eventyay?.eventDates?.date_to
			if (!dateFrom) return this.$t('Organizer account')
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
		individualRooms() {
			if (!Array.isArray(this.rooms)) return []
			return this.rooms.filter(room => !isChatManagedRoom(room))
		},
		individualChannels() {
			if (!Array.isArray(this.rooms)) return []
			return this.rooms.filter(room => isChatManagedRoom(room))
		},
		individualKiosks() {
			return this.kiosks || []
		},
		isRoomsActive() {
			return this.$route.name?.startsWith('admin:rooms') || this.$route.name === 'room:manage'
		},
		isChatActive() {
			return this.$route.name?.startsWith('admin:chat')
		},
		isKiosksActive() {
			return this.$route.name?.startsWith('admin:kiosks')
		},
		isConfigActive() {
			return this.$route.name === 'admin:config'
		},
		isReportsActive() {
			return this.$route.name === 'admin:reports' || this.$route.name === 'admin:config:reports'
		},
		isLogsActive() {
			return this.$route.name === 'admin:logs' || this.$route.name === 'admin:config:audit-log'
		},
		call() {
			return this.$store.state.chat?.call
		},
		directMessageChannels() {
			if (!this.hasPermission('world:chat.direct') && !this.isAdminMode) {
				return []
			}
			return this.$store.getters['chat/directMessageChannels'] || []
		},
		notificationCount() {
			return this.$store.getters['chat/notificationCount']
		},
		sidebarStyle() {
			if (this.$mq?.above?.m) return null
			if (this.pointerMovementX === 0) return null
			return {
				transform: `translateX(${this.pointerMovementX}px)`
			}
		}
	},
	watch: {
		'$store.state.connected': {
			immediate: true,
			handler(connected) {
				if (connected) this.fetchKiosks()
			}
		},
		'$route.name': {
			immediate: true,
			handler(name) {
				if (!name) return
				if (name.startsWith('admin:rooms') || name === 'room:manage') this.openFolds.rooms = true
				if (name.startsWith('admin:chat')) this.openFolds.chat = true
				if (name.startsWith('admin:kiosks')) {
					this.openFolds.kiosks = true
					this.fetchKiosks()
				}
				if (name.startsWith('admin:config')) this.openFolds.config = true
			}
		}
	},
	created() {
		this.fetchKiosks()
	},
	methods: {
		getRoomTargetRoute(room) {
			if (!room) return { name: 'admin:rooms:index' }
			// inferRoomType reads room.modules (the store shape)
			const isConfigured = !!inferRoomType(room)
			if (isConfigured) {
				return { name: 'room:manage', params: { roomId: room.id } }
			}
			return { name: 'admin:rooms:item', params: { roomId: room.id } }
		},
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
		async fetchKiosks() {
			if (!this.hasPermission('world:kiosks.manage') && !this.isAdminMode) return
			try {
				const res = await api.call('user.list', {type: 'kiosk'})
				this.kiosks = res?.results || []
			} catch (e) {
				console.error('Failed to fetch kiosks for sidebar', e)
			}
		},
		toggleFold(key) {
			this.openFolds[key] = !this.openFolds[key]
			if (key === 'kiosks' && this.openFolds.kiosks) {
				this.fetchKiosks()
			}
		},
		onNavClick() {
			if (this.$mq?.below?.m) {
				this.$emit('close')
			}
		},
		onViewPublicVideo() {
			try {
				sessionStorage.setItem('video_auth_mode', 'organizer')
				localStorage.removeItem('token')
			} catch (e) {}
			this.onNavClick()
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
.c-organiser-sidebar
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

					&.nav-sub-link--nested
						> .room-name, > span:first-child
							padding-left: 2.6em

					&.nav-sub-link--add, &.nav-sub-link--action
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

		.btn-public-view
			align-items: center
			background-color: #ffffff
			border: 1px solid #2185d0
			border-radius: 4px
			box-sizing: border-box
			color: #2185d0
			display: flex
			font-size: 13px
			font-weight: 600
			justify-content: center
			padding: 8px 12px
			text-decoration: none
			gap: 6px
			transition: background-color 0.15s ease, color 0.15s ease

			.fa, .mdi
				font-size: 16px

			&:hover, &:focus
				background-color: #2185d0
				color: #ffffff
				text-decoration: none
</style>
