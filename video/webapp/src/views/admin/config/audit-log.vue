<template lang="pug">
.c-auditlog
	.ui-page-header
		h1 Audit Log
	bunt-input.search(name="search", placeholder="Search log", icon="search", v-model="search")
	.auditlog-list
		.header
			.timestamp Timestamp
			.user User
			.type Action type
			.data Data
		RecycleScroller.tbody.bunt-scrollbar(v-if="filteredEntries", :items="filteredEntries", :item-size="48", v-slot="{item: entry}", v-scrollbar.y="")
			div.logentry.table-row(@click.prevent="detailsPrompt = entry")
				.timestamp {{ moment(entry.timestamp).format('L LT') }}
				.user
					avatar.avatar(:user="entry.user", :size="32")
					.name {{ entry.user.profile.display_name }}
				.type(:title="entry.type") {{ entry.type }}
				.data {{ entry.data }}
		bunt-progress-circular(v-else, size="huge", :page="true")
	transition(name="prompt")
		prompt.details-prompt(v-if="detailsPrompt != null")
			.content
				bunt-icon-button#btn-close(@click="detailsPrompt = null") close
				p {{ moment(detailsPrompt.timestamp).format('L LT') }}
				p {{ detailsPrompt.user.profile.display_name }}
				p {{ detailsPrompt.type }}
				code
					pre {{ JSON.stringify(detailsPrompt.data, null, 2) }}
</template>
<script>
import api from 'lib/api'
import moment from 'moment'
import Avatar from 'components/Avatar'
import Prompt from 'components/Prompt'

export default {
	name: 'AuditLog',
	components: { Avatar, Prompt },
	data () {
		return {
			moment,
			detailsPrompt: null,
			entries: null,
			search: ''
		}
	},
	computed: {
		filteredEntries () {
			if (!this.entries) return
			if (!this.search) return this.entries
			return this.entries.filter(entry => entry.user.profile.display_name.toLowerCase().indexOf(this.search.toLowerCase()) >= 0 || entry.type.toLowerCase().startsWith(this.search.toLowerCase()) || JSON.stringify(entry.data).toLowerCase().indexOf(this.search.toLowerCase()) >= 0)
		}
	},
	async created () {
		this.entries = (await api.call('world.auditlog.list')).results
	}
}
</script>
<style lang="stylus">
@import '~styles/flex-table'

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
		.content
			display: flex
			flex-direction: column
			padding: 32px
			position: relative
		p
			margin: 4px
		pre
			width: 100%
			overflow-x: auto
</style>
