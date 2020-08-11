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
			.contact
				bunt-button(@click="contact", :tooltip="$t('Exhibition:contact-button:tooltip')") {{ $t('Exhibition:contact-button:label') }}
			.staff
				h3 Unser Standpersonal
				<div class="user"><div class="c-avatar" style="--avatar-size:28px;"><div class="c-identicon"><svg viewBox="0 0 2.8284271247461903 2.8284271247461903"><g transform="translate(0.125 1.4142135623730951) scale(.9 .9) rotate(-45 0 0)"><g transform="translate(1 0)" class="shape square"><path d="M 0 0 L 0 1 L 1 1 L 1 0z" transform="scale(0.5, 0.5) translate(0.75, 0.2)" style="fill: rgb(0, 188, 212);"></path></g><g transform="translate(0 0)" class="block"><path d="M 0 0 L 1 0 L 0 1" style="fill: rgb(103, 58, 183);"></path><path d="M 0 0 L 1 0 L 0 1" style="fill: rgb(0, 188, 212);"></path><path d="M 0 0 L 0 1 L 1 1 L 1 0z" class="stroke"></path></g><g transform="translate(0 1)" class="block"><path d="M 0 0 L 0 1 L 1 1" style="fill: rgb(0, 188, 212);"></path><path d="M 0 0 L 1 0 L 0 1" style="fill: rgb(103, 58, 183);"></path><path d="M 0 0 L 0 1 L 1 1 L 1 0z" class="stroke"></path></g><g transform="translate(1 1)" class="block"><path d="M 0 0 L 1 0 L 0 1" style="fill: rgb(0, 188, 212);"></path><path d="M 0 0 L 0 1 L 1 1" style="fill: rgb(103, 58, 183);"></path><path d="M 0 0 L 0 1 L 1 1 L 1 0z" class="stroke"></path></g></g></svg></div></div><span class="display-name">Max Muster</span></div>
				<div class="user"><div class="c-avatar" style="--avatar-size:28px;"><div class="c-identicon"><svg viewBox="0 0 2.8284271247461903 2.8284271247461903"><g transform="translate(0.125 1.4142135623730951) scale(.9 .9) rotate(-45 0 0)"><g transform="translate(1 0)" class="shape square"><path d="M 0 0 L 0 1 L 1 1 L 1 0z" transform="scale(0.5, 0.5) translate(0.75, 0.2)" style="fill: rgb(233, 30, 99);"></path></g><g transform="translate(0 0)" class="block"><path d="M 0 0 L 1 0 L 0 1" style="fill: rgb(255, 87, 34);"></path><path d="M 0 0 L 1 0 L 0 1" style="fill: rgb(233, 30, 99);"></path><path d="M 0 0 L 0 1 L 1 1 L 1 0z" class="stroke"></path></g><g transform="translate(0 1)" class="block"><path d="M 0 0 L 0 1 L 1 1" style="fill: rgb(233, 30, 99);"></path><path d="M 0 0 L 1 0 L 0 1" style="fill: rgb(255, 87, 34);"></path><path d="M 0 0 L 0 1 L 1 1 L 1 0z" class="stroke"></path></g><g transform="translate(1 1)" class="block"><path d="M 0 0 L 1 0 L 0 1" style="fill: rgb(233, 30, 99);"></path><path d="M 0 0 L 0 1 L 1 1" style="fill: rgb(255, 87, 34);"></path><path d="M 0 0 L 0 1 L 1 1 L 1 0z" class="stroke"></path></g></g></svg></div></div><span class="display-name">Maria Müller</span></div>

	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapState } from 'vuex'
import api from 'lib/api'
import MarkdownContent from 'components/MarkdownContent'

export default {
	components: { MarkdownContent },
	props: {
		exhibitorId: String,
		roomId: String
	},
	data () {
		return {
			exhibitor: null
		}
	},
	async created () {
		this.exhibitor = (await api.call('exhibition.get', {exhibitor: this.exhibitorId})).exhibitor
	},
	computed: {
		...mapState(['user']),
	},
	methods: {
		prettifyUrl (link) {
			const url = new URL(link)
			return url.hostname + (url.pathname !== '/' ? url.pathname : '')
		},
		async contact () {
			this.$store.dispatch('contact', {exhibitorId: this.exhibitorId})
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
				cursor: pointer
				padding: 2px 16px 2px 0
				&:hover
					background-color: $clr-grey-100
				.display-name
					font-weight: 600
					color: $clr-secondary-text-light
					margin-left: 8px
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
