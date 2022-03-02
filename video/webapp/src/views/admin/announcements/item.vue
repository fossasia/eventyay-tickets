<template lang="pug">
.c-announcement(v-if="announcement", :class="[announcement.state, {expired: announcement.expired}]")
	.header
		h2(v-if="!announcement.id") Draft New Announcement
		template(v-else)
			h2 Edit
			.actions
				bunt-link-button#btn-clone(:to="{name: 'admin:announcements:item', params: {announcementId: 'new'}, query: {text: announcement.text, show_until: announcement.show_until ? announcement.show_until.format() : null}}") Clone
				bunt-button#btn-progress-state(v-if="announcement.state !== 'archived'", :loading="settingState", @click="progressState") {{ announcement.state === 'draft' ? 'activate' : 'archive' }}
	scrollbars(y)
		bunt-input-outline-container(label="Text", name="text")
			textarea.text(slot-scope="{focus, blur}", @focus="focus", @blur="blur", v-model="announcement.text", :disabled="announcement.state !== 'draft'")
		bunt-input.floating-label(name="show-until", label="Show Until", type="datetime-local", v-model="plainShowUntil", :disabled="announcement.state !== 'draft'")
		.button-group
			bunt-button(:class="{selected: !announcement.show_until}", @click="clearShowUntil", :disabled="announcement.state !== 'draft'") forever
			bunt-button(@click="modifyToShowUntil({minutes: 10})", :disabled="announcement.state !== 'draft'") {{showUntilModifyOperator}}10min
			bunt-button(@click="modifyToShowUntil({minutes: 30})", :disabled="announcement.state !== 'draft'") {{showUntilModifyOperator}}30min
			bunt-button(@click="modifyToShowUntil({hours: 1})", :disabled="announcement.state !== 'draft'") {{showUntilModifyOperator}}1h
			bunt-button(@click="modifyToShowUntil({hours: 24})", :disabled="announcement.state !== 'draft'") {{showUntilModifyOperator}}24h
		bunt-button#btn-save(:loading="saving", @click="save", :disabled="announcement.state !== 'draft'") {{ !announcement.id ? 'create' : 'save' }}
</template>
<script>
// TODO
// - clean up that moment(show_until) mess
// - warn if show_until is in the past
import moment from 'moment'
import api from 'lib/api'

export default {
	props: {
		announcements: Array,
		announcementId: String
	},
	data () {
		return {
			announcement: null,
			saving: false,
			settingState: false,
			shiftPressed: false
		}
	},
	computed: {
		plainShowUntil: {
			get () {
				return this.announcement.show_until?.format('yyyy-MM-DDTHH:mm')
			},
			set (value) {
				this.announcement.show_until = moment(value)
			}
		},
		showUntilModifyOperator () {
			return this.shiftPressed ? '–' : '+'
		}
	},
	watch: {
		announcementId: {
			handler () {
				if (this.announcementId === 'new') {
					this.announcement = {
						state: 'draft',
						text: this.$route.query.text || '',
						show_until: this.$route.query.show_until ? moment(this.$route.query.show_until) : null
					}
				} else {
					this.announcement = Object.assign({}, this.announcements.find(a => a.id === this.announcementId))
					this.announcement.show_until = this.announcement.show_until ? moment(this.announcement.show_until) : null
				}
			},
			immediate: true
		}
	},
	created () {
		document.addEventListener('keydown', this.onGlobalKeyDown)
		document.addEventListener('keyup', this.onGlobalKeyUp)
	},
	beforeDestroy () {
		document.removeEventListener('keydown', this.onGlobalKeyDown)
		document.removeEventListener('keyup', this.onGlobalKeyUp)
	},
	methods: {
		onGlobalKeyDown (event) {
			if (event.key === 'Shift') {
				this.shiftPressed = true
			}
		},
		onGlobalKeyUp (event) {
			if (event.key === 'Shift') {
				this.shiftPressed = false
			}
		},
		modifyToShowUntil (duration, event) {
			// TODO document the shift
			if (!this.announcement.show_until) this.announcement.show_until = moment().startOf('minute')
			this.announcement.show_until = moment(this.announcement.show_until[this.shiftPressed ? 'subtract' : 'add'](duration))
		},
		clearShowUntil () {
			this.announcement.show_until = null
		},
		async save () {
			this.saving = true
			if (this.announcement.id) {
				const { announcement } = await api.call('announcement.update', this.announcement)
				const existingAnnouncement = this.announcements.find(a => a.id === announcement.id)
				Object.assign(existingAnnouncement, announcement)
			} else {
				const { announcement } = await api.call('announcement.create', this.announcement)
				// TODO not really best practice
				this.announcements.push(announcement)
				this.$router.push({ name: 'admin:announcements:item', params: {announcementId: announcement.id}})
				this.announcement = Object.assign({}, announcement)
				this.announcement.show_until = this.announcement.show_until ? moment(this.announcement.show_until) : null
			}
			this.saving = false
		},
		async progressState () {
			this.settingState = true
			const { announcement } = await api.call('announcement.update', {
				id: this.announcement.id,
				state: this.announcement.state === 'draft' ? 'active' : 'archived'
			})
			this.announcement = announcement
			this.announcement.show_until = this.announcement.show_until ? moment(this.announcement.show_until) : null
			const existingAnnouncement = this.announcements.find(a => a.id === announcement.id)
			Object.assign(existingAnnouncement, announcement)
			this.settingState = false
		}
	}
}
</script>
<style lang="stylus">
.c-announcement
	display: flex
	flex-direction: column
	width: 360px
	border-left: border-separator()
	min-height: 0
	.header
		display: flex
		align-items: center
		height: 48px
		box-sizing: border-box
		padding: 8px
		border-bottom: border-separator()
		h2
			font-size: 20px
			font-weight: 500
			margin: 0
		.actions
			display: flex
			flex: auto
			justify-content: flex-end
			gap: 8px
			#btn-progress-state
				button-style(color: $clr-danger)
				^[0].draft ^[1..-1]
					button-style(color: $clr-success)
	.scroll-content
		padding: 8px
	.bunt-input-outline-container
		margin: 8px 0
	textarea
		font-family: $font-stack
		font-size: 16px
		background-color: transparent
		border: none
		outline: none
		resize: vertical
		min-height: 250px
		padding: 0 8px
	.bunt-input
		input-style(size: compact)
	// TODO decopypaste
	.button-group
		margin: 4px 0 16px 0
		display: flex
		> .bunt-button
			flex: auto
			border-radius: 0
			font-size: 12px
			height: 26px
			padding: 0 12px
			min-width: 0
			&.selected
				themed-button-primary()
			&:not(.selected)
				themed-button-secondary()
				border: 2px solid var(--clr-primary)
			&:first-child
				border-radius: 4px 0 0 4px
			&:last-child
				border-radius: 0 4px 4px 0
			&:not(:last-child)
				border-right: none
	#btn-save
		themed-button-primary()
		align-self: flex-start
		padding: 0 32px
</style>
