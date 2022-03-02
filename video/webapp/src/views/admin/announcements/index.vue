<template lang="pug">
.c-admin-announcements
	.ui-page-header
		h1 Announcements
		.actions
			bunt-link-button#btn-create(:to="{name: 'admin:announcements:item', params: {announcementId: 'new'}}") Create a new announcement
	.page-content(v-if="announcements")
		.announcements-list
			.header
				.state state
				.text text
				.show-until show until
			.tbody(v-scrollbar.y="")
				router-link.announcement.table-row(v-for="announcement of announcements", :to="{name: 'admin:announcements:item', params: {announcementId: announcement.id}}")
					.state(:class="[announcement.state, {expired: announcement.expired}]")
					.text {{ announcement.text }}
					.show-until {{ announcement.show_until ? announcement.show_until.format('LLL') : '' }}
		router-view(:announcements="rawAnnouncements")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
// TODO
// - server won't send draft announcements via websocket?
// - add created column?
import { mapState } from 'vuex'
import moment from 'moment'
import api from 'lib/api'

export default {
	components: {},
	data () {
		return {
			rawAnnouncements: null
		}
	},
	computed: {
		...mapState(['now']),
		announcements () {
			if (!this.rawAnnouncements) return null
			return this.rawAnnouncements.map(announcement => {
				// COPYPASTA from store
				const showUntil = announcement.show_until ? moment(announcement.show_until) : null
				return Object.assign({}, announcement, {
					show_until: showUntil,
					expired: showUntil?.isBefore(this.now)
				})
			}).sort((a, b) => {
				if (a.state === 'draft' && b.state === 'active') return -1
				if (a.state === 'active' && b.state === 'draft') return 1
				if (a.state === 'draft' && b.state === 'archived') return -1
				if (a.state === 'archived' && b.state === 'draft') return 1
				if (a.state === 'active' && b.state === 'archived') return -1
				if (a.state === 'archived' && b.state === 'active') return 1
				if (a.state === 'active' && b.state === 'active') {
					if (a.expired && !b.expired) return 1
					if (!a.expired && b.expired) return -1
				}
				return a.show_until?.isAfter(b.show_until) ? -1 : 1
			})
		}
	},
	async created () {
		this.rawAnnouncements = (await api.call('announcement.list'))
	}
}
</script>
<style lang="stylus">
@import '~styles/flex-table'

.c-admin-announcements
	display: flex
	flex-direction: column
	min-height: 0
	min-width: 0
	#btn-create
		themed-button-primary()
	h2
		margin: 16px
	.page-content
		flex: auto
		display: flex
		min-height: 0
		.announcements-list
			flex-table()
			min-height: 0
			.announcement
				display: flex
				align-items: center
				color: $clr-primary-text-light
				cursor: pointer
				&.router-link-exact-active
					background-color: $clr-grey-200
			.state
				flex: none
				width: 80px
				padding: 0 4px 0 16px
				text-align: center
			.text
				flex: auto
				ellipsis()
			.show-until
				flex: none
				width: 160px
			.announcement
				.active
					color: $clr-danger
					&.is-active
						color: $clr-success
			.tbody
				.state
					display: flex
					align-items: center
					justify-content: center
					&::before
						height: 18px
						padding: 2px 8px
						display: inline-block
						text-transform: uppercase
						font-weight: 500
						line-height: @height
						color: $clr-primary-text-dark
					&.draft::before
						content: 'draft'
						background-color: $clr-blue
					&.active::before
						content: 'active'
						background-color: $clr-success
					&.active.expired::before
						content: 'expired'
						background-color: $clr-warning
					&.archived::before
						content: 'archived'
						background-color: $clr-grey-600
</style>
