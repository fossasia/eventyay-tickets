<template lang="pug">
.c-user-search
	.combobox
		input.combobox__input.bunt-input(type="search", name="search", :placeholder="placeholder", autocomplete="off", v-model="search", @focus="showDropdown=true", @keyup.enter.prevent="select(selectedIndex)", @keydown.down.prevent="selectNext()", @keydown.up.prevent="selectPrev()", @keyup.8="handleBackspace()", @keydown.esc.prevent="showDropdown=false")
		ul.list(v-if="showDropdown", v-scrollbar.y="")
			li.list__item(v-for="(user, index) in list", @click="select(index)", :class="{'selected': index == selectedIndex}")
				avatar(:user="user", :size="26")
				span.display-name
					| {{ user ? user.profile.display_name : '' }}
					span.ui-badge(v-for="badge in user.badges") {{ badge }}
			li(v-if="!lastPage")
				bunt-progress-circular(v-if="loading", size="small")
				bunt-button#btn-more(v-else, @click="page++") Load more
</template>
<script>
import api from 'lib/api'
import Avatar from 'components/Avatar'

export default {
	components: { Avatar },
	props: {
		placeholder: String
	},
	data () {
		return {
			search: '',
			loading: false,
			page: 1,
			list: [],
			showDropdown: false,
			selectedIndex: 0,
			user: null,
			lastPage: false
		}
	},
	watch: {
		page: async function () {
			this.loading = true
			const newPage = (await api.call('user.list.search', {search_term: this.search, page: this.page}))
			this.lastPage = newPage.isLastPage
			this.list.push(...newPage.results)
			this.loading = false
		},
		search: async function () {
			await this.updateList()
		}
	},
	async created () {
		this.loading = true
		this.list = (await api.call('user.list.search', {search_term: this.search, page: this.page})).results
		this.loading = false
	},
	methods: {
		updateList: async function () {
			this.loading = true
			this.page = 1
			this.list = (await api.call('user.list.search', {search_term: this.search, page: this.page})).results
			this.loading = false
		},
		handleBackspace: function () {
			this.showDropdown = true
		},
		select: function (index) {
			this.showDropdown = false
			this.user = this.list[index]
			this.search = this.user ? this.user.profile.display_name : ''
			this.$emit('select', this.user)
		},
		selectNext: function () {
			if (this.showDropdown) {
				if (this.selectedIndex < this.list.length - 1) {
					if (this.selectedIndex === this.list.length - 2) { this.page++ }
					this.selectedIndex++
				} else {
					this.selectedIndex = 0
				}
			} else {
				this.showDropdown = true
			}
		},
		selectPrev: function () {
			if (this.selectedIndex > 0) {
				this.selectedIndex--
			} else {
				this.selectedIndex = this.list.length - 1
			}
		}
	}
}
</script>
<style lang="stylus">
.c-user-search
	position: relative
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-white
	.combobox__input
		select-style()
		font-size: 16px
		padding: 4px
		height: 36px
		width: 100%
	.list
		card()
		position: absolute
		width: 100%
		margin: 0
		padding: 0
		max-height: 300px
		.list__item
			margin: 0
			list-style-type: none
			display: flex
			cursor: pointer
			.display-name
				margin: auto 8px
				flex: auto
				ellipsis()
		#btn-more
			width: 100%
		.list__item:hover
			background-color: $clr-grey-50
		.selected
			background-color: $clr-grey-100
</style>
