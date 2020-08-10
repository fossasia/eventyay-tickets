<template lang="pug">
.c-schedule
	pretalx-schedule(v-if="schedule", :schedule="schedule")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState } from 'vuex'
import PretalxSchedule from 'components/pretalx/Schedule'

export default {
	components: { PretalxSchedule },
	data () {
		return {
		}
	},
	computed: {
		...mapState(['schedule'])
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
	flex-direction: column
	min-height: 0
</style>
