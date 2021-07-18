<template lang="pug">
.c-room-header
	.ui-page-header(v-if="!modules['page.markdown'] && !modules['page.landing']")
		.room-info
			.room-name {{ room.name }}
			.room-session(v-if="currentSession") {{ currentSession.title }}
		//- bunt-icon-button(v-if="$features.enabled('schedule-control')", @click="showEditSchedule = true") calendar_edit
		.actions
			bunt-icon-button(v-if="modules['call.bigbluebutton'] && hasPermission('room:bbb.recordings')", :tooltip="$t('Room:recordings:tooltip')", tooltipPlacement="bottom-end", @click="showRecordingsPrompt = true") file-video-outline
			.button-group(v-if="['stage', 'channel-bbb', 'channel-janus', 'channel-zoom'].includes(roomType) && canManage")
				// TODO buntpapier does not support replace
				// hardlink params so home page alias works
				bunt-link-button(:to="{name: 'room:manage', params: {roomId: room.id}}", replace) manage
				bunt-link-button(:to="{name: 'room'}", replace) view
	router-view(:room="room", :modules="modules")
</template>
<script>
import {mapGetters, mapState} from 'vuex'
import { inferRoomType } from 'lib/room-types'

const PERMISSIONS_TO_MANAGE = [
	'room:chat.moderate',
	'room:question.moderate',
	'room:poll.manage'
]

export default {
	props: {
		roomId: String
	},
	computed: {
		...mapGetters(['hasPermission']),
		...mapState(['rooms']),
		...mapGetters('schedule', ['sessions', 'sessionsScheduledNow']),
		room () {
			if (this.roomId === undefined) return this.rooms[0] // '/' is the first room
			return this.rooms.find(room => room.id === this.roomId)
		},
		roomType () {
			return inferRoomType(this.room).id
		},
		modules () {
			return this.room?.modules.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		currentSession () {
			if (!this.$features.enabled('schedule-control')) return
			let session
			if (this.room.schedule_data) {
				session = this.sessions?.find(session => session.id === this.room.schedule_data.session)
			}
			if (!session) {
				session = this.sessionsScheduledNow?.find(session => session.room === this.room)
			}
			return session
		},
		canManage () {
			for (const permission of PERMISSIONS_TO_MANAGE) {
				if (this.hasPermission(permission)) return true
			}
			return false
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
		.room-info
			padding: 0 24px
			display: flex
			align-items: baseline
			min-width: 0
			.room-name
				font-size: 24px
				line-height: 56px
				font-weight: 600
				display: flex
				flex-direction: column
			.room-session
				margin-left: 8px
				font-size: 18px
				ellipsis()
			+below('m')
				padding: 0 4px 0 0
		.actions
			flex: none
			display: flex
			.button-group
				> .bunt-link-button
					box-sizing: border-box
					&.router-link-exact-active
						themed-button-primary()
					&:not(.router-link-exact-active)
						themed-button-secondary()
						border: 2px solid var(--clr-primary)
					&:first-child
						border-radius: 4px 0 0 4px
					&:last-child
						border-radius: 0 4px 4px 0
</style>
