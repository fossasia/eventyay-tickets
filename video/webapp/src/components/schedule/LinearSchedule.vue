<template lang="pug">
.c-linear-schedule
	.sessions-list(v-scrollbar.y="")
		.bucket(v-for="({date, sessions}, index) of sessionBuckets")
			.bucket-label
				span.day(v-if="index > 0 && date.clone().startOf('day').diff(sessionBuckets[index - 1].date.clone().startOf('day'), 'day') > 0")  {{ date.format('DD. MMMM LT') }}
				span(v-else) {{ date.format('LT') }}
			session(v-for="session of sessions", :session="session")
</template>
<script>
import { mapGetters } from 'vuex'
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
		...mapGetters(['flatSchedule']),
		sessions () {
			return this.flatSchedule?.sessions.filter(session => !session.end.isBefore(this.now))
		},
		sessionBuckets () {
			const buckets = {}
			for (const session of this.sessions) {
				const key = session.start.toISOString()
				if (!buckets[key]) {
					buckets[key] = []
				}
				buckets[key].push(session)
			}
			return Object.entries(buckets).map(([date, sessions]) => ({date: moment(date), sessions}))
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
.c-linear-schedule
	display: flex
	flex-direction: column
	min-height: 0
	padding: 8px
	.bucket
		padding-top: 8px
		.bucket-label
			font-size: 14px
			font-weight: 500
			color: $clr-secondary-text-light
			padding-left: 16px
</style>
