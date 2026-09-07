<template lang="pug">
.c-reports
	.ui-page-header
		bunt-icon-button(@click="$router.push({name: 'organizer'})", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h1 {{ $t('Generate Reports') }}
	scrollbars(y).ui-form-body
		.report-section
			.section-header-with-controls
				h3 {{ $t('Analytics Reports') }}
				.date-controls
					.quick-presets
						bunt-button(@click="setToday", :class="{active: activePreset === 'today'}", :aria-pressed="activePreset === 'today'") {{ $t('Today') }}
						bunt-button(@click="setYesterday", :class="{active: activePreset === 'yesterday'}", :aria-pressed="activePreset === 'yesterday'") {{ $t('Yesterday') }}
						bunt-button(@click="setLast7Days", :class="{active: activePreset === 'last7days'}", :aria-pressed="activePreset === 'last7days'") {{ $t('Last 7 Days') }}
						bunt-button(@click="setThisWeek", :class="{active: activePreset === 'thisweek'}", :aria-pressed="activePreset === 'thisweek'") {{ $t('This Week') }}
						bunt-button(@click="toggleCustom", :class="{active: activePreset === 'custom'}", :aria-pressed="activePreset === 'custom'") {{ $t('Custom') }}
					.date-time-inputs(v-if="showCustom")
						bunt-input(v-model="datetimeStart", name="datetime_start", type="datetime-local", :label="$t('From')")
						bunt-input(v-model="datetimeEnd", name="datetime_end", type="datetime-local", :label="$t('To')")
			.report-buttons
				bunt-button(@click="generateSummary", :error="task == 'summary' && error") {{ $t('Summary') }}
				bunt-button(@click="generateRoomviews", :error="task == 'roomviews' && error") {{ $t('Room Activity') }}
				bunt-button(v-if="world.pretalx", @click="generateSessionviews", :error="task == 'sessionviews' && error") {{ $t('Session Activity') }}
				bunt-button(@click="generateViews", :error="task == 'views' && error") {{ $t('Raw Tracking') }}

		.report-section
			h3 {{ $t('Attendee Reports') }}
			.report-buttons
				bunt-button(@click="run('attendee_list', {})", :error="task == 'attendee_list' && error") {{ $t('All Attendees') }}
				bunt-button(@click="run('attendee_session_list', {})", :error="task == 'attendee_session_list' && error") {{ $t('By Session') }}
		
		.report-section
			h3 {{ $t('Room-Specific Reports') }}
			.room-report-item
				bunt-select(v-model="channel", :label="$t('Chat History')", name="channel", :options="channels", option-label="name")
				bunt-button(@click="run('chat_history', {channel})", :disabled="!channel", :error="task == 'chat_history' && error") {{ $t('Generate') }}
			.room-report-item
				bunt-select(v-model="questionRoom", :label="$t('Questions')", name="questionRoom", :options="questionRooms", option-label="name")
				bunt-button(@click="run('question_history', {room: questionRoom})", :disabled="!questionRoom", :error="task == 'question_history' && error") {{ $t('Generate') }}
			.room-report-item
				bunt-select(v-model="pollRoom", :label="$t('Polls')", name="pollRoom", :options="pollRooms", option-label="name")
				bunt-button(@click="run('poll_history', {room: pollRoom})", :disabled="!pollRoom", :error="task == 'poll_history' && error") {{ $t('Generate') }}

	transition(name="prompt")
		prompt.report-result-prompt(v-if="running || result", @close="clear")
			.content
				h1(v-if="running") {{ $t('Preparing report…') }}
				h1(v-else) {{ $t('Report ready') }}
				bunt-progress-circular(v-if="running", size="huge")
				bunt-button.btn-download(v-else, @click="open") {{ $t('Download report') }}
				p(v-if="running") {{ $t('If your event is large, this might take multiple minutes.') }}

</template>
<script>
import { mapState } from 'vuex'
import api from 'lib/api'
import moment from 'lib/timetravelMoment'
import Prompt from 'components/Prompt'

export default {
	components: { Prompt },
	data() {
		const now = moment()
		return {
			showCustom: false,
			activePreset: 'today',
			datetimeStart: now.clone().startOf('day').format('YYYY-MM-DDTHH:mm'),
			datetimeEnd: now.clone().endOf('day').format('YYYY-MM-DDTHH:mm'),
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
		questionRooms() {
			return this.$store.state.rooms.filter((room) => room.modules.some(m => m.type === 'question'))
		},
		pollRooms() {
			return this.$store.state.rooms.filter((room) => room.modules.some(m => m.type === 'poll'))
		},
		channels() {
			return this.$store.state.rooms.filter((room) => room.modules.some(m => m.type === 'chat.native')).map((room) => {
				return {
					id: room.modules.find(m => m.type === 'chat.native').channel_id,
					name: room.name
				}
			})
		}
	},
	unmounted() {
		window.clearTimeout(this.timeout)
	},
	methods: {
		getDateTimePayload() {
			return {
				begin: this.datetimeStart,
				end: this.datetimeEnd,
			}
		},
		setPreset(presetName, startMoment, endMoment) {
			this.datetimeStart = startMoment.format('YYYY-MM-DDTHH:mm')
			this.datetimeEnd = endMoment.format('YYYY-MM-DDTHH:mm')
			this.activePreset = presetName
			this.showCustom = false
		},
		setToday() {
			const today = moment()
			this.setPreset('today', today.clone().startOf('day'), today.clone().endOf('day'))
		},
		setYesterday() {
			const yesterday = moment().subtract(1, 'day')
			this.setPreset('yesterday', yesterday.clone().startOf('day'), yesterday.clone().endOf('day'))
		},
		setLast7Days() {
			const now = moment()
			this.setPreset('last7days', now.clone().subtract(6, 'days').startOf('day'), now.clone().endOf('day'))
		},
		setThisWeek() {
			const now = moment()
			this.setPreset('thisweek', now.clone().startOf('week'), now.clone().endOf('week'))
		},
		toggleCustom() {
			this.showCustom = !this.showCustom
			if (this.showCustom) {
				this.activePreset = 'custom'
			} else if (this.activePreset === 'custom') {
				// Reset to today when toggling off custom - updates both preset and datetime values
				this.setToday()
			}
		},
		generateReport(type) {
			return this.run(type, this.getDateTimePayload())
		},
		generateSummary() {
			return this.generateReport('summary')
		},
		generateRoomviews() {
			return this.generateReport('roomviews')
		},
		generateSessionviews() {
			return this.generateReport('sessionviews')
		},
		generateViews() {
			return this.generateReport('views')
		},
		async run(name, payload) {
			this.running = true
			this.error = false
			this.task = name
			try {
				const r = await api.call(`world.report.generate.${name}`, payload)
				this.resultid = r.resultid
				this.timeout = window.setTimeout(this.check, 2000)
			} catch (err) {
				console.error('Report generation failed:', String(err))
				this.error = true
				this.running = false
			}
		},
		async check() {
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
			} catch (err) {
				console.error('Report status check failed:', String(err))
				this.error = true
				this.running = false
			}
		},
		open() {
			window.open(this.result)
			this.clear()
		},
		clear() {
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

	.ui-form-body
		padding: 20px
		max-width: 100%

	.report-section
		margin-bottom: 32px
		padding: 5px 5px 20px 5px
		background: $clr-white
		border-radius: 4px
		box-shadow: 0 1px 3px rgba(0,0,0,0.08)

		h3
			margin: 0 0 16px 0
			font-size: 18px
			font-weight: 600
			line-height: 1.4

		.section-header-with-controls
			display: flex
			justify-content: space-between
			align-items: flex-start
			gap: 24px
			margin-bottom: 16px
			flex-wrap: wrap

			h3
				margin: 0
				flex-shrink: 0

			.date-controls
				display: flex
				flex-direction: column
				gap: 12px
				align-items: flex-end
				flex: 1
				min-width: 300px

				.quick-presets
					display: flex
					gap: 6px
					flex-wrap: wrap
					justify-content: flex-end

					button
						themed-button-secondary()
						font-size: 13px
						padding: 6px 12px

						&.active
							themed-button-primary()

				.date-time-inputs
					display: flex
					gap: 12px
					flex-wrap: wrap
					justify-content: flex-end

					.bunt-input
						min-width: 200px
						max-width: 250px

		.report-buttons
			display: flex
			flex-wrap: wrap
			gap: 12px

			button
				themed-button-secondary()
				flex-shrink: 0
				background-color var(--clr-input-secondary-fg-alpha)

		.room-report-item
			display: flex
			align-items: baseline
			gap: 16px
			margin-bottom: 12px

			.bunt-select
				flex: 1
				max-width: 400px

			button
				themed-button-secondary()
				flex-shrink: 0
				background-color var(--clr-input-secondary-fg-alpha)

	.report-result-prompt
		.content
			padding: 0 20px 20px
			text-align: center
			.btn-download
				themed-button-primary()
</style>
