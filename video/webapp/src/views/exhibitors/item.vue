<template lang="pug">
.c-exhibitor
	.exhibitor(v-if="exhibitor")
		.header
			img.logo(:src="exhibitor.logo" height="150" width="150")
			.heading
				.name {{ exhibitor.name }}
				.tagline {{ exhibitor.tagline }}
		.content(v-scrollbar.y="")
			.div
				.text(v-html="markdownContent")
				.sm-links
					a.link.bunt-button(v-for="link in exhibitor.social_media_links")(:href="link.url", target="_blank") {{ link.display_text }}
				.links
					a.link.bunt-button(v-for="link in exhibitor.links")(:href="link.url", target="_blank") {{ link.display_text }}
		.contact
			bunt-button(@click="contact", :tooltip="$t('Exhibition:contact-button:tooltip')") {{ $t('Exhibition:contact-button:label') }}
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import api from 'lib/api'
import MarkdownIt from 'markdown-it'
import sanitizeHtml from 'sanitize-html'

const markdownIt = MarkdownIt({
	breaks: true,
	html: true,
})

export default {
	props: {
		exhibitorId: String
	},
	data () {
		return {
			exhibitor: null
		}
	},
	computed: {
		markdownContent () {
			if (!this.exhibitor.text) return
			return sanitizeHtml(markdownIt.render(this.exhibitor.text), {
				transformTags: {
					a: sanitizeHtml.simpleTransform('a', {target: '_blank'}),
				},
				allowedTags: sanitizeHtml.defaults.allowedTags.concat(['img', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
			})
		}
	},
	async created () {
		this.exhibitor = (await api.call('exhibition.get', {exhibitor: this.exhibitorId})).exhibitor
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		contact () {
			return // TODO: issue chat request
		},
	}
}
</script>
<style lang="stylus">
.c-exhibitor
	display: flex
	.exhibitor
		display: flex
		flex-direction: column
		width: 100%
	.header
		flex: none
		display: flex
		border-bottom: border-separator()
		padding: 16px
		.heading
			display: flex
			width: 100%
			flex-direction: column
			.name
				display: flex
				font-size: 1.8rem
				text-rendering: optimizelegibility
				font-weight: bold
				padding: 0.83rem
			.tagline
				display: flex
				font-size: 1.2rem
				text-rendering: optimizelegibility
				font-weight: bold
				padding: 0.83rem
	.content
		flex: 1
		flex-basis: 10px
		padding: 16px
		.links
			display: flex
			flex-direction: row
			margin-top: 8px
			.bunt-button
				themed-button-secondary()
		.sm-links
			display: flex
			flex-direction: row
			margin-top: 8px
			.bunt-button
				themed-button-primary()
	.contact
		flex: none
		border-top: border-separator()
		min-height: 56px
		padding: 8px 0
		box-sizing: border-box
		display: flex
		justify-content: center
		align-items: center
		.bunt-button
			themed-button-primary()
			width: calc(100% - 16px)
</style>
