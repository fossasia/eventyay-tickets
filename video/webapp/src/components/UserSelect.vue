<template lang="pug">
.c-user-select
	.search-bar
		bunt-input-outline-container
			.search-field(slot-scope="{focus, blur}")
				.selected-user(v-for="user of selectedUsers")
					avatar(:user="user", :size="20")
					.display-name {{ user.profile.display_name }}
					bunt-icon-button(@click="removeUser(user)") close
				input(ref="input", name="search", v-model="search", @focus="focus", @blur="blur")
		bunt-button(@click="submit") {{ buttonLabel }}
	scrollbars.search-results(y)
		.user(v-for="user of results", :class="{selected: isSelected(user)}", @click="addUser(user)")
			avatar(:user="user", :size="36")
			.display-name {{ user.profile.display_name }}
		infinite-scroll(v-if="nextPage", :loading="loading", @load="loadPage")
</template>
<script>
// USAGE
// user-select(button-label="create", @selected="doSomethingWithUserArray")

// TODO
// - delete user on backspace when input empty
// - rewrite with contenteditable?
import api from 'lib/api'
import Avatar from 'components/Avatar'
import InfiniteScroll from './InfiniteScroll'

export default {
	components: { Avatar, InfiniteScroll },
	props: {
		buttonLabel: {
			type: String,
			required: true
		}
	},
	data () {
		return {
			selectedUsers: [],
			search: '',
			results: [],
			loading: false,
			nextPage: null
		}
	},
	watch: {
		search () {
			this.results = []
			this.nextPage = 1
		}
	},
	methods: {
		async loadPage () {
			this.loading = true
			const search = this.search
			const newPage = (await api.call('user.list.search', {search_term: this.search, page: this.nextPage}))
			if (search !== this.search) return
			this.results.push(...newPage.results)
			if (newPage.isLastPage) {
				this.nextPage = null
			} else {
				this.nextPage++
			}
			this.loading = false
		},
		addUser (user) {
			if (this.isSelected(user)) return this.removeUser(user)
			this.selectedUsers.push(user)
			this.$refs.input.focus()
			this.$refs.input.select()
		},
		removeUser (user) {
			const index = this.selectedUsers.indexOf(user)
			if (index > -1) {
				this.selectedUsers.splice(index, 1)
			}
			this.$refs.input.focus()
			this.$refs.input.select()
		},
		submit () {
			this.$emit('selected', this.selectedUsers)
		},
		isSelected (user) {
			return this.selectedUsers.some(u => u.id === user.id)
		}
	}
}
</script>
<style lang="stylus">
.c-user-select
	min-height: 0
	display: flex
	flex-direction: column
	.search-bar
		margin: 8px 16px
		display: flex
		.bunt-input-outline-container
			flex: auto
			margin-right: 8px
			padding: 0
	.search-field
		flex: auto
		display: flex
		align-items: center
		flex-wrap: wrap
		padding-left: 4px
		.selected-user
			flex: none
			display: flex
			align-items: center
			padding: 4px
			margin: 4px 4px 4px 0
			background-color: var(--clr-primary)
			border-radius: 14px
			color: var(--clr-input-primary-fg)
			// font-weight: 500
			// &:first-child
			// 	margin-top: 4px
			&:nth-last-child(2)
				margin-right: 4px
			.c-avatar
				background-color: $clr-white
				border-radius: 50%
			.display-name
				margin: 0 2px 0 4px
			.bunt-icon-button
				icon-button-style(color: $clr-primary-text-dark, style: clear)
				height: 20px
				width: @height
				.mdi
					font-size: 16px
		input
			flex: auto
			border: none
			outline: none
			height: 24px
			font-family: $font-stack
			font-size: 16px
			font-weight: 400
			margin-left: -4px
			padding: 6px 8px 6px 12px
	.bunt-button
		themed-button-primary()
	.search-results
		.user
			display: flex
			align-items: center
			cursor: pointer
			padding: 2px 8px
			&:not(:last-child)
				border-bottom: border-separator()
			&:hover
				background-color: $clr-grey-100
			.c-avatar
				flex: none
				border-radius: 50%
				border: 4px solid transparent
			.display-name
				flex: auto
				margin-left: 8px
				ellipsis()
			&.selected
				.c-avatar
					border: 4px solid $clr-success
				&::after
					flex: none
					content: '\F012C'
					display: inline-block
					font: normal normal normal 24px/1 "Material Design Icons"
					color: $clr-success
					margin-right: 8px
</style>
