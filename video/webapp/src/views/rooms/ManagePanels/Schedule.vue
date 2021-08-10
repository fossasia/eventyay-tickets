<template lang="pug">
.c-manage-schedule
	bunt-switch(name="computeSession", v-model="computeSession", label="Compute current session from schedule")
</template>
<script>
export default {
	components: {},
	props: {
		room: Object
	},
	data () {
		return {
		}
	},
	computed: {
		computeSession: {
			get () {
				return this.room.schedule_data?.computeSession
			},
			set (value) {
				if (value) {
					this.$store.dispatch('updateRoomSchedule', {
						room: this.room,
						schedule_data: {
							computeSession: true
						}
					})
				} else {
					this.$store.dispatch('updateRoomSchedule', {
						room: this.room,
						schedule_data: null
					})
				}
			}
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
</style>
