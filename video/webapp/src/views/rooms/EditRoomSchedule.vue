<template lang="pug">
.c-edit-room-schedule
	.edit-wrapper
		bunt-icon-button#btn-close(@click="$emit('close')") close
		h2 Change session for room {{ room.name }}
		.content
			.sessions(v-scrollbar.y="")
				.session(v-for="session, index of sessions", :ref="session === currentSession ? 'currentSession': null", :class="{current: session === currentSession, selected: session === selectedSession}", @click="selectedSession = session")
					img.preview(:src="`https://picsum.photos/64?v=${index}`")
					.info
						.title {{ session.title }}
						.speakers(v-if="session.speakers") {{ session.speakers.map(s => s.name).join(', ')}}
					.time {{ formatTime(session.start) }}-{{ formatTime(session.end) }}
			.selected-session(v-if="selectedSession")
				img.preview(:src="`https://picsum.photos/64`")
				h3 DETAIL VIEW HERE
				.info
					.title {{ selectedSession.title }}
					.speakers(v-if="selectedSession.speakers") {{ selectedSession.speakers.map(s => s.name).join(', ')}}
				.time {{ formatTime(selectedSession.start) }}-{{ formatTime(selectedSession.end) }}
				bunt-button#btn-change(@click="change") change to
</template>
<script>
import { mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'

export default {
	props: {
		room: Object,
		currentSession: Object
	},
	data () {
		return {
			selectedSession: null
		}
	},
	computed: {
		...mapGetters(['flatSchedule']),
		sessions () {
			console.log(this.flatSchedule?.sessions.filter(session => session.room === this.room))
			return this.flatSchedule?.sessions.filter(session => session.room === this.room)
		}
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
			console.log(this.$refs)
			this.$refs.currentSession[0].scrollIntoView()
		})
	},
	methods: {
		formatTime (value) {
			return moment(value).format('HH:mm')
		},
		change () {
			this.$store.dispatch('updateRoomSchedule', {room: this.room, schedule_data: {session: this.selectedSession.id}})
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-edit-room-schedule
	position: fixed
	top: 0
	left: 0
	width: 100vw
	height: var(--vh100)
	z-index: 1000
	background-color: $clr-secondary-text-light
	display: flex
	justify-content: center
	align-items: center
	.edit-wrapper
		position: relative
		card()
		display: flex
		flex-direction: column
		width: 920px
		min-height: 40vh
		max-height: 80vh
		h2
			border-bottom: border-separator()
			margin: 0
			padding: 0 16px
			line-height: 52px
	.content
		flex: auto
		display: flex
		min-height: 0
	#btn-close
		icon-button-style(style: clear)
		position: absolute
		top: 8px
		right: 8px
	.sessions
		display: flex
		flex-direction: column
		border: border-separator()
		width: 420px
		.session
			height: 56px
			position: relative
			padding: 4px 0
			box-sizing: border-box
			display: flex
			cursor: pointer
			&:not(:last-child)
				border-bottom: border-separator()
			&:hover
				background-color: $clr-grey-100
			&.current
				background-color: var(--clr-primary-alpha-60)
				opacity: .6
				pointer-events: none
			&.selected
				background-color: $clr-grey-200
			.preview
				border-radius: 50%
				height: 48px
				width: 48px
				margin: 0 8px 0 4px
			.info
				flex: auto
				display: flex
				flex-direction: column
				width: calc(100% - 64px)
				justify-content: center
			.title
				ellipsis()
				display: block
				line-height: 28px
			.speakers
				ellipsis()
				width: calc(100% - 80px)
				color: $clr-secondary-text-light
			.time
				position: absolute
				bottom: 4px
				right: 4px
				color: $clr-secondary-text-light
				padding: 2px 4px
				border-radius: 4px
	.selected-session
		padding: 16px
		.preview
			border-radius: 50%
			height: 64px
			width: 64px
			margin: 0 8px 0 4px
		#btn-change
			position: absolute
			bottom: 16px
			right: 16px
			themed-button-primary()
</style>
