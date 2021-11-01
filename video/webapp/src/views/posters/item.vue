<template lang="pug">
.v-poster
	template(v-if="poster")
		bunt-tabs(v-if="$mq.below['1200px']", :active-tab="activeTab")
			bunt-tab(id="info", header="Info", @selected="activeTab = 'info'")
			bunt-tab(id="poster", header="Poster", @selected="activeTab = 'poster'")
			bunt-tab(id="chat", header="Presentation", @selected="activeTab = 'chat'")
		.info-sidebar(v-if="$mq.above['1200px'] || activeTab === 'info'")
			scrollbars(y)
				.info
					h2.category(v-if="poster.category") {{ poster.category }}
					.tags
						.tag(v-for="tag of poster.tags") {{ tag }}
					h1.title {{ poster.title }}
					.authors
						.author(v-for="author of poster.authors.authors")
							.name {{ author.name }}
							.orgs {{ author.orgs.map(org => org + 1).join(',') }}
					.organizations
						.organization(v-for="(organziation, index) of poster.authors.organizations")
							.index {{ index + 1 }}
							.name {{ organziation }}
					rich-text-content.abstract(:content="poster.abstract")
					.downloads(v-if="poster.links.length > 0")
						h3 {{ $t("Exhibitor:downloads-headline:text") }}
						a.download(v-for="file in poster.links", :href="file.url", target="_blank")
							.mdi.mdi-file-pdf-outline(v-if="file.url.toLowerCase().endsWith('pdf')")
							.filename {{ file.display_text }}
		template(v-if="$mq.above['1200px'] || activeTab === 'poster'")
			a.poster.no-pdf(v-if="pdfLoadFailed", :href="poster.poster_url", target="_blank", title="Download poster")
				.mdi(:class="`mdi-${getIconByFileEnding(poster.poster_url)}`")
				p Download Poster
			a.poster(v-else, v-scrollbar.x.y="", :href="poster.poster_url", target="_blank", title="Download poster")
				canvas(ref="pdfCanvas")
		.chat-sidebar(v-if="$mq.above['1200px'] || activeTab === 'chat'")
			bunt-button.btn-likes(tooltip="like this poster", @click="like")
				.mdi(:class="poster.has_voted ? 'mdi-heart' : 'mdi-heart-outline'")
				.count {{ poster.votes }}
			.presentation(v-if="presentationRoom")
				h2 Presentation
				p presented in:
				router-link.room(:to="{name: 'room', params: {roomId: presentationRoom.id}}") {{ presentationRoom.name }}
				router-link.session(v-if="session", :to="{name: 'schedule:talk', params: {talkId: session.id}}")
					.title {{ session.title }}
					.date {{ session.start.format('dddd DD. MMMM LT') }} - {{ session.end.isSame(session.start, 'day') ? session.end.format('LT') : session.end.format('dddd DD. MMMM LT') }}
				p presented by:
				.presenters
					.presenter(v-for="user in poster.presenters", @click="showUserCard($event, user)")
						avatar(:user="user", :size="36")
						span.display-name {{ user ? user.profile.display_name : '' }}
			//- h3 Discuss
			//- chat(mode="compact", :module="{channel_id: poster.channel}")
	bunt-progress-circular(v-else, size="huge", :page="true")
	chat-user-card(v-if="selectedUser", ref="avatarCard", :sender="selectedUser", @close="selectedUser = null")
</template>
<script>
import * as pdfjs from 'pdfjs-dist/webpack'
import { createPopper } from '@popperjs/core'
import api from 'lib/api'
import { getIconByFileEnding } from 'lib/filetypes'
import Avatar from 'components/Avatar'
import Chat from 'components/Chat'
import ChatUserCard from 'components/ChatUserCard'
import RichTextContent from 'components/RichTextContent'

export default {
	components: { Avatar, Chat, ChatUserCard, RichTextContent },
	props: {
		posterId: String
	},
	data () {
		return {
			poster: null,
			pdfLoadFailed: false,
			activeTab: 'info',
			selectedUser: null,
			getIconByFileEnding
		}
	},
	computed: {
		presentationRoom () {
			if (!this.poster?.presentation_room_id) return
			return this.$store.state.rooms.find(room => room.id === this.poster.presentation_room_id)
		},
		session () {
			if (!this.poster?.schedule_session || !this.$store.getters['schedule/sessions']) return
			return this.$store.getters['schedule/sessions'].find(session => session.id === this.poster.schedule_session)
		}
	},
	watch: {
		async activeTab () {
			if (this.activeTab === 'poster') {
				await this.$nextTick()
				this.renderPdf()
			}
		}
	},
	async created () {
		this.poster = await api.call('poster.get', {poster: this.posterId})
		this.renderPdf()
	},
	methods: {
		async renderPdf () {
			this.pdfLoadFailed = false
			await this.$nextTick()
			try {
				const canvas = this.$refs.pdfCanvas
				const canvasRect = canvas.getBoundingClientRect()
				const pdf = await pdfjs.getDocument(this.poster.poster_url).promise
				const page = await pdf.getPage(1)
				const unscaledViewport = page.getViewport({scale: 1})
				const viewport = page.getViewport({scale: canvasRect.width / unscaledViewport.width})
				canvas.height = viewport.height
				canvas.width = viewport.width
				await page.render({
					canvasContext: canvas.getContext('2d'),
					viewport
				}).promise
			} catch (error) {
				console.error(error)
				this.pdfLoadFailed = true
			}
		},
		async like () {
			// TODO error handling
			if (this.poster.has_voted) {
				await api.call('poster.unvote', {poster: this.poster.id})
				this.poster.votes--
				this.poster.has_voted = false
			} else {
				await api.call('poster.vote', {poster: this.poster.id})
				this.poster.votes++
				this.poster.has_voted = true
			}
		},
		async showUserCard (event, user) {
			this.selectedUser = user
			await this.$nextTick()
			const target = event.target.closest('.presenter')
			createPopper(target, this.$refs.avatarCard.$refs.card, {
				placement: 'left-start',
				modifiers: [{
					name: 'flip',
					options: {
						flipVariations: false
					}
				}]
			})
		}
	}
}
</script>
<style lang="stylus">
.v-poster
	display: flex
	min-height: 0
	min-width: 0
	flex: auto
	.info-sidebar
		display: flex
		flex-direction: column
		min-height: 0
		width: 380px
		flex: none
		border-right: border-separator()
		.info
			display: flex
			flex-direction: column
			padding: 8px
		.category
			font-size: 20px
		.title
			font-size: 18px
		.authors
			color: $clr-secondary-text-light
			.author
				display: inline
				.name
					display: inline
				.orgs
					display: inline
					font-size: 10px
					vertical-align: super
				&:not(:last-child)::after
					content: ' / '
		.organizations
			color: $clr-disabled-text-light
			font-size: 12px
			.organization
				.name, .index
					display: inline
				.index
					vertical-align: super
					margin-right: 2px
	.content
		flex: auto
		display: flex
		min-height: 0
		> .c-scrollbars
			align-items: center
			.scroll-content
				max-width: 920px

	.poster
		display: flex
		flex-direction: column
		flex: auto
		canvas
			width: 100%
		&.no-pdf
			justify-content: center
			align-items: center
			background-color: $clr-grey-100
			color: $clr-grey-600
			.mdi
				font-size: 10vw
			p
				font-size: 48px
				font-weight: 600
				margin: 0
			&:hover
				background-color: $clr-grey-200
				color: $clr-grey-700
	.tags
		display: flex
		flex-wrap: wrap
		gap: 4px
		.tag
			color: $clr-primary-text-light
			border: 2px solid $clr-primary
			border-radius: 12px
			padding: 2px 6px
	.actions
		display: flex
		gap: 8px
		margin: 8px
	.btn-likes
		themed-button-secondary()
		align-self: flex-start
		margin: 8px
		.bunt-button-text
			display: flex
			align-items: center
			font-size: 18px
			cursor: pointer
			gap: 8px
			color: $clr-primary-text-light
			.mdi
				font-size: 32px
				color: $clr-pink
	.downloads
		display: flex
		flex-direction: column
		h3
			margin: 8px 0 0px
		.download
			display: flex
			align-items: center
			height: 36px
			font-weight: 600
			font-size: 16px
			min-width: 0
			&:hover
				background-color: $clr-grey-100
				text-decoration: underline
			.mdi
				font-size: 28px
				margin: 0 4px
			.filename
				ellipsis()
	.chat-sidebar
		display: flex
		flex-direction: column
		min-height: 0
		width: 380px
		flex: none
		border-left: border-separator()
		h3
			margin: 0
			padding: 8px
			border-bottom: border-separator()
		.presentation
			display: flex
			flex-direction: column
			> h2, p
				margin: 0 0 0 8px
			.session, .room, .presenter
				display: flex
				height: 52px
				cursor: pointer
				padding: 8px 8px 8px 16px
				box-sizing: border-box
				color: $clr-primary-text-light
				&:hover
					background-color: $clr-grey-100
			.room
				ellipsis()
				font-size: 16px
				font-weight: 500
				line-height: 36px
			.session
				flex-direction: column
				justify-content: center
				.title
					ellipsis()
					font-size: 16px
			.presenters
				display: flex
				flex-direction: column
				.presenter
					align-items: center
					gap: 8px
	+below(1200px)
		flex-direction: column
		.bunt-tabs
			tabs-style(active-color: var(--clr-primary), indicator-color: var(--clr-primary), background-color: transparent)
			margin-bottom: 0
			border-bottom: border-separator()
			.bunt-tabs-header-items
				justify-content: center
		.info-sidebar, .chat-sidebar
			border: none
			width: auto
			flex: auto
</style>
