<template lang="pug">
.c-timezone-changer
	bunt-button(:class="{active: localTimezone === userTimezone}", @click="$store.dispatch('updateUserTimezone', localTimezone)")
		.zone-type local
		.timezone-label {{ localTimezoneLabel }}
	bunt-button(:class="{active: eventTimezone === userTimezone}", @click="$store.dispatch('updateUserTimezone', eventTimezone)")
		.zone-type event
		.timezone-label {{ eventTimezoneLabel }}
</template>
<script>
import moment from 'lib/timetravelMoment'
import { mapState } from 'vuex'

export default {
	components: {},
	data () {
		return {
			moment
		}
	},
	computed: {
		...mapState(['userTimezone']),
		...mapState('schedule', ['schedule']),
		localTimezone () {
			return moment.tz.guess()
		},
		localTimezoneLabel () {
			return moment.tz(this.localTimezone).format('Z z')
		},
		eventTimezone () {
			return 'America/Chicago' // this.schedule.timezone
		},
		eventTimezoneLabel () {
			return moment.tz(this.eventTimezone).format('Z z')
		},
	},
	async created () {},
	async mounted () {
		await this.$nextTick()
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-timezone-changer
	margin-left: 32px
	> .bunt-button
		&.active
			themed-button-primary()
		&:not(.active)
			themed-button-secondary()
			border: 2px solid var(--clr-primary)
		&:first-child
			border-radius: 4px 0 0 4px
		&:last-child
			border-radius: 0 4px 4px 0
		.zone-type
			font-size: 12px
			line-height: 1.1
			font-weight: 400
		.timezone-label
			font-size: 14px
			line-height: 1
</style>
