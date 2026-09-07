<template lang="pug">
.c-room-header
	.ui-page-header(v-if="!modules['page.markdown'] && !modules['page.landing'] && $route.name !== 'room:manage'")
		bunt-icon-button.btn-back(@click="onBack", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		.room-info
			.room-name(v-html="$emojify(room.name)")
			.room-session(v-if="currentSession") {{ $localize(currentSession.title) }}
		//- bunt-icon-button(v-if="$features.enabled('schedule-control')", @click="showEditSchedule = true") calendar_edit
		.actions
			bunt-icon-button(v-if="modules['call.bigbluebutton'] && hasPermission('room:bbb.recordings')", :tooltip="$t('Recordings')", tooltipPlacement="bottom-end", @click="showRecordingsPrompt = true") file-video-outline
	router-view(:room="room", :modules="modules")
	transition(name="prompt")
		recordings-prompt(v-if="showRecordingsPrompt && room", :room="room", @close="showRecordingsPrompt = false")
</template>
<script>
// TODO
// better ellipsing for room name + session title on small screens
import {mapGetters, mapState} from 'vuex'
import { inferRoomType, inferType } from 'lib/room-types'
import RecordingsPrompt from 'components/RecordingsPrompt'

const PERMISSIONS_TO_MANAGE = [
	'room:chat.moderate',
	'room:question.moderate',
	'room:poll.manage'
]

export default {
	components: { RecordingsPrompt },
	props: {
		roomId: String
	},
	data() {
		return {
			showRecordingsPrompt: false,
			_redirectCheckTimer: null
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		...mapState(['rooms']),
		...mapGetters('schedule', ['sessions', 'currentSessionPerRoom']),
		room() {
			if (this.roomId === undefined) {
				const rooms = this.rooms || []
				const infoRoom = rooms.find(room => room && room.modules && room.modules.some(m => m.type === 'page.landing'))
				if (infoRoom) return infoRoom

				return {
					name: 'About',
					modules: [{
						type: 'page.landing'
					}]
				}
			}
			const wantedId = String(this.roomId)
			return this.rooms?.find(room => String(room.id) === wantedId || (room.pretalx_id != null && String(room.pretalx_id) === wantedId))
		},
		roomType() {
			if (!this.room) return null
			const type = Array.isArray(this.room.module_config)
				? inferType({ module_config: this.room.module_config })
				: inferRoomType(this.room)
			return type ? type.id : null
		},
		modules() {
			if (!this.room || !this.room.modules) return {}
			return this.room.modules.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		currentSession() {
			if (!this.$features.enabled('schedule-control') || !this.room) return
			return this.currentSessionPerRoom?.[this.room.id]?.session
		},
		canManage() {
			for (const permission of PERMISSIONS_TO_MANAGE) {
				if (this.hasPermission(permission)) return true
			}
			return false
		}
	},
	watch: {
		room: {
			handler: 'scheduleRedirectIfUninitiated',
			immediate: true
		},
		rooms: {
			handler: 'scheduleRedirectIfUninitiated',
			deep: true
		},
		roomId: 'scheduleRedirectIfUninitiated'
	},
	methods: {
		scheduleRedirectIfUninitiated() {
			if (this._redirectCheckTimer) {
				clearTimeout(this._redirectCheckTimer)
			}
			this._redirectCheckTimer = setTimeout(() => {
				this._redirectCheckTimer = null
				this.redirectIfUninitiated()
			}, 50)
		},
		redirectIfUninitiated() {
			// Only enforce this for direct room navigation (/rooms/:roomId).
			// Home ('/') will always show the first available room.
			if (this.roomId === undefined) return
			// Wait until rooms have loaded.
			if (!this.rooms || this.rooms.length === 0) return
			// If the room does not exist or is unconfigured, redirect to home.
			const inferred = this.room
				? (Array.isArray(this.room.module_config)
					? inferType({ module_config: this.room.module_config })
					: inferRoomType(this.room))
				: null
			if (!inferred) {
				if (this.$route.name === 'about') return
				this.$router.replace({name: 'about'})
			}
		},
		onBack() {
			if (window.history.state && window.history.state.back) {
				this.$router.back()
			} else if (window.eventyay?.isOrganizerArea) {
				this.$router.replace({ name: 'organizer' })
			} else {
				this.$router.replace({ name: 'about' })
			}
		}
	},
	beforeUnmount() {
		if (this._redirectCheckTimer) {
			clearTimeout(this._redirectCheckTimer)
			this._redirectCheckTimer = null
		}
	}
}
</script>
<style lang="stylus">
.c-room-header
	flex: auto
	display: flex
	flex-direction: column
	background-color: $clr-white
	min-height: 0
	min-width: 0
	> .ui-page-header
		justify-content: space-between
		.btn-back
			icon-button-style(style: clear)
			flex: none
		.room-info
			padding: 0 12px
			flex: 1
			display: flex
			align-items: baseline
			min-width: 0
			.room-name
				ellipsis()
				font-size: 24px
				line-height: 56px
				font-weight: 600
				// TODO decopypaste
				.emoji
					display: inline-block
					vertical-align: middle
					width: 36px
					height: @width
					&.needs-space
						margin-right: 8px
			.room-session
				margin-left: 8px
				font-size: 18px
				ellipsis()
			+below('m')
				padding: 0 4px 0 0
		.actions
			flex: none
			display: flex
			align-items: center
			gap: 8px
			.bunt-icon-button
				icon-button-style(style: clear)
</style>
