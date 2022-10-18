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
		bunt-button.btn-generate(@click="generateSummary", :error="task == 'summary' && error") Generate PDF
		bunt-button.btn-secondary(@click="generateRoomviews", :error="task == 'roomviews' && error") Room activity (XLSX)
		bunt-button.btn-secondary(v-if="world.pretalx", @click="generateSessionviews", :error="task == 'sessionviews' && error") Session activity (XLSX)
		bunt-button.btn-secondary(@click="generateViews", :error="task == 'views' && error") Raw tracking data (XLSX)
		h3 Attendee list
		bunt-button.btn-generate(@click="run('attendee_list', {})", :error="task == 'attendee_list' && error") Generate XLSX
		h3 Chat history
		bunt-select(v-model="channel", label="Room", name="channel", :options="channels", option-label="name")
		bunt-button.btn-generate(@click="run('chat_history', {channel})", :disabled="!channel", :error="task == 'chat_history' && error") Generate XLSX
		h3 Questions
		bunt-select(v-model="questionRoom", label="Room", name="questionRoom", :options="questionRooms", option-label="name")
		bunt-button.btn-generate(@click="run('question_history', {room: questionRoom})", :disabled="!questionRoom", :error="task == 'question_history' && error") Generate XLSX
		h3 Polls
		bunt-select(v-model="pollRoom", label="Room", name="pollRoom", :options="pollRooms", option-label="name")
		bunt-button.btn-generate(@click="run('poll_history', {room: pollRoom})", :disabled="!pollRoom", :error="task == 'poll_history' && error") Generate XLSX
	transition(name="prompt")
		prompt.report-result-prompt(v-if="running || result", @close="clear")
			.content
				h1(v-if="running") Preparing report…
				h1(v-else) Report ready
				bunt-progress-circular(v-if="running", size="huge")
				bunt-button.btn-download(v-else, @click="open") Download report
				p(v-if="running") If your event is large, this might take multiple minutes.

</template>
<script>
import { mapState } from 'vuex'
import api from 'lib/api'
import moment from 'lib/timetravelMoment'
import {helpers, required} from 'vuelidate/lib/validators'
import Prompt from 'components/Prompt'

const day = helpers.regex('day', /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/)
const time = helpers.regex('time', /^[0-9]{2}:[0-9]{2}$/)

export default {
	components: { Prompt },
	data () {
		return {
			day_start: moment().format('YYYY-MM-DD'),
			day_end: moment().format('YYYY-MM-DD'),
			time_start: '07:00',
			time_end: '19:00',
			channel: null,
			questionRoom: null,
			pollRoom: null,
			resultid: null,
			result: null,
			running: false,
			error: false,
			timeout: null,
			task: null,
		}
	},
	computed: {
		...mapState(['world']),
		questionRooms () {
			const r = []
			r.push(...this.$store.state.rooms.filter((room) => room.modules.filter(m => m.type === 'question').length))
			return r
		},
		pollRooms () {
			const r = []
			r.push(...this.$store.state.rooms.filter((room) => room.modules.filter(m => m.type === 'poll').length))
			return r
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
		async generateViews () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			await this.run('views', {
				begin: this.day_start + 'T' + this.time_start,
				end: this.day_end + 'T' + this.time_end,
			})
		},
		async generateRoomviews () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			await this.run('roomviews', {
				begin: this.day_start + 'T' + this.time_start,
				end: this.day_end + 'T' + this.time_end,
			})
		},
		async generateSessionviews () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			await this.run('sessionviews', {
				begin: this.day_start + 'T' + this.time_start,
				end: this.day_end + 'T' + this.time_end,
			})
		},
		async generateSummary () {
			this.$v.$touch()
			if (this.$v.$invalid) return

			await this.run('summary', {
				begin: this.day_start + 'T' + this.time_start,
				end: this.day_end + 'T' + this.time_end,
			})
		},
		async run (name, payload) {
			this.running = true
			this.error = false
			this.task = name
			try {
				const r = await api.call(`world.report.generate.${name}`, payload)
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
					this.result = r.result
					this.error = false
					this.running = false
				} else {
					this.timeout = window.setTimeout(this.check, 2000)
				}
			} catch {
				this.error = true
				this.running = false
			}
		},
		open () {
			window.open(this.result)
			this.clear()
		},
		clear () {
			this.result = null
			this.error = false
			this.running = false
			window.clearTimeout(this.timeout)
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
	.report-result-prompt
		.content
			padding: 0 20px 20px
			text-align: center
			.btn-download
				themed-button-primary()
</style>
