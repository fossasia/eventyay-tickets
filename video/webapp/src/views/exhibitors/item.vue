<template lang="pug">
.c-exhibitor
	template(v-if="exhibitor")
		.header
			img.logo(:src="exhibitor.logo")
			.heading
				.name {{ exhibitor.name }}
				.tagline {{ exhibitor.tagline }}
		scrollbars.content(y)
			markdown-content.text(:markdown="exhibitor.text")
			.sm-links
				a.link.bunt-button(v-for="link in exhibitor.social_media_links", :href="link.url", target="_blank") {{ link.display_text }}
			.links
				a.link.bunt-button(v-for="link in exhibitor.links", :href="link.url", target="_blank") {{ link.display_text }}
		.contact
			bunt-button(@click="contact", :tooltip="$t('Exhibition:contact-button:tooltip')") {{ $t('Exhibition:contact-button:label') }}
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import api from 'lib/api'
import MarkdownContent from 'components/MarkdownContent'

export default {
	components: { MarkdownContent },
	props: {
		exhibitorId: String
	},
	data () {
		return {
			exhibitor: null
		}
	},
	async created () {
		this.exhibitor = (await api.call('exhibition.get', {exhibitor: this.exhibitorId})).exhibitor
	},
	methods: {
		contact () {
			// TODO: issue chat request
		},
	}
}
</script>
<style lang="stylus">
.c-exhibitor
	flex: auto
	display: flex
	flex-direction: column
	.header
		flex: none
		display: flex
		border-bottom: border-separator()
		padding: 16px
		img.logo
			object-fit: contain
			height: 130px
			max-height: 130px
			max-width: 360px
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
