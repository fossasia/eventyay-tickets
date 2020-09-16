<template lang="pug">
scrollbars.c-exhibitor(y)
	.content-wrapper(v-if="exhibitor")
		.content
			img.banner(:src="exhibitor.banner_detail", v-if="exhibitor.banner_detail && !bannerIsVideo")
			.iframe-banner(v-else-if="exhibitor.banner_detail && bannerIsVideo")
				iframe(:src="bannerVideoSource", allowfullscreen, allow="fullscreen")
			markdown-content.text(:markdown="exhibitor.text")
			.downloads(v-if="downloadLinks.length > 0")
				h2 {{ $t("Exhibitor:downloads-headline:text") }}
				a.download(v-for="link in downloadLinks", :href="link.url", target="_blank")
					.mdi.mdi-file-pdf-outline(v-if="link.url.toLowerCase().endsWith('pdf')")
					.mdi.mdi-file-excel-outline(v-else-if="link.url.toLowerCase().endsWith('xlsx') || link.url.toLowerCase().endsWith('xls')")
					.mdi.mdi-file-word-outline(v-else-if="link.url.toLowerCase().endsWith('docx') || link.url.toLowerCase().endsWith('doc')")
					.mdi.mdi-file-powerpoint-outline(v-else-if="link.url.toLowerCase().endsWith('pptx') || link.url.toLowerCase().endsWith('ppt')")
					.mdi.mdi-file-image-outline(v-else-if="link.url.toLowerCase().endsWith('jpg') || link.url.toLowerCase().endsWith('jpeg') || link.url.toLowerCase().endsWith('png') || link.url.toLowerCase().endsWith('tiff')")
					.mdi.mdi-file-video-outline(v-else-if="link.url.toLowerCase().endsWith('mp4') || link.url.toLowerCase().endsWith('mov') || link.url.toLowerCase().endsWith('webm') || link.url.toLowerCase().endsWith('avi')")
					.mdi.mdi-file-download-outline(v-else)
					.filename {{ link.display_text }}
		.sidebar
			.header
				img.logo(:src="exhibitor.logo", v-if="exhibitor.logo")
				.heading
					h2.name {{ exhibitor.name }}
					h3.tagline(v-if="exhibitor.tagline") {{ exhibitor.tagline }}
			.social-media-links(v-if="exhibitor.social_media_links.length > 0")
				a.mdi(v-for="link in exhibitor.social_media_links", :class="`mdi-${link.display_text.toLowerCase()}`", :href="link.url", :title="link.display_text", target="_blank")
			table.external-links(v-if="profileLinks.length > 0")
				tr(v-for="link in profileLinks")
					th.name {{ link.display_text }}
					td: a(:href="link.url", target="_blank") {{ prettifyUrl(link.url) }}
			template(v-if="exhibitor.staff.length > 0")
				.contact(v-if="hasPermission('world:exhibition.contact') && exhibitor.contact_enabled")
					bunt-button(@click="showContactPrompt = true", :tooltip="$t('Exhibition:contact-button:tooltip')") {{ $t('Exhibition:contact-button:label') }}
				.staff
					h3 {{ $t("Exhibitor:staff-headline:text") }}
					.user(v-for="user in exhibitor.staff")
						avatar(:user="user", :size="36")
						span.display-name {{ user ? user.profile.display_name : '' }}

	bunt-progress-circular(v-else, size="huge", :page="true")
	transition(name="prompt")
		contact-exhibitor-prompt(v-if="showContactPrompt", @close="showContactPrompt = false", :exhibitor="exhibitor")
</template>
<script>
// TODO
// - user action for staff list?
import { mapState, mapGetters } from 'vuex'
import api from 'lib/api'
import Avatar from 'components/Avatar'
import ContactExhibitorPrompt from 'components/ContactExhibitorPrompt'
import MarkdownContent from 'components/MarkdownContent'

export default {
	components: { Avatar, ContactExhibitorPrompt, MarkdownContent },
	props: {
		exhibitorId: String
	},
	data () {
		return {
			exhibitor: null,
			showContactPrompt: false
		}
	},
	computed: {
		...mapState(['user']),
		...mapGetters(['hasPermission']),
		bannerIsVideo () {
			return this.exhibitor.banner_detail && this.exhibitor.banner_detail.match('^https?://(www.)?youtube.com/watch\\?v=(.*)$')
		},
		bannerVideoSource () {
			const ytMatch = this.exhibitor.banner_detail.match('^https?://(www.)?youtube.com/watch\\?v=(.*)$')
			if (ytMatch) {
				return 'https://www.youtube-nocookie.com/embed/' + ytMatch[2]
			}
			return this.exhibitor.banner_detail
		},
		profileLinks () {
			return this.exhibitor.links.filter((l) => (l.category === 'profile'))
		},
		downloadLinks () {
			return this.exhibitor.links.filter((l) => (l.category === 'download'))
		}
	},
	async created () {
		this.exhibitor = (await api.call('exhibition.get', {exhibitor: this.exhibitorId})).exhibitor
	},
	methods: {
		prettifyUrl (link) {
			const url = new URL(link)
			return url.hostname + (url.pathname !== '/' ? url.pathname : '')
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
		> .content
			display: flex
			flex-direction: column
			width: 100%
			max-width: 720px
			padding: 0 16px 0 0
			.iframe-banner
				padding-top: 56.25%
				position: relative
				height: 0
				overflow: hidden
				margin-top: 16px
				iframe
					position: absolute
					top: 0
					left: 0
					width: 100%
					height: 100%
					border: 0
			img.banner
				object-fit: contain
				width: 100%
				margin-top: 16px
	.markdown-content img
		max-width: 100%
	.sidebar
		flex: none
		min-height: min-content
		display: flex
		flex-direction: column
		width: 360px
		border: border-separator()
		border-radius: 4px
		margin-top: 16px
		align-self: flex-start
		.header
			flex: none
			display: flex
			flex-direction: column
			border-bottom: border-separator()
			padding: 8px
			img.logo
				object-fit: contain
				width: 100%
				height: 344px
				max-height: 344px
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
			a:hover
					text-decoration: underline
		.contact
			flex: none
			padding: 8px
			display: flex
			flex-direction: column
			border-bottom: border-separator()
			.bunt-button
				themed-button-primary()
		.staff
			padding: 8px
			h3
				margin: 0
			.user
				display: flex
				align-items: center
				min-height: 48px
				.display-name
					margin-left: 8px
					flex: auto
					ellipsis()
				.bunt-icon-button
					icon-button-style(style: clear)
				&:not(:hover) .bunt-icon-button
					display: none
	.downloads
		border: border-separator()
		border-radius: 4px
		display: flex
		flex-direction: column
		margin-top: 16px
		h2
			margin: 4px 8px
		.download
			display: flex
			align-items: center
			height: 56px
			font-weight: 600
			font-size: 16px
			border-top: border-separator()
			&:hover
				background-color: $clr-grey-100
				text-decoration: underline
			.mdi
				font-size: 36px
				margin: 0 4px
	+below('m')
		.content-wrapper
			flex-direction: column-reverse
			> .content
				max-width: none
				padding: 16px 0
		.sidebar
			width: auto
</style>
