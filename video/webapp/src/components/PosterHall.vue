<template lang="pug">
.c-poster-hall
	bunt-input#input-search(name="search", placeholder="Search posters", icon="search", v-model="search")
	//- p Search by everything, filter by category, tags, ?, sort by name, likes
	scrollbars.posters(v-if="posters", y)
		.category(v-for="(posters, category) of categorizedFilteredPosters")
			h2 {{ category }}
			router-link.poster(v-for="poster of posters", :to="{name: 'poster', params: {posterId: poster.id}}")
				.content
					.tags
						.tag(v-for="tag of poster.tags") {{ tag }}
					h3.title {{ poster.title }}
					.authors {{ poster.authors.authors.map(a => a.name).join(' / ') }}
					rich-text-content.abstract(:content="poster.abstract")
					.actions
						bunt-button {{ $t('Exhibition:more:label') }}
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
			return this.posterModule.config.categories.reduce((acc, category) => {
				acc[category.id] = category
				return acc
			}, {})
		},
		tagsLookup () {
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
			if (!this.posterModule.config.categories) return this.filteredPosters
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
	#input-search, p
		width: 100%
		max-width: 1160px
		align-self: center
	.posters .scroll-content
		display: flex
		flex-direction: column
		gap: 8px
		padding: 8px
		align-items: center
	.category
		display: flex
		flex-direction: column
		gap: 16px
		width: 100%
		max-width: 1160px
	.poster
		background-color: $clr-white
		border: border-separator()
		border-radius: 4px
		display: flex
		padding: 8px
		cursor: pointer
		max-height: 360px
		box-sizing: border-box
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
			display: -webkit-box
			-webkit-line-clamp: 7
			-webkit-box-orient: vertical
			overflow: hidden
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
