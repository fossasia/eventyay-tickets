<template lang="pug">
.c-schedule
	template(v-if="schedule")
		//- linear-schedule
		grid-schedule
		//- pretalx-schedule(v-if="pretalxEvent", :schedule="pretalxEvent")

	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState } from 'vuex'
import PretalxSchedule from 'components/pretalx/Schedule'
import LinearSchedule from 'components/schedule/LinearSchedule'
import GridSchedule from 'components/schedule/GridSchedule'

export default {
	components: { PretalxSchedule, LinearSchedule, GridSchedule },
	data () {
		return {
		}
	},
	computed: {
		...mapState(['schedule', 'pretalxEvent'])
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
.c-schedule
	display: flex
	// flex-direction: column
	min-height: 0
</style>
