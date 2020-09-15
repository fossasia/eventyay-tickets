<template lang="pug">
.c-userlist
	.profile(v-if="showProfile")
		bunt-progress-circular(size="huge", v-if="loading")
		template(v-else-if="selectedUser")
			.ui-page-header(v-if="$mq.below['s']")
				bunt-icon-button(@click="toggleView=!toggleView") arrow_left
				h2 {{ $t('UserSearch:placeholder:text') }}
			scrollbars.content(y)
				avatar(:user="selectedUser", :size="128")
				h1.display-name
					| {{ selectedUser.profile ? selectedUser.profile.display_name : (selectedUser.id ? selectedUser.id : '(unknown user)') }}
					.ui-badge(v-for="badge in selectedUser.badges") {{ badge }}
				.state {{ userStates.join(', ') }}
				.fields(v-if="availableFields")
					.field(v-for="field of availableFields")
						.label {{ field.label }}
						.value {{ field.value }}
				.exhibitions(v-if="exhibitors.length > 0")
					h3 {{ $t('UserListPage:staffed-exhibitions:text') }}
					.exhibitors
						router-link.exhibitor(v-for="exhibitor of exhibitors", :to="{name: 'exhibitor', params: {exhibitorId: exhibitor.id}}")
							img.logo(:src="exhibitor.banner_list ? exhibitor.banner_list : exhibitor.logo", :alt="exhibitor.name")
							.name {{ exhibitor.name }}
							.tagline {{ exhibitor.tagline }}
							.actions
								bunt-button {{ $t('Exhibition:more:label') }}
			.actions(v-if="selectedUser.id !== user.id && selectedUser.id")
				.action-row
					bunt-button.btn-dm(v-if="hasPermission('world:chat.direct')", @click="openDM") {{ $t('UserAction:action.dm:label') }}
					bunt-button.btn-call(v-if="hasPermission('world:chat.direct')", @click="startCall") {{ $t('UserAction:action.call:label') }}
					bunt-button.unblock(v-if="isBlocked", @click="userAction = 'unblock'") {{ $t('UserAction:action.unblock:label') }}
					bunt-button.block(v-else, @click="userAction = 'block'") {{ $t('UserAction:action.block:label') }}
				template(v-if="$features.enabled('chat-moderation') && hasPermission('room:chat.moderate') && selectedUser.id !== user.id")
					.devider {{ $t('UserAction:moderataor.actions.devider:text') }}
					.action-row
						bunt-button.reactivate(v-if="selectedUser.moderation_state", @click="userAction = 'reactivate'")
							| {{ selectedUser.moderation_state === 'banned' ? $t('UserAction:action.unban:label') : $t('UserAction:action.unsilence:label') }}
						bunt-button.ban(v-if="selectedUser.moderation_state !== 'banned'", @click="userAction = 'ban'") {{ $t('UserAction:action.ban:label') }}
						bunt-button.silence(v-if="!selectedUser.moderation_state", @click="userAction = 'silence'") {{ $t('UserAction:action.silence:label') }}
	UserSearch(v-if="showList", :placeholder="$t('UserSearch:placeholder:text')", @selected="selectUser").user-list
	user-action-prompt(v-if="userAction", :action="userAction", :user="selectedUser", @close="updateProfile")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import api from 'lib/api'
import Avatar from 'components/Avatar'
import UserSearch from 'components/UserSearch'
import UserActionPrompt from 'components/UserActionPrompt'

export default {
	components: { Avatar, UserSearch, UserActionPrompt },
	props: {
		room: Object,
		module: {
			type: Object,
			required: true
		}
	},
	data () {
		return {
			toggleView: false,
			loading: false,
			blockedUsers: null,
			selectedUser: null,
			userAction: null,
			moderationError: null,
			exhibitors: []
		}
	},
	computed: {
		...mapState(['user', 'world']),
		...mapGetters(['hasPermission']),
		showProfile () {
			if (!this.$mq.below.s) return true
			return this.toggleView
		},
		showList () {
			if (!this.$mq.below.s) return true
			return !this.toggleView
		},
		isBlocked () {
			if (!this.blockedUsers) return
			return this.blockedUsers.some(user => user.id === this.selectedUser.id)
		},
		availableFields () {
			if (!this.selectedUser.profile?.fields) return
			return this.world?.profile_fields
				.map(field => ({label: field.label, value: this.selectedUser.profile.fields[field.id]}))
				.filter(field => !!field.value)
		},
		userStates () {
			const states = []
			if (this.isBlocked) {
				states.push('blocked')
			}
			if (this.selectedUser.moderation_state) {
				states.push(this.selectedUser.moderation_state)
			}
			return states
		}
	},
	async created () {
		this.blockedUsers = (await api.call('user.list.blocked')).users
	},
	methods: {
		async updateProfile () {
			this.loading = true
			this.userAction = null
			this.blockedUsers = (await api.call('user.list.blocked')).users
			this.selectedUser = await api.call('user.fetch', {id: this.selectedUser.id})
			this.loading = false
		},
		async selectUser (user) {
			this.loading = true
			this.toggleView = !this.toggleView
			this.selectedUser = user
			this.exhibitors = (await api.call('exhibition.get.staffed_by_user', {user_id: user.id})).exhibitors
			this.loading = false
		},
		async openDM () {
			await this.$store.dispatch('chat/openDirectMessage', {users: [this.selectedUser]})
		},
		async startCall () {
			const channel = await this.$store.dispatch('chat/openDirectMessage', {users: [this.selectedUser]})
			await this.$store.dispatch('chat/startCall', {channel})
		}
	}
}
</script>
<style lang="stylus">
$grid-size = 280px
$logo-height-medium = 160px

.c-userlist
	flex auto
	background-color $clr-white
	display flex
	flex-direction row
	+below('s')
		flex-direction column
	.ui-page-header
		padding 0
	.user-list
		flex none
		display flex
		flex-direction column
		width 240px
		grid-area sidebar
		border-left border-separator()
		min-height 0
		height 100%
		+below('s')
			width 100%
			grid-area unset
			border-left none
	.profile
		flex auto
		display flex
		flex-direction column
		min-height 0
		max-height 100%
		.content
			display flex
			padding 16px 0px 0px 32px
			h1
				margin 0
				.display-name
					margin auto 8px
					flex auto
					ellipsis()
			.fields
				display flex
				flex-direction column
				align-self stretch
				margin 0 8px
				.field
					display flex
					flex-direction column
					margin 4px
					.label
						color $clr-secondary-text-light
						font-weight 500
						font-size 12px
					.value
						margin 2px 0 0 8px
			.state
				height 16px
				margin-bottom 8px
			.exhibitors
				flex auto
				display grid
				grid-template-columns repeat(auto-fill, $grid-size)
				grid-auto-rows $grid-size
				gap 16px
				padding 16px
				justify-content center
				.exhibitor
					grid-area: span 1 / span 2
					background-color $clr-white
					border border-separator()
					border-radius 4px
					display flex
					flex-direction column
					padding 8px
					margin 16px
					cursor pointer
					&:hover
						border 1px solid var(--clr-primary)
					img.logo
						height: $logo-height-medium
						min-height: $logo-height-medium
						margin: 0
						object-fit contain
						max-width 100%
					.actions
						flex auto
						display flex
						justify-content flex-end
						align-items flex-end
						.bunt-button
							themed-button-secondary()
		.actions
			margin-top auto
			border-top border-separator()
			padding-left 32px
			.action-row
				margin 8px 0px 8px 0px
				display flex
				align-self stretch
				justify-content flex-start
				.bunt-button
					button-style(style: clear)
				.bunt-icon-button
					icon-button-style(style: clear)
			.devider
				color $clr-secondary-text-light
				font-weight 500
				font-size 12px
				margin 0px 8px

</style>
