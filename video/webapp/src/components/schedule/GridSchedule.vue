<template lang="pug">
.c-grid-schedule(v-scrollbar.y="")
	.grid(:style="gridStyle")
		.room(v-for="(room, index) of rooms", :style="{'grid-area': `1 / ${index + 1 } / auto / auto`}") {{ room.name }}
		session(v-for="session of sessions", :session="session", :style="getSessionStyle(session)")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'
import Session from './Session'

export default {
	components: { Session },
	data () {
		return {
			moment
		}
	},
	computed: {
		...mapState(['schedule', 'pretalxEvent', 'pretalxRooms']),
		...mapGetters(['flatSchedule']),
		sessions () {
			return this.flatSchedule?.sessions
		},
		rooms () {
			return this.pretalxRooms.map(room => this.$store.state.rooms.find(r => r.pretalx_id === room.id))
		},
		// find this to not tax the grid with 1min rows
		greatestCommonDurationDivisor () {
			const gcd = (a, b) => a ? gcd(b % a, a) : b
			return this.sessions
				.map(s => moment(s.end).diff(s.start, 'minutes'))
				.reduce(gcd)
		},
		totalRows () {
			const days = this.pretalxEvent.schedule
			const totalMinutes = moment(days[days.length - 1].end).diff(days[0].start, 'minutes')
			return Math.ceil(totalMinutes / this.greatestCommonDurationDivisor)
		},
		gridStyle () {
			return {
				'--row-height': this.greatestCommonDurationDivisor,
				'--total-rows': this.totalRows,
				'--total-rooms': this.pretalxRooms.length
			}
		}
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		getSessionStyle (session) {
			const days = this.pretalxEvent.schedule
			const minutesFromStart = session.start.diff(days[0].start, 'minutes')
			const startingRow = Math.ceil(minutesFromStart / this.greatestCommonDurationDivisor)
			const durationMinutes = session.end.diff(session.start, 'minutes')
			const height = Math.ceil(durationMinutes / this.greatestCommonDurationDivisor)
			const roomIndex = this.pretalxRooms.findIndex(r => r.id === session.room.pretalx_id)
			return {
				'grid-row': `${startingRow} / span ${height}`,
				'grid-column': `${roomIndex + 1}`
			}
		}
	}
}
</script>
<style lang="stylus">
.c-grid-schedule
	display: flex
	flex-direction: column
	margin: 8px
	.grid
		display: grid
		grid-template-rows: unquote("[header] 52px repeat(var(--total-rows), minmax(calc(var(--row-height) * 2px), auto))")
		grid-template-columns: repeat(var(--total-rooms), 1fr)
		grid-gap: 8px
		> .room
			position: sticky
			top: 0
			display: flex
			justify-content: center
			align-items: center
			font-size: 18px
			background-color: $clr-white
			border-bottom: border-separator()
</style>
