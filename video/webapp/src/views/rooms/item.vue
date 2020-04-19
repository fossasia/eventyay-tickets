<template lang="pug">
.c-room
	.main
		.room-info
			img(:src="room.picture")
			.room-info-text
				h2 {{ room.name }}
				.description {{ room.description }}
			.talk-info(v-if="currentTalk")
				h3 {{ currentTalk.title }}
		livestream(v-if="modules['livestream.native']", :room="room", :module="modules['livestream.native']")
	chat(v-if="modules['chat.native']", :room="room", :module="modules['chat.native']")
</template>
<script>
import { mapState } from 'vuex'
import moment from 'moment'
import Chat from 'components/Chat'
import Livestream from 'components/Livestream'

export default {
	name: 'room',
	props: {
		roomId: String
	},
	components: { Chat, Livestream },
	data () {
		return {
		}
	},
	computed: {
		...mapState(['world', 'schedule']),
		room () {
			return this.$store.state.rooms.find(room => room.id === this.roomId)
		},
		modules () {
			return this.room.modules.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		scheduleRoom () {
			if (!this.schedule || !this.world.pretalx?.room_mapping) return
			const scheduleDay = this.schedule.schedule.find(day => moment().isSame(day.start, 'day'))
			if (!scheduleDay) return
			const roomId = Number(Object.entries(this.world.pretalx.room_mapping).find(mapping => mapping[1] === this.room.id)?.[0])
			return scheduleDay.rooms.find(room => room.id === roomId)
		},
		currentTalk () {
			if (!this.scheduleRoom) return
			return this.scheduleRoom.talks.find(talk => moment().isBetween(talk.start, talk.end))
		}
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-room
	flex: auto
	display: flex
	background-color: $clr-white
	min-height: 0
	.main
		flex: auto
		display: flex
		flex-direction: column
		min-height: 0
	.room-info
		flex: none
		display: flex
		padding: 16px 16px
		.room-info-text
			margin-left: 16px
	.c-chat
		border-left: border-separator()
		flex: none
		width: 380px
</style>
