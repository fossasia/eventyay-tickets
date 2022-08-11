<template lang="pug">
.c-poster-hall
	template(v-if="posters")
		.list-actions
			bunt-input-outline-container#input-search
				.search-field(slot-scope="{focus, blur}")
					.icon.mdi.mdi-magnify
					.applied-filter(v-for="filter of filters", :title="filter.field + ': ' + filter.value")
						.field {{ filter.field }}:
						.value {{ filter.value }}
						bunt-icon-button(@click="removeFilter(filter)") close
					input(ref="input", name="search", v-model="search", :placeholder="$t('PosterHall:input-search:placeholder')", @focus="focus", @blur="blur", autofocus, autocomplete="off")
			menu-dropdown(v-model="showAddFilters", placement="bottom-end", @mousedown.native.stop="")
				template(v-slot:button="{toggle}")
					bunt-button(icon="filter-plus", @click="toggle") add filter
				template(v-slot:menu)
					scrollbars.not-menu-item(y)
						.filter
							label Categories
							.filter-items
								.filter-item(v-for="category of categories", :title="category.name", :class="{active: filters.some(filter => filter.field === 'category' && filter.value === category.name)}", @click="toggleFilter({field: 'category', value: category.name})")
									.name {{ category.name }}
									.count {{ category.count }}
						.filter
							label Tags
							.filter-items
								.filter-item(v-for="tag of tags", :title="tag.name", :class="{active: filters.some(filter => filter.field === 'tag' && filter.value === tag.name)}", @click="toggleFilter({field: 'tag', value: tag.name})")
									.name {{ tag.name }}
									.count {{ tag.count }}
		//- p Search by everything, filter by category, tags, ?, sort by name, likes
		RecycleScroller.posters.bunt-scrollbar(:items="flatCategorizedFilteredPosters", type-field="type", v-slot="{item: poster}", v-scrollbar.y="")
			h2.category(v-if="poster.type === 'category'") {{ poster.id }}
			router-link.poster(v-else, :to="{name: 'poster', params: {posterId: poster.id}}", :key="poster.id")
				.content
					.tags
						.tag(v-for="tag of poster.tags") {{ tag }}
					h3.title {{ poster.title }}
					.authors(v-if="poster.authors && poster.authors.authors") {{ poster.authors.authors.map(a => a.name).join(' / ') }}
					rich-text-content.abstract(:content="poster.abstract", v-dynamic-line-clamp)
					.actions
						bunt-button {{ $t('PosterHall:more:label') }}
				img.poster-screenshot(v-if="poster.poster_preview", :src="poster.poster_preview")
				.preview-placeholder(v-else)
					.mdi(:class="`mdi-${getIconByFileEnding(poster.poster_url)}`")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
// TODO
// - put categories through config key map
// - don't let filters be applied multiple times

import intersection from 'lodash/intersection'
import api from 'lib/api'
import MenuDropdown from 'components/MenuDropdown'
import RichTextContent from 'components/RichTextContent'
import { getIconByFileEnding } from 'lib/filetypes'
import { phonyMatcher } from 'lib/search'

function matchesFilter (filter, poster) {
	let field = filter.field
	if (field === 'tag') field = 'tags'
	if (Array.isArray(poster[field])) {
		return poster[field].includes(filter.value)
	} else {
		return poster[field] === filter.value
	}
}

export default {
	components: { MenuDropdown, RichTextContent },
	props: {
		room: Object
	},
	data () {
		return {
			posters: null,
			search: '',
			showAddFilters: false,
			filters: [],
			getIconByFileEnding
		}
	},
	computed: {
		posterModule () {
			return this.room.modules.find(module => module.type === 'poster.native')
		},
		categoriesLookup () {
			if (!this.posterModule.config.categories) return {}
			return this.posterModule.config.categories.reduce((acc, category) => {
				acc[category.id] = category
				return acc
			}, {})
		},
		tagsLookup () {
			if (!this.posterModule.config.tags) return {}
			return this.posterModule.config.tags.reduce((acc, tag) => {
				acc[tag.id] = tag
				return acc
			}, {})
		},
		filteredPosters () {
			const singleSearch = (searchTerm) => {
				const matchesSearch = phonyMatcher(searchTerm)
				return this.posters.filter(poster =>
					(matchesSearch(poster.title) ||
					poster.tags.some(tag => matchesSearch(tag)) ||
					poster.authors.authors.some(author => matchesSearch(author.name)))
				)
			}
			return intersection(this.posters.filter(poster => this.filters.every(filter => matchesFilter(filter, poster))), ...this.search.trim().toLowerCase().split(' ').map(singleSearch))
		},
		categorizedFilteredPosters () {
			if (!this.posterModule.config.categories) return {'': this.filteredPosters}
			// prefill configured categories to enforce order, null/'' category is first, unknown categories are at the end, by order of poster appearance
			const categorizedPosters = {
				'': []
			}

			for (const category of this.posterModule.config.categories) {
				categorizedPosters[category.id] = []
			}

			for (const poster of this.filteredPosters) {
				if (poster.category && !categorizedPosters[poster.category]) categorizedPosters[poster.category] = []
				categorizedPosters[poster.category || ''].push(poster)
			}
			// remove empty categories
			return Object.fromEntries(Object.entries(categorizedPosters).filter(([key, value]) => value.length > 0))
		},
		categories () {
			return Object.entries(this.categorizedFilteredPosters).map(([key, value]) => {
				return {
					name: key === '' ? this.$t('PosterHall:categories-filter:uncategorized') : key,
					count: value.length
				}
			}).filter(filter => filter.count).sort((a, b) => b.count - a.count)
		},
		tags () {
			const tags = {}

			for (const poster of this.filteredPosters) {
				for (const tag of poster.tags) {
					if (!tags[tag]) tags[tag] = 0
					tags[tag]++
				}
			}
			return Object.entries(tags).map(([key, value]) => {
				return {
					name: key,
					count: value
				}
			}).filter(filter => filter.count).sort((a, b) => b.count - a.count)
		},
		flatCategorizedFilteredPosters () {
			// hack categories into a flat list with posters for the virtual scroller
			const flatCategorizedFilteredPosters = []
			for (const [category, posters] of Object.entries(this.categorizedFilteredPosters)) {
				flatCategorizedFilteredPosters.push({id: category, type: 'category', size: 56})
				flatCategorizedFilteredPosters.push(...posters.map(poster => ({...poster, type: 'poster', size: 368})))
			}
			return flatCategorizedFilteredPosters
		}
	},
	async created () {
		this.posters = (await api.call('poster.list', {room: this.room.id}))
	},
	methods: {
		toggleFilter (filter) {
			const index = this.filters.findIndex(f => f.field === filter.field && f.value === filter.value)
			if (index >= 0) {
				this.filters.splice(index, 1)
			} else {
				this.filters.push(filter)
			}
		},
		removeFilter (filter) {
			this.filters = this.filters.filter(f => f !== filter)
		}
	}
}
</script>
<style lang="stylus">
$grid-size = 280px
$logo-height = 130px
$logo-height-medium = 160px
$logo-height-large = 427px

.c-poster-hall
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-grey-50
	.list-actions
		width: 100%
		max-width: 1160px
		align-self: center
		display: flex
		align-items: center
		gap: 8px
		margin: 8px 0
		#input-search
			flex: auto
			padding: 0
			.search-field
				flex: auto
				display: flex
				align-items: center
				flex-wrap: wrap
				.icon
					font-size: 22px
					color: $clr-secondary-text-light
					padding: 0 0 0 8px
				.applied-filter
					flex: none
					max-width: 180px
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
					.field
						margin: 0 4px
					.value
						font-weight: 600
						ellipsis()
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
		.not-menu-item
			display: flex
			flex-direction: column
			width: 320px
			max-height: calc(var(--vh100) - 56px * 2) // TODO add mobile header height

			.filter
				display: flex
				flex-direction: column
				cursor: pointer
				&:not(:first-child)
					margin-top: 4px
					border-top: border-separator()
				label
					color: $clr-secondary-text-light
					margin: 4px
					font-size: 16px
					line-height: 1.5
					font-weight: 600
				.filter-item
					display: flex
					gap: 8px
					padding: 4px 10px 4px 8px
					&.active
						opacity: .7
						background-color: var(--clr-input-primary-bg)
						color: var(--clr-input-primary-fg)
						.count
							color: var(--clr-input-primary-fg)
					&:hover
						background-color: var(--clr-input-primary-bg)
						color: var(--clr-input-primary-fg)
						.count
							color: var(--clr-input-primary-fg)
					.name
						flex: auto
						ellipsis()
					.count
						color: $clr-secondary-text-light
	.posters
		.category, .poster
			width: 100%
			max-width: 1160px
			margin: 0 auto
		.poster
			background-color: $clr-white
			border: border-separator()
			border-radius: 4px
			display: flex
			padding: 8px
			cursor: pointer
			height: 360px
			box-sizing: border-box
			margin-bottom: 8px
			.content
				display: flex
				flex-direction: column
				flex: 1 1 60%
				padding: 0 16px 0 0
			.tags
				display: flex
				flex-wrap: wrap
				gap: 4px
				.tag
					color: $clr-primary-text-light
					border: 2px solid $clr-primary
					border-radius: 12px
					padding: 2px 6px
			.title
				margin: 0 0 8px 0
				line-height: 1.4
			.authors
				color: $clr-secondary-text-light
			.abstract
				margin-top: 12px
				color: $clr-primary-text-light
				overflow: hidden
				.ql-editor
					display: -webkit-box
					-webkit-line-clamp: var(--dynamic-line-clamp)
					-webkit-box-orient: vertical
					overflow: hidden
					padding: 0
					height: auto

					> *
						line-height: 1.4
			.actions
				flex: auto
				display: flex
				justify-content: flex-start
				align-items: flex-end
				.bunt-button
					themed-button-secondary()
			img.poster-screenshot, .preview-placeholder
				object-fit: contain
				max-height: 360px
				min-width: 40%
				flex: 1 1 40%
			.preview-placeholder
				display: flex
				justify-content: center
				align-items: center
				background-color: $clr-grey-100
				.mdi
					color: $clr-grey-600
					font-size: 64px
			&:hover
				border: 1px solid var(--clr-primary)
			+below('s')
				flex-direction: column-reverse
				max-height: none
				.content
					padding: 16px 0 0 0
</style>
