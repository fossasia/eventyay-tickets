<template lang="pug">
scrollbars.c-exhibitor(y)
	.content-wrapper(v-if="exhibitor")
		.content
			//- TODO banner
			img.banner(src="/sponsors/venueless-stage.png")
			markdown-content.text(:markdown="exhibitor.text")
			.downloads
				h2 Downloads
				a.download(href="#")
					.mdi.mdi-file-pdf-outline
					.filename Broschüre „Übersicht offene Stellen“
				a.download(href="#")
					.mdi.mdi-file-pdf-outline
					.filename Broschüre „Unsere Produktpalette“
				a.download(href="#")
					.mdi.mdi-file-powerpoint-outline
					.filename Vortragsfolien „Zukunft im Wandel“
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
					td: a(:href="link.url", target="_blank") {{ prettifyUrl(link.url) }}
			div(v-if="exhibitor.staff.length > 0")
				.contact
					bunt-button(@click="contact", :tooltip="$t('Exhibition:contact-button:tooltip')") {{ $t('Exhibition:contact-button:label') }}
				.staff
					h3 Unser Standpersonal
					.user(v-for="user in exhibitor.staff")
						avatar(:user="user", :size="28")
						span.display-name {{ user ? user.profile.display_name : '' }}
						bunt-icon-button(v-if="hasPermission('world:rooms.create.exhibition')", @click.prevent.stop="removeStaff(user)") close

	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import api from 'lib/api'
import MarkdownContent from 'components/MarkdownContent'
import Avatar from 'components/Avatar'

export default {
	components: { MarkdownContent, Avatar },
	props: {
		exhibitorId: String
	},
	data () {
		return {
			exhibitor: null,
		}
	},
	async created () {
		this.exhibitor = (await api.call('exhibition.get', {exhibitor: this.exhibitorId})).exhibitor
	},
	computed: {
		...mapState(['user']),
		...mapGetters(['hasPermission']),
	},
	methods: {
		prettifyUrl (link) {
			const url = new URL(link)
			return url.hostname + (url.pathname !== '/' ? url.pathname : '')
		},
		async contact () {
			this.$store.dispatch('exhibition/contact', {exhibitorId: this.exhibitorId})
		},
		async removeStaff (user) {
			await api.call('exhibition.remove_staff', {user: user.id, exhibitor: this.exhibitor.id})
			this.exhibitor = (await api.call('exhibition.get', {exhibitor: this.exhibitorId})).exhibitor
		}
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
		.staff
			padding: 8px
			h3
				margin: 0
			.user
				display: flex
				align-items: center
				padding: 2px 0px 2px 0
				min-height: 36px
				.display-name
					font-weight: 600
					color: $clr-secondary-text-light
					margin-left: 8px
					flex: 1
				.bunt-icon-button
					icon-button-style(style: clear)
				&:not(:hover) .bunt-icon-button
					display: none
				&:hover
					background-color: $clr-grey-100
		.contact
			flex: none
			padding: 8px
			display: flex
			flex-direction: column
			border-bottom: border-separator()
			.bunt-button
				themed-button-primary()
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
</style>
