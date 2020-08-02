<template lang="pug">
scrollbars.c-exhibitor(y)
	.content-wrapper(v-if="exhibitor")
		.content
			//- TODO banner
			markdown-content.text(:markdown="exhibitor.text")
		.sidebar
			.header
				img.logo(:src="exhibitor.logo")
				.heading
					h2.name {{ exhibitor.name }}
					h3.tagline {{ exhibitor.tagline }}
			.social-media-links
				a.mdi(v-for="link in exhibitor.social_media_links", :class="`mdi-${link.display_text.toLowerCase()}`", :href="link.url", :title="link.display_text", target="_blank")
			table.external-links
				tr(v-for="link in exhibitor.links")
					th.name {{ link.display_text }}
					td: a(:href="link.url", target="_blank") {{ link.url }}
			.contact
				bunt-button(@click="contact", :tooltip="$t('Exhibition:contact-button:tooltip')") {{ $t('Exhibition:contact-button:label') }}
			.staff
				h2 TODO STAFF

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
	background-color: $clr-white
	.content-wrapper
		display: flex
		justify-content: center
		padding: 8px
	.content
		display: flex
		flex-direction: column
		width: 100%
		max-width: 720px
		padding: 0 16px 0 0
	.sidebar
		flex: none
		min-height: min-content
		display: flex
		flex-direction: column
		width: 320px
		border: border-separator()
		border-radius: 4px
		margin-top: 16px
		.header
			flex: none
			display: flex
			flex-direction: column
			border-bottom: border-separator()
			padding: 8px
			img.logo
				object-fit: contain
				width: 100%
				height: 160px
				max-height: 160px
			.heading
				display: flex
				width: 100%
				flex-direction: column
				.name
					margin: 16px 0 8px 0
				.tagline
					margin: 0
		.social-media-links
			flex: none
			display: flex
			border-bottom: border-separator()
			padding: 4px 16px
			justify-content: center
			a
				font-size: 36px
				line-height: @font-size
		.external-links
			flex: none
			border-bottom: border-separator()
			tr
				height: 24px
			th
				font-weight: 400
				text-align: right
			td
				overflow: hidden
				white-space: nowrap
				text-overflow: ellipsis
				max-width: 0
				width: 100%
			.name
				white-space: nowrap
		.contact
			flex: none
			padding: 8px
			display: flex
			flex-direction: column
			.bunt-button
				themed-button-primary()
</style>
