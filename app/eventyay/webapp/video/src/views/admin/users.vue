<template lang="pug">
.c-admin-users
	.ui-page-header
		bunt-icon-button(@click="$router.push({name: 'organizer'})", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h2 {{ $t('Users') }}
		.actions
			bunt-input.search(name="search", :placeholder="$t('Search users')", icon="search", v-model="search")
	.users-list
		.header
			.avatar
			.id {{ $t('ID') }}
			.tokenid {{ $t('External ID') }}
			.name {{ $t('Name') }}
			.email {{ $t('Email') }}
			.ticket-info
				span.ticket-info-head-order {{ $t('Order/') }}
				span.ticket-info-head-ticket {{ $t('Ticket code') }}
			.wikimedia {{ $t('Wikimedia') }}
			.state {{ $t('State') }}
		RecycleScroller.tbody.bunt-scrollbar(v-if="users", :items="users", :item-size="56", v-scrollbar.y="")
			template(#default="{item: user}")
				.user.table-row(
					:class="{error: user.error, updating: user.updating}",
					tabindex="0",
					role="link",
					:aria-label="userRowAriaLabel(user)",
					@click="goToUser(user)",
					@keydown.enter.self.prevent="goToUser(user)"
				)
					avatar.avatar(:user="user", :size="24")
					.id(:title="user.id") {{ user.id }}
					.tokenid(:title="user.token_id || ''") {{ user.token_id || '–' }}
					.name
						| {{ user.profile.display_name }}
						.ui-badge(v-for="badge in user.badges") {{ badge }}
					.email(:title="user.email || ''") {{ user.email || '–' }}
					.ticket-info(@click.stop="")
						template(v-if="user.order_code && eventRouting.organizer && eventRouting.event")
							a.order-link(
								:href="`/control/event/${encodeURIComponent(eventRouting.organizer)}/${encodeURIComponent(eventRouting.event)}/orders/${encodeURIComponent(user.order_code)}/`",
								target="_blank",
								rel="noopener noreferrer",
								:title="user.order_code",
								@click.stop
							) {{ user.order_code }}
							span.ticket-code(v-if="user.ticket_code", :title="user.ticket_code") {{ user.ticket_code }}
						span.ticket-code-only(v-else-if="user.ticket_code", :title="user.ticket_code") {{ user.ticket_code }}
						span.ticket-empty(v-else) –
					.wikimedia(:title="user.wikimedia_username || ''") {{ user.wikimedia_username || '–' }}
					.state {{ user.moderation_state || '–' }}
					.row-actions(v-if="user.id !== ownUser.id", @click.stop="")
						bunt-button.btn-open-dm(v-if="hasPermission('world:chat.direct') && liveFeatures.direct_messaging", @click="$store.dispatch('chat/openDirectMessage', {users: [user]})") message
						bunt-button.btn-ban(
							v-if="hasPermission('world:users.manage') && user.moderation_state !== 'banned'",
							:key="`${user.id}-ban`",
							:loading="user.updating === 'ban'",
							:error-message="(user.error && user.error.action === 'ban') ? user.error.message : null",
							tooltipPlacement="left",
							@click="doAction(user, 'ban', 'banned')")
							| ban
						bunt-button.btn-silence(
							v-if="hasPermission('world:users.manage') && !user.moderation_state",
							:key="`${user.id}-silence`",
							:loading="user.updating === 'silence'",
							:error-message="(user.error && user.error.action === 'silence') ? user.error.message : null",
							tooltipPlacement="left",
							@click="doAction(user, 'silence', 'silenced')")
							| silence
						bunt-button.btn-reactivate(
							v-if="hasPermission('world:users.manage') && user.moderation_state",
							:key="`${user.id}-reactivate`",
							:loading="user.updating === 'reactivate'",
							:error-message="(user.error && user.error.action === 'reactivate') ? user.error.message : null",
							tooltipPlacement="left",
							@click="doAction(user, 'reactivate', null)")
							| {{ user.moderation_state === 'banned' ? 'unban' : 'unsilence'}}
			template(#after)
				.load-more(v-if="!isLastPage")
					bunt-button(@click="loadUsers(page + 1)", :loading="loadingMore") {{ $t('Load more') }}
		bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import api from 'lib/api'
import Avatar from 'components/Avatar'
import debounce from 'lodash/debounce'

export default {
	name: 'AdminUsers',
	components: { Avatar },
	data() {
		return {
			users: null,
			search: '',
			page: 1,
			isLastPage: false,
			loadingMore: false,
			debouncedSearch: null,
			currentSearchRequestId: 0
		}
	},
	computed: {
		...mapState({
			ownUser: 'user',
			world: 'world'
		}),
		...mapGetters(['hasPermission', 'eventRouting']),
		liveFeatures() {
			return Object.assign({
				chat_rooms: false,
				kiosks: false,
				direct_messaging: false,
				announcements: true
			}, this.world?.live_features || window.eventyay?.liveFeatures || {})
		},
	},
	watch: {
		search() {
			this.debouncedSearch()
		}
	},
	async created() {
		this.debouncedSearch = debounce(this.doSearch, 300)
		await this.loadUsers(1)
	},
	beforeUnmount() {
		if (this.debouncedSearch) {
			this.debouncedSearch.cancel()
		}
	},
	methods: {
		async doSearch() {
			await this.loadUsers(1)
		},
		async loadUsers(page) {
			if (page === 1) {
				this.users = null
			} else {
				this.loadingMore = true
			}
			const requestId = ++this.currentSearchRequestId
			try {
				const response = await api.call('user.list.search', {
					search_term: this.search.trim(),
					page: page,
					include_banned: true
				})
				if (this.currentSearchRequestId !== requestId) return
				const results = response.results.map(user => ({
					...user,
					updating: null,
					error: null
				}))
				if (page === 1) {
					this.users = results
				} else if (this.users) {
					this.users.push(...results)
				}
				this.isLastPage = response.isLastPage
				this.page = page
			} catch (e) {
				if (this.currentSearchRequestId === requestId) {
					console.error(e)
					if (page === 1 && !this.users) {
						this.users = []
					}
				}
			} finally {
				if (this.currentSearchRequestId === requestId) {
					this.loadingMore = false
				}
			}
		},
		goToUser(user) {
			this.$router.push({ name: 'admin:user', params: { userId: user.id } })
		},
		userRowAriaLabel(user) {
			const name = user.profile?.display_name
			return name ? `User ${name}` : `User ${user.id}`
		},
		async doAction(user, action, postState) {
			user.updating = action
			user.error = null
			try {
				await api.call(`user.${action}`, {id: user.id})
				user.moderation_state = postState
			} catch (error) {
				user.error = {
					action,
					message: error?.message || this.$t('Something went wrong.'),
				}
			}
			user.updating = null
		}
	}
}
</script>
<style lang="stylus">
@import 'flex-table'

.c-admin-users
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-white
	.ui-page-header
		.search
			input-style(size: compact)
			padding: 0
			margin: 0
			flex: none
			background-color: $clr-white
	.users-list
		flex-table()
		font-size: 12px
		// flex-table uses overflow: hidden — allow horizontal scroll when needed
		overflow-x: auto
		overflow-y: hidden
		> .header, .tbody .user.table-row
			width: 100%
			min-width: 0
			max-width: 100%
			box-sizing: border-box
		> .header > *, .tbody .user.table-row > *
			padding: 3px 6px
			box-sizing: border-box
		.avatar, .id, .tokenid, .wikimedia, .state
			flex-shrink: 0
		.id, .tokenid, .wikimedia, .state, .name, .email
			overflow: hidden
			text-overflow: ellipsis
			white-space: nowrap
		> .header > *
			line-height: 1.2
			white-space: normal
			overflow: visible
			text-overflow: clip
		.header, .user.table-row
			height: auto
			min-height: 56px
			line-height: 1.2
			align-items: stretch
			> .ticket-info
				line-height: 1.15
				padding-top: 2px
				padding-bottom: 2px
				justify-content: center
				white-space: normal
				overflow: visible
				text-overflow: clip
		.tbody .table-row
			overflow: visible
			position: relative
		.user.table-row
			display: flex
			align-items: stretch
			color: $clr-primary-text-light
			cursor: pointer
			&:focus-visible
				outline: 2px solid $clr-primary
				outline-offset: 2px
			> *:not(.ticket-info)
				align-self: center
		.header
			> *:not(.ticket-info)
				align-self: center
		.avatar
			display: flex
			flex: 0 0 40px
			width: 40px
			min-width: 40px
			padding-left: 4px
			padding-right: 4px
			align-items: center
			justify-content: flex-start
			box-sizing: border-box
		.id
			flex: 0 0 56px
			width: 56px
			min-width: 56px
			max-width: 56px
		.tokenid
			flex: 0 0 108px
			width: 108px
			min-width: 108px
			max-width: 108px
		.name
			flex: 0.6 1 0
			min-width: 0
			width: 0
			max-width: 150px
		.email
			flex: 0.75 1 0
			min-width: 0
			width: 0
			max-width: 200px
		.ticket-info
			flex: 0.75 1 0
			min-width: 0
			width: 0
			max-width: 240px
			flex-shrink: 1
			overflow: hidden
			display: flex
			flex-direction: column
			align-items: flex-start
			justify-content: center
			gap: 1px
			box-sizing: border-box
			.ticket-info-head-order, .ticket-info-head-ticket
				display: block
				font-weight: 600
				color: $clr-primary-text
				font-size: 9px
				line-height: 1.1
				text-transform: uppercase
				letter-spacing: 0.02em
			.order-link
				flex: 0 1 auto
				min-width: 0
				max-width: 100%
				color: $clr-primary
				text-decoration: none
				font-size: 11px
				overflow: hidden
				text-overflow: ellipsis
				white-space: nowrap
				&:hover
					text-decoration: underline
			.ticket-code, .ticket-code-only
				color: $clr-secondary-text-light
				font-size: 10px
				font-family: ui-monospace, monospace
				max-width: 100%
				overflow: hidden
				text-overflow: ellipsis
				white-space: nowrap
			.ticket-empty
				color: $clr-secondary-text-light
		.wikimedia
			flex: 0 0 264px
			width: 264px
			min-width: 264px
			max-width: 264px
		.state
			flex: 0 0 88px
			width: 88px
			min-width: 88px
			max-width: 88px
		.row-actions
			display: none
			position: absolute
			right: 0
			top: 50%
			transform: translateY(-50%)
			align-items: center
			gap: 2px
			padding: 0 8px
			z-index: 1
			.btn-open-dm
				button-style(style: clear)
			.btn-reactivate
				button-style(style: clear, color: $clr-success, text-color: $clr-success)
			.btn-ban
				button-style(style: clear, color: $clr-danger, text-color: $clr-danger)
			.btn-silence
				button-style(style: clear, color: $clr-deep-orange, text-color: $clr-deep-orange)
		.user.table-row:hover .row-actions,
		.user.table-row:focus-within .row-actions
			display: flex
</style>
