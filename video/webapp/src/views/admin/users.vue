<template lang="pug">
.c-admin-users
	.header
		h2 Users
		bunt-input.search(name="search", placeholder="Search users", icon="search", v-model="search")
	.users-list
		.header
			.avatar
			.id ID
			.name Name
			.state State
			.actions
		RecycleScroller.tbody.bunt-scrollbar(v-if="filteredUsers", :items="filteredUsers", :item-size="48", v-slot="{item: user}", v-scrollbar.y="")
			.user.table-row(:class="{error: user.error, updating: user.updating}")
				avatar.avatar(:user="user", :size="32")
				.id(:title="user.id") {{ user.id }}
				.name {{ user.profile.display_name }}
				.state {{ user.moderation_state }}
				.actions(v-if="user.id !== ownUser.id")
					//- moderation_state
					.placeholder.mdi.mdi-dots-horizontal
					bunt-button.btn-open-dm(@click="$store.dispatch('chat/openDirectMessage', {user})") message
					bunt-button.btn-reactivate(
						v-if="user.moderation_state",
						:loading="user.updating === 'reactivate'",
						:error-message="(user.error && user.error.action === 'reactivate') ? user.error.message : null",
						tooltipPlacement="left",
						@click="doAction(user, 'reactivate', null)", :key="`${user.id}-reactivate`")
						| {{ user.moderation_state === 'banned' ? 'unban' : 'unsilence'}}
					bunt-button.btn-ban(
						v-if="user.moderation_state !== 'banned'",
						:loading="user.updating === 'ban'",
						:error-message="(user.error && user.error.action === 'ban') ? user.error.message : null",
						tooltipPlacement="left",
						@click="doAction(user, 'ban', 'banned')", :key="`${user.id}-ban`")
						| ban
					bunt-button.btn-silence(
						v-if="!user.moderation_state",
						:loading="user.updating === 'silence'",
						:error-message="(user.error && user.error.action === 'silence') ? user.error.message : null",
						tooltipPlacement="left",
						@click="doAction(user, 'silence', 'silenced')", :key="`${user.id}-silence`")
						| silence
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
// TODO
// - search
import { mapState } from 'vuex'
import api from 'lib/api'
import fuzzysearch from 'lib/fuzzysearch'
import Avatar from 'components/Avatar'

export default {
	name: 'AdminUsers',
	components: { Avatar },
	data () {
		return {
			users: null,
			search: ''
		}
	},
	computed: {
		...mapState({
			ownUser: 'user'
		}),
		filteredUsers () {
			if (!this.users) return
			if (!this.search) return this.users
			return this.users.filter(user => user.id === this.search.trim() || fuzzysearch(this.search.toLowerCase(), user.profile?.display_name?.toLowerCase()))
		}
	},
	async created () {
		this.users = (await api.call('user.list')).results.map(user => {
			return {
				...user,
				updating: null,
				error: null
			}
		})
	},
	methods: {
		async doAction (user, action, postState) {
			user.updating = action
			user.error = null
			try {
				await api.call(`user.${action}`, {id: user.id})
				user.moderation_state = postState
			} catch (error) {
				user.error = {
					action,
					message: this.$t(`error:${error.code}`)
				}
			}
			user.updating = null
		}
	}
}
</script>
<style lang="stylus">
@import '~styles/flex-table'

.c-admin-users
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-white
	.header
		background-color: $clr-grey-50
	h2
		margin: 16px
	.search
		input-style(size: compact)
		padding: 0
		margin: 8px
		flex: none
	.users-list
		flex-table()
		.user
			display: flex
			align-items: center
		.avatar
			width: 32px
			padding-right: 0
		.id
			width: 128px
			ellipsis()
		.name
			flex: auto
		.state
			width: 78px
		.actions
			flex: none
			width: 260px
			padding: 0 24px 0 0
			display: flex
			align-items: center
			justify-content: flex-end
			.placeholder
				flex: none
				color: $clr-secondary-text-light
			.btn-open-dm
				button-style(style: clear)
			.btn-reactivate
				button-style(style: clear, color: $clr-success, text-color: $clr-success)
			.btn-ban
				button-style(style: clear, color: $clr-danger, text-color: $clr-danger)
			.btn-silence
				button-style(style: clear, color: $clr-deep-orange, text-color: $clr-deep-orange)
		.user:not(:hover):not(.error):not(.updating)
			.actions .bunt-button
				display: none
		.user:hover, .user.error, .user.updating
			.actions .placeholder
				display: none
</style>
