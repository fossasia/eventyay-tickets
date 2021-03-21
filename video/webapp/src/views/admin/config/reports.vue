<template lang="pug">
.c-reports
	.ui-page-header
		h1 Generate Reports
	scrollbars(y).ui-form-body
		h3 Summary report
		div.flex-row
			div
				bunt-input(v-model="day_start", label="First day", name="day_start", :validation="$v.day_start")
			div
				bunt-input(v-model="day_end", label="Last day", name="day_end", :validation="$v.day_end")
		div.flex-row
			div
				bunt-input(v-model="time_start", label="Start of day", name="time_start", :validation="$v.time_start")
			div
				bunt-input(v-model="time_end", label="End of day", name="time_end", :validation="$v.time_end")
		bunt-button.btn-generate(@click="generateSummary", :loading="task == 'summary' && running", :error="task == 'summary' && error") Generate PDF (may take a while)
		bunt-button.btn-secondary(@click="generateRoomviews", :loading="task == 'roomviews' && running", :error="task == 'roomviews' && error") Room activity (XLSX)
		h3 Attendee list
		bunt-button.btn-generate(@click="generateAttendeeList", :loading="task == 'attendee_list' && running", :error="task == 'attendee_list' && error") Generate XLSX (may take a while)
		h3 Chat history
		bunt-select(v-model="channel", label="Room", name="channel", :options="channels", option-label="name")
		bunt-button.btn-generate(@click="generateChatHistory", :loading="task == 'chat' && running", :error="task == 'chat' && error") Generate XLSX (may take a while)
</template>
<script>
import api from 'lib/api'
import i18n from 'i18n'
import moment from 'lib/timetravelMoment'
import {helpers, required} from 'vuelidate/lib/validators'

const day = helpers.regex('day', /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)
const time = helpers.regex('time', /^[0-9]{2}:[0-9]{2}$/)

export default {
	data () {
		return {
			day_start: moment().format('YYYY-MM-DD'),
			day_end: moment().format('YYYY-MM-DD'),
			time_start: '07:00',
			time_end: '19:00',
			channel: null,
			resultid: null,
			running: false,
			error: false,
			timeout: null,
			task: null,
		}
	},
	computed: {
		strings () {
			return i18n.messages[i18n.locale]
		},
		channels () {
			const r = []
			r.push(...this.$store.state.rooms.filter((room) => room.modules.filter(m => m.type === 'chat.native').length).map((room) => {
				return {
					id: room.modules.find(m => m.type === 'chat.native').channel_id,
					name: room.name
				}
			}))
			return r
		}
	},
	validations: {
		day_start: {
			day,
			required,
		},
		day_end: {
			day,
			required,
		},
		time_start: {
			time,
			required,
		},
		time_end: {
			time,
			required,
		},
	},
	destroyed () {
		window.clearTimeout(this.timeout)
	},
	methods: {
		async generateAttendeeList () {
			this.running = true
			this.error = false
			this.task = 'attendee_list'
			try {
				const r = await api.call('world.report.generate.attendee_list', {
				})
				this.resultid = r.resultid
				this.timeout = window.setTimeout(this.check, 2000)
			} catch {
				this.error = true
				this.running = false
			}
		},
		async generateChatHistory () {
			if (!this.channel) return

			this.running = true
			this.error = false
			this.task = 'chat'
			try {
				const r = await api.call('world.report.generate.chat_history', {
					channel: this.channel
				})
				this.resultid = r.resultid
				this.timeout = window.setTimeout(this.check, 2000)
			} catch {
				this.error = true
				this.running = false
			}
		},
		async generateRoomviews () {
			this.$v.$touch()
			if (this.$v.$invalid) return

			this.running = true
			this.error = false
			this.task = 'roomviews'
			try {
				const r = await api.call('world.report.generate.roomviews', {
					begin: this.day_start + 'T' + this.time_start,
					end: this.day_end + 'T' + this.time_end,
				})
				this.resultid = r.resultid
				this.timeout = window.setTimeout(this.check, 2000)
			} catch {
				this.error = true
				this.running = false
			}
		},
		async generateSummary () {
			this.$v.$touch()
			if (this.$v.$invalid) return

			this.running = true
			this.error = false
			this.task = 'summary'
			try {
				const r = await api.call('world.report.generate.summary', {
					begin: this.day_start + 'T' + this.time_start,
					end: this.day_end + 'T' + this.time_end,
				})
				this.resultid = r.resultid
				this.timeout = window.setTimeout(this.check, 2000)
			} catch {
				this.error = true
				this.running = false
			}
		},
		async check () {
			try {
				const r = await api.call('world.report.status', {
					resultid: this.resultid
				})
				if (r.ready) {
					window.open(r.result)
					this.error = false
					this.running = false
				} else {
					this.timeout = window.setTimeout(this.check, 2000)
				}
			} catch {
				this.error = true
				this.running = false
			}
		}
	}
}
</script>
<style lang="stylus">
.c-reports
	flex: auto
	display: flex
	flex-direction: column
	.flex-row
		display: flex
		gap: 20px
		margin: 0 -10px
		&> div
			flex: auto 1 1
			margin: 0 10px

	.btn-generate
		margin-bottom: 32px
		themed-button-primary()
	.btn-secondary
		margin-bottom: 32px
		themed-button-secondary()

	.bunt-input-outline-container
		textarea
			background-color: transparent
			border: none
			outline: none
			resize: vertical
			min-height: 250px
			padding: 0 8px
</style>
