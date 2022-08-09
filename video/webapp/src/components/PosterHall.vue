<template lang="pug">
.c-poster-hall
	bunt-input#input-search(name="search", :placeholder="$t('PosterHall:input-search:placeholder')", icon="search", v-model="search")
	//- p Search by everything, filter by category, tags, ?, sort by name, likes
	RecycleScroller.posters.bunt-scrollbar(v-if="posters", :items="flatCategorizedFilteredPosters", type-field="type", v-slot="{item: poster}", v-scrollbar.y="")
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
import union from 'lodash/union'
import api from 'lib/api'
import RichTextContent from 'components/RichTextContent'
import { getIconByFileEnding } from 'lib/filetypes'
import { phonyMatcher } from 'lib/search'

export default {
	components: { RichTextContent },
	props: {
		room: Object
	},
	data () {
		return {
			posters: null,
			search: '',
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
					matchesSearch(poster.title) ||
					poster.tags.some(tag => matchesSearch(tag)) ||
					poster.authors.authors.some(author => matchesSearch(author.name))
				)
			}
			return union(...this.search.trim().toLowerCase().split(' ').map(singleSearch))
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
	#input-search
		width: 100%
		max-width: 1160px
		align-self: center
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
