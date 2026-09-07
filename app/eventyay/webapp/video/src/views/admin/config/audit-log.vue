<template lang="pug">
.c-auditlog
	.ui-page-header
		bunt-icon-button(@click="$router.push({name: 'organizer'})", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h1 {{ $t('Logs') }}
	bunt-input.search(name="search", :placeholder="$t('Search log')", icon="search", v-model="search")
	.auditlog-list
		.header
			.timestamp {{ $t('Timestamp') }}
			.user {{ $t('User') }}
			.type {{ $t('Action type') }}
			.data {{ $t('Data') }}
		RecycleScroller.tbody.bunt-scrollbar(v-if="filteredEntries", :items="filteredEntries", :item-size="48", v-slot="{item: entry}", v-scrollbar.y="")
			div.logentry.table-row(@click.prevent="detailsPrompt = entry")
				.timestamp {{ moment(entry.timestamp).format('L LT') }}
				.user
					avatar.avatar(:user="entry.user", :size="32")
					.name {{ entry.user.profile.display_name }}
				.type(:title="entry.type") {{ entry.type }}
				.data {{ entry.data }}
		bunt-progress-circular(v-else, size="huge", :page="true")
	teleport(to="body")
		transition(name="prompt")
			prompt.details-prompt(v-if="detailsPrompt != null", @close="detailsPrompt = null")
				.content
					h2 {{ $t('Log Entry') }}
					.detail-meta
						.meta-item
							span.label {{ $t('Timestamp') }}:
							span.value {{ moment(detailsPrompt.timestamp).format('L LTS') }}
						.meta-item(v-if="detailsPrompt.user")
							span.label {{ $t('User') }}:
							span.value {{ detailsPrompt.user.profile?.display_name || detailsPrompt.user.id }}
						.meta-item
							span.label {{ $t('Action') }}:
							span.value.type-badge {{ detailsPrompt.type }}
					.detail-data
						span.label {{ $t('Data Payload') }}:
						pre {{ JSON.stringify(detailsPrompt.data, null, 2) }}
					.actions
						bunt-button#btn-close-details(@click="detailsPrompt = null") {{ $t('Close') }}
</template>
<script>
import api from 'lib/api'
import moment from 'moment'
import Avatar from 'components/Avatar'
import Prompt from 'components/Prompt'

export default {
	name: 'AuditLog',
	components: { Avatar, Prompt },
	data() {
		return {
			moment,
			detailsPrompt: null,
			entries: null,
			search: ''
		}
	},
	computed: {
		filteredEntries() {
			if (!this.entries) return
			if (!this.search) return this.entries
			return this.entries.filter(entry => entry.user?.profile?.display_name?.toLowerCase()?.indexOf(this.search.toLowerCase()) >= 0 || entry.type?.toLowerCase()?.startsWith(this.search.toLowerCase()) || JSON.stringify(entry.data)?.toLowerCase()?.indexOf(this.search.toLowerCase()) >= 0)
		}
	},
	created() {
		this.ensureConnectedAndFetch()
	},
	beforeUnmount() {
		if (this._unwatchConnected) this._unwatchConnected()
	},
	methods: {
		ensureConnectedAndFetch() {
			if (this.$store.state.connected) {
				this.fetchEntries()
			} else {
				this._unwatchConnected = this.$store.watch(
					state => state.connected,
					connected => {
						if (connected) {
							this.fetchEntries()
							if (this._unwatchConnected) this._unwatchConnected()
						}
					}
				)
			}
		},
		async fetchEntries() {
			try {
				const res = await api.call('world.auditlog.list')
				this.entries = res?.results || []
			} catch (e) {
				console.error('Failed to fetch audit log entries', e)
			}
		}
	}
}
</script>
<style lang="stylus">
@import 'flex-table'

.c-auditlog
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-white
	.header
		background-color: $clr-grey-50
	.search
		input-style(size: compact)
		padding: 0
		margin: 8px
		flex: none
	.auditlog-list
		flex-table()
		.logentry
			cursor: pointer
		.room
			display: flex
			align-items: center
			color: $clr-primary-text-light
		.timestamp
			width: 128px
			flex: none
			ellipsis()
		.user
			width: 128px
			flex: none
			display: flex
			align-items: center
			.avatar
				width: 32px
				margin: 0 4px 0 0
			.name
				flex: auto
				ellipsis()
		.type
			width: 200px
			flex: none
			ellipsis()
		.data
			flex: auto

.details-prompt
	.prompt-wrapper
		width: 640px !important
		max-width: min(640px, 94vw) !important
		max-height: calc(100vh - 48px) !important
		display: flex
		flex-direction: column
		border-radius: 8px
		overflow: hidden

	.content
		display: flex
		flex-direction: column
		padding: 24px 28px !important
		gap: 16px
		overflow-y: auto
		min-height: 0
		flex: 1 1 auto
		box-sizing: border-box

		h2
			margin: 0
			font-size: 18px
			font-weight: 600
			color: #1e293b

		.detail-meta
			display: flex
			flex-direction: column
			gap: 8px
			background-color: #f8fafc
			padding: 14px 16px
			border-radius: 6px
			border: 1px solid #e2e8f0
			flex-shrink: 0

			.meta-item
				display: flex
				align-items: center
				gap: 10px
				font-size: 13.5px

				.label
					font-weight: 600
					color: #64748b
					min-width: 90px

				.value
					color: #1e293b
					word-break: break-all

				.type-badge
					background-color: #e0f2fe
					color: #0369a1
					padding: 2px 8px
					border-radius: 4px
					font-family: monospace
					font-size: 12px
					font-weight: 600

		.detail-data
			display: flex
			flex-direction: column
			gap: 8px
			min-height: 0
			flex: 1 1 auto

			.label
				font-weight: 600
				font-size: 13.5px
				color: #64748b

			pre
				margin: 0
				padding: 14px
				background-color: #0f172a
				color: #e2e8f0
				border-radius: 6px
				font-size: 12.5px
				line-height: 1.5
				max-height: 300px
				overflow-y: auto
				overflow-x: auto
				box-sizing: border-box
				word-break: normal
				white-space: pre

		.actions
			display: flex
			justify-content: flex-end
			margin-top: 8px
			flex-shrink: 0

			#btn-close-details
				min-width: 90px
</style>
