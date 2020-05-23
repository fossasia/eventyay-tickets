<template lang="pug">
.pretalx-schedule(:class="{mobile}", ref="wrapper", :style="style")
	.header
		h2 Schedule
		bunt-tabs(v-if="schedule.schedule.length > 1", :active-tab="activeDay.start")
			bunt-tab(v-for="day in schedule.schedule", :id="day.start", :header="formatDate(day.start)", @selected="activeDay = day")
		.pretalx-widget-attribution
			| · powered by #[a(href="https://pretalx.com", rel="noopener", target="_blank") pretalx] ·
	pretalx-schedule-day(:day="activeDay", :key="activeDay.start")
</template>
<script>
import moment from 'lib/timetravelMoment'
import PretalxScheduleDay from './ScheduleDay'

export default {
	name: 'pretalx-schedule',
	components: { PretalxScheduleDay },
	props: {
		schedule: Object
	},
	data () {
		return {
			scheduleData: null,
			mobile: false,
			activeDay: null,
		}
	},
	computed: {
		style () {
			/* if (this.widgetData.height) {
				return {
					'max-height': this.widgetData.height,
					display: 'block',
				}
			} */
			return {}
		},
	},
	filters: {
		dateDisplay (value) {
			return moment(value).format('dddd, LL')
		}
	},
	created () {
		// TODO properly set this globally
		const lang = 'en'
		moment.locale(lang)
		moment.updateLocale(lang, {
			longDateFormat: {
				LL: moment.localeData()._longDateFormat.LL.replace(/Y/g, '').replace(/,? *$/, '')
			}
		})
		this.activeDay = this.schedule.schedule.find(day => moment().isSame(day.start, 'day')) ?? this.schedule.schedule[0]
	},
	mounted () {
		// TODO replace with proper mq support
		this.mobile = this.$refs && this.$refs.wrapper && this.$refs.wrapper.clientWidth <= 800
	},
	methods: {
		formatDate (value) {
			return moment(value).format('dddd, LL')
		}
	}
}
</script>
<style lang="stylus">
.pretalx-schedule
	--pixels-per-minute: 2
	display: flex
	flex-direction: column
	flex: auto
	min-height: 0
	> .header
		display: flex
		justify-content: space-between
		align-items: center
		height: 48px
		padding: 0 16px
		border-bottom: border-separator()
		h2
			margin: 0
			font-weight: 400
		> .bunt-tabs
			tabs-style(
				background-color: transparent,
				color: $clr-secondary-text-light,
				active-color: $clr-primary-text-light,
				indicator-color: var(--clr-primary)
			)
			width: auto
			margin-bottom: 0
			display: flex
			flex-direction: column
</style>
