<template lang="pug">
.c-landing-page(:style="landingStyle", :class="{'has-header-image': hasHeaderBackground}")
	.landing-top-bg
	.landing-scroll(v-scrollbar.y="")
		header.landing-header
			a.event-home-back(
				v-if="homeBackLink",
				:href="homeBackLink.href",
				:aria-label="homeBackLink.ariaLabel",
				:class="{'event-home-back--expanded': homeBackExpanded}",
				@click.prevent="handleHomeBackClick"
			)
				span.event-home-back-pill
					i.fa.fa-angle-left.event-home-back-icon(aria-hidden="true")
					span.event-home-back-label(aria-hidden="true") {{ homeBackLink.label }}
			.event-hero
				.event-hero-overlay
					.event-brand
						.event-logo(v-if="heroImage")
							a(:href="presaleHomeUrl")
								img#event-logo.hero-logo(:src="heroImage", :alt="eventTitle")
						.event-hero-text(v-if="eventTitle || eventStartLine || showEventEndLine")
							a.event-title.event-public-text-link(v-if="eventTitle", :href="presaleHomeUrl") {{ eventTitle }}
							a.event-date-line.event-public-text-link(v-if="eventStartLine", :href="presaleHomeUrl") {{ eventStartLine }}
							a.event-date-line.event-public-text-link(v-if="showEventEndLine", :href="presaleHomeUrl") {{ eventEndLine }}
		.content-card(v-if="hasContent")
			.content
				rich-text-content(v-if="mainContentIsRichText", :content="mainContent")
				markdown-content(v-else-if="mainContentIsMarkdown", :content="mainContent")
				.split-layout
					.split-left(v-if="(featuredSessions && featuredSessions.length) || (nextSessions && nextSessions.length)")
						.landing-section(v-if="featuredSessions && featuredSessions.length")
							.section-header
								h3 {{ $t('Featured sessions') }}
								bunt-link-button.section-link(:to="{name: 'schedule'}") {{ $t('Complete schedule') }}
							.sessions
								session(
									v-for="session of featuredSessions",
									:session="session",
									:now="now",
									:faved="favs.includes(session.id)",
									@fav="$store.dispatch('schedule/fav', $event)",
									@unfav="$store.dispatch('schedule/unfav', $event)"
								)
						.landing-section(v-if="nextSessions && nextSessions.length")
							.section-header
								h3 {{ $t('Upcoming sessions') }}
								bunt-link-button.section-link(:to="{name: 'schedule'}") {{ $t('Complete schedule') }}
							.sessions
								session(
									v-for="session of nextSessions",
									:session="session",
									:now="now",
									:faved="favs.includes(session.id)",
									@fav="$store.dispatch('schedule/fav', $event)",
									@unfav="$store.dispatch('schedule/unfav', $event)"
								)
					.split-right
						.landing-section(v-if="activeRooms && activeRooms.length")
							.section-header
								h3 {{ $t('Stages') }}
							.active-rooms.active-rooms-list
								router-link.room-card(v-for="item of activeRooms", :key="item.room.id", :to="{name: 'room', params: {roomId: item.room.id}}")
									.room-info
										.room-name(v-html="$emojify(item.room.name)")
										.current-session(v-if="item.session")
											span.live-badge(v-if="item.isLive") {{ $t('Live') }}
											span {{ item.session.title }}
									svg.room-arrow(viewBox="0 0 24 24", stroke="currentColor", stroke-width="2", fill="none")
										path(d="M5 12h14M12 5l7 7-7 7")
						.landing-section.speakers-section(v-if="featuredSpeakers.length")
							.section-header
								h3 {{ $t('Featured speakers') }}
								bunt-link-button.section-link(:to="{name: 'schedule:speakers'}") {{ $t('All speakers') }}
							speakers-list(:hideToolbar="true", viewMode="list", :speakers="featuredSpeakers")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'
import config from 'config'
import Session from '@schedule/components/Session.vue'
import SpeakersList from '@schedule/components/SpeakersList.vue'
import MarkdownContent from 'components/MarkdownContent'
import RichTextContent from 'components/RichTextContent'
import { isRoomVisibleToAttendee } from 'lib/video-providers'

export default {
	components: { MarkdownContent, Session, RichTextContent, SpeakersList },
	props: {
		module: Object
	},
	data() {
		return {
			moment,
			eventMeta: null,
			homeBackExpanded: false
		}
	},
	computed: {
		...mapState(['now', 'rooms', 'world', 'userTimezone']),
		...mapState('schedule', ['schedule']),
		...mapGetters('schedule', ['sessions', 'favs', 'currentSessionPerRoom']),
		landingConfig() {
			return this.module?.config || {}
		},
		mainContent() {
			return this.landingConfig.main_content ?? this.landingConfig.content ?? null
		},
		mainContentIsRichText() {
			const content = this.mainContent
			if (!content) return false
			// Legacy Quill Delta (array of ops or { ops: [...] })
			if (typeof content === 'object') {
				if (Array.isArray(content)) {
					return content.some(op => typeof op?.insert === 'string' && op.insert.trim() !== '')
				}
				if (Array.isArray(content.ops)) {
					return content.ops.some(op => typeof op?.insert === 'string' && op.insert.trim() !== '')
				}
				return false
			}
			// Tiptap HTML strings (vs legacy plain Markdown)
			if (typeof content === 'string') {
				return /^\s*</.test(content)
			}
			return false
		},
		mainContentIsMarkdown() {
			return typeof this.mainContent === 'string' &&
				this.mainContent.trim().length > 0 &&
				!this.mainContentIsRichText
		},
		hasContent() {
			return this.mainContentIsRichText ||
				this.mainContentIsMarkdown ||
				(this.activeRooms && this.activeRooms.length > 0) ||
				(this.featuredSessions && this.featuredSessions.length > 0) ||
				(this.nextSessions && this.nextSessions.length > 0) ||
				this.featuredSpeakers.length > 0
		},
		mediaBaseUrl() {
			const apiBase = config?.api?.base
			if (!apiBase) return '/media/'
			try {
				return new URL('/media/', apiBase).toString()
			} catch {
				return '/media/'
			}
		},
		heroImage() {
			return this.resolveMediaUrl(
				this.landingConfig.header_image
				|| this.world?.visible_logo_url
				|| config?.visibleLogoUrl
			)
		},
		heroBackgroundImage() {
			return this.resolveMediaUrl(
				this.landingConfig.header_background_image
				|| this.world?.visible_header_image_url
				|| config?.visibleHeaderImageUrl
			)
		},
		hasHeaderBackground() {
			return !!this.heroBackgroundImage
		},
		eventTimezone() {
			return this.world?.timezone
				|| config?.eventTimezone
				|| this.userTimezone
				|| moment.tz.guess()
		},
		eventDateFrom() {
			return this.world?.date_from
				|| this.eventMeta?.date_from
				|| config?.eventDates?.date_from
				|| null
		},
		eventDateTo() {
			return this.world?.date_to
				|| this.eventMeta?.date_to
				|| config?.eventDates?.date_to
				|| null
		},
		landingStyle() {
			const themeColors = config?.theme?.colors || {}
			const headerBackground = themeColors.header_background
				|| themeColors.primary
				|| this.landingConfig.header_background_color
				|| '#2185d0'
			const headerText = themeColors.header_text || '#ffffff'
			return {
				'--landing-hero-background-color': headerBackground,
				'--landing-hero-text-color': headerText,
				'--landing-hero-background-image': this.heroBackgroundImage ? `url('${this.heroBackgroundImage}')` : 'none'
			}
		},
		presaleHomeUrl() {
			return config?.theme?.navigation?.presale_home_url
				|| config?.eventUrl
				|| ''
		},
		homeBackLink() {
			const navigation = config?.theme?.navigation
			if (navigation?.organizer_link_back && navigation.organizer_presale_url) {
				return {
					href: navigation.organizer_presale_url,
					label: navigation.organizer_name || '',
					ariaLabel: this.$t('Back to {{name}}', {
						name: navigation.organizer_name || ''
					})
				}
			}
			const href = navigation?.site_home_url
			if (!href) return null
			return {
				href,
				label: this.$t('Home'),
				ariaLabel: this.$t('Home')
			}
		},
		eventTitle() {
			if (this.world?.title) return this.world.title
			if (config?.eventTitle) return config.eventTitle
			const name = this.eventMeta?.name
			if (typeof name === 'string') return name
			if (name && typeof name === 'object') {
				return name[this.$i18n?.language] || name.en || Object.values(name)[0] || ''
			}
			return ''
		},
		eventDateRange() {
			if (this.eventDateFrom) {
				const timezone = this.eventTimezone
				return {
					start: moment.tz(this.eventDateFrom, timezone),
					end: moment.tz(this.eventDateTo || this.eventDateFrom, timezone)
				}
			}
			if (this.sessions?.length) {
				const start = this.sessions[0].start
				const end = this.sessions.reduce((latest, session) => session.end.isAfter(latest) ? session.end : latest, this.sessions[0].end)
				return { start, end }
			}
			return null
		},
		showDateTo() {
			return config?.showDateTo ?? true
		},
		showTimes() {
			return config?.showTimes ?? true
		},
		eventStartLine() {
			if (!this.eventDateRange) return ''
			return this.formatEventDateTime(this.eventDateRange.start)
		},
		showEventEndLine() {
			if (!this.eventDateRange || !this.showDateTo) return false
			return !this.eventDateRange.start.isSame(this.eventDateRange.end, 'day')
		},
		eventEndLine() {
			if (!this.showEventEndLine) return ''
			return this.$t('To {{- date}}', { date: this.formatEventDateTime(this.eventDateRange.end) })
		},
		featuredSessions() {
			if (!this.sessions) return
			return this.sessions.filter(session => session.featured)
		},
		featuredSpeakers() {
			if (!this.schedule?.speakers) return []
			return this.schedule.speakers.filter(speaker => speaker.is_featured)
		},
		nextSessions() {
			if (!this.sessions) return []
			// current or next sessions per room
			const sessions = []
			for (const session of this.sessions) {
				if (!session.room || !session.id) continue
				if (session.end.isBefore(this.now) || sessions.reduce((acc, s) => s.room === session.room ? ++acc : acc, 0) >= 2) continue
				sessions.push(session)
			}
			return sessions
		},
		activeRooms() {
			if (!this.rooms) return []
			// Shared list used for both the inclusion filter and the hasVideo flag.
			// Using the same constant avoids the bug where rooms with only
			// livestream.youtube rooms are shown as active but
			// not marked as having video.
			const videoModuleTypes = [
				'livestream.native',
				'livestream.youtube',
				'call.bigbluebutton',
				'call.zoom',
				'call.janus',
				'call.jitsi',
				'call.loungemesh'
			]
			return this.rooms
				.filter(r => isRoomVisibleToAttendee(r, this.world?.video_providers))
				.filter(r => r.schedule_data || r.modules?.some(m => videoModuleTypes.includes(m.type)))
				.map(room => {
				const sessionInfo = this.currentSessionPerRoom?.[room.id]
				const session = sessionInfo?.session
				const hasVideo = room.modules && room.modules.some(m => videoModuleTypes.includes(m.type))
				const isLive = !!session && hasVideo
				return { room, session, hasVideo, isLive }
			})
		},
	},
	async mounted() {
		await this.fetchEventMeta()
		document.addEventListener('click', this.handleHomeBackOutsideClick)
	},
	beforeUnmount() {
		document.removeEventListener('click', this.handleHomeBackOutsideClick)
	},
	methods: {
		handleHomeBackClick() {
			const href = this.homeBackLink?.href
			if (!href) return

			const supportsHover = window.matchMedia('(hover: hover)').matches
			if (supportsHover) {
				window.location.assign(href)
				return
			}
			if (!this.homeBackExpanded) {
				this.homeBackExpanded = true
				return
			}
			window.location.assign(href)
		},
		handleHomeBackOutsideClick(event) {
			if (event.target.closest('.event-home-back')) return
			this.homeBackExpanded = false
		},
		toMediaUrl(pathValue) {
			const cleaned = String(pathValue || '').replace(/^\/+/, '')
			if (!cleaned) return ''
			if (this.mediaBaseUrl.endsWith('/')) {
				return `${this.mediaBaseUrl}${cleaned}`
			}
			return `${this.mediaBaseUrl}/${cleaned}`
		},
		resolveMediaUrl(rawValue) {
			let value = typeof rawValue === 'string'
				? rawValue.trim()
				: (rawValue && typeof rawValue.url === 'string' ? rawValue.url.trim() : '')
			if (!value) return ''
			value = value.replace(/^['"]|['"]$/g, '')

			if (value.startsWith('public:')) {
				return this.toMediaUrl(value.slice(7))
			}
			if (value.startsWith('file://')) {
				return this.toMediaUrl(value.slice(7))
			}
			if (value.startsWith('data:') || value.startsWith('blob:')) {
				return value
			}
			if (/^(https?:)?\/\//.test(value)) {
				return value
			}
			if (value.startsWith('/')) {
				return value
			}

			return this.toMediaUrl(value)
		},
		formatEventDateTime(value) {
			const timezoneLabel = this.eventTimezone
			if (!this.showTimes) {
				return value.clone().tz(timezoneLabel).format('dddd, D MMMM, YYYY')
			}
			return `${value.clone().tz(timezoneLabel).format('dddd, D MMMM, YYYY HH:mm')} (${timezoneLabel})`
		},
		async fetchEventMeta() {
			if (!config?.api?.base) return
			try {
				const token = this.$store?.state?.token
				const clientId = this.$store?.state?.clientId
				const headers = {
					Accept: 'application/json'
				}
				if (token) {
					headers.Authorization = `Bearer ${token}`
				} else if (clientId) {
					headers.Authorization = `Client ${clientId}`
				}

				const response = await fetch(config.api.base, {
					method: 'GET',
					headers,
					credentials: 'same-origin'
				})
				if (response.ok) {
					const data = await response.json()
					if (data?.date_from) {
						this.eventMeta = data
						return
					}
				}

				const organizer = this.world?.organizer_slug || config?.organizerSlug
				const eventSlug = this.world?.slug || config?.eventSlug
				if (!organizer || !eventSlug) return

				const detailUrl = `/api/v1/organizers/${encodeURIComponent(organizer)}/events/${encodeURIComponent(eventSlug)}/`
				const detailResponse = await fetch(detailUrl, {
					method: 'GET',
					headers,
					credentials: 'same-origin'
				})
				if (!detailResponse.ok) return
				this.eventMeta = await detailResponse.json()
			} catch (error) {
				console.error('Failed to load landing page event metadata:', error)
			}
		},
	}
}
</script>
<style lang="stylus">
.c-landing-page
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	min-width: 0
	width: 100%
	position: relative
	background-color: $clr-grey-50
	overflow-x: hidden
	.landing-top-bg
		position: absolute
		top: 0
		left: 0
		right: 0
		height: calc(320px - 48px)
		z-index: 0
		pointer-events: none
		background-color: var(--landing-hero-background-color)
		background-image: var(--landing-hero-background-image)
		background-repeat: no-repeat
		background-size: cover
		background-position: center
	&.has-header-image .landing-top-bg::after
		content: ''
		position: absolute
		inset: 0
		background: linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.35) 40%, rgba(0,0,0,0.15) 100%)
	.landing-scroll
		flex: auto
		min-height: 0
		min-width: 0
		position: relative
		z-index: 1
		overflow-x: hidden
	.landing-header
		display: flex
		flex-direction: column
		justify-content: flex-end
		width: 100%
		max-width: 1600px
		margin: 0 auto
		padding: calc(1.5rem + 24px) 15px 0
		padding-left: calc(15px + 1.75rem)
		box-sizing: border-box
	.event-home-back
		align-self: flex-start
		display: inline-block
		margin: 0 0 6px
		padding-left: 0
		box-sizing: border-box
		text-decoration: none
		color: var(--landing-hero-text-color, var(--color-header-text, #fff))
		&:hover,
		&:focus-visible
			color: var(--landing-hero-text-color, var(--color-header-text, #fff))
			text-decoration: none
	.event-home-back-pill
		display: inline-flex
		align-items: center
		justify-content: center
		gap: 0
		min-height: 32px
		padding: 0 11px
		background: rgba(0, 0, 0, 0.45)
		border-radius: 8px
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.28)
		transition: gap 0.18s ease, background 0.18s ease
	.event-home-back:hover .event-home-back-pill,
	.event-home-back:focus-visible .event-home-back-pill,
	.event-home-back.event-home-back--expanded .event-home-back-pill
		gap: 0.4em
		background: rgba(0, 0, 0, 0.62)
	.event-home-back:focus-visible
		outline: none
	.event-home-back:focus-visible .event-home-back-pill
		outline: 2px solid rgb(255 255 255 / 0.85)
		outline-offset: 2px
	.event-home-back .event-home-back-icon
		font-size: 22px
		line-height: 1
		flex-shrink: 0
	.event-home-back .event-home-back-label
		font-size: 14px
		font-weight: 600
		line-height: 1
		max-width: 0
		opacity: 0
		overflow: hidden
		white-space: nowrap
		transition: max-width 0.22s ease, opacity 0.18s ease
	.event-home-back:hover .event-home-back-label,
	.event-home-back:focus-visible .event-home-back-label,
	.event-home-back.event-home-back--expanded .event-home-back-label
		max-width: 12em
		opacity: 1
	.event-hero
		display: flex
		align-items: center
		margin: 1rem 0 3.5rem
		min-height: 100px
	.event-hero-overlay
		display: flex
		width: 100%
		padding: 0
		box-sizing: border-box
		min-height: 100px
		align-items: center
	.event-brand
		display: flex
		align-items: center
		gap: 2rem
		flex-wrap: nowrap
		text-align: left
		min-width: 0
		width: 100%
	.event-logo a
		display: block
		text-decoration: none
	.event-hero-text
		color: var(--landing-hero-text-color, var(--color-header-text, #fff))
		display: flex
		flex-direction: column
		gap: 2px
		min-width: 0
	.event-hero-text .event-title
		font-size: 3rem
		font-weight: 700
		line-height: 1.2
		word-break: break-word
		overflow-wrap: break-word
		min-width: 0
		text-align: left
		margin: 0
	.event-date-line
		font-size: 1rem
		line-height: 1.3
		opacity: 0.96
		margin: 0
		color: var(--landing-hero-text-color, var(--color-header-text, #fff))
	.event-public-text-link
		color: inherit
		text-decoration: none
		display: block
		&:hover,
		&:focus-visible
			color: inherit
			text-decoration: none
	.hero-logo,
	#event-logo
		height: auto
		max-height: 140px
		max-width: 240px
		width: auto
		object-fit: contain
	.content-card
		position: relative
		z-index: 2
		width: 100%
		max-width: 1600px
		margin: 0 auto
		background-color: $clr-white
		box-shadow: 0 5px 10px rgba(0, 0, 0, 0.2)
		border-radius: 4px 4px 0 0
		box-sizing: border-box
		min-width: 0
		overflow-x: hidden
	.content
		display: flex
		flex-direction: column
		width: 100%
		min-width: 0
		padding: 24px
		box-sizing: border-box
	.rich-text-content, .c-markdown-content
		max-width: 960px
		margin: 0 auto
	.landing-section
		margin-top: 30px
		&:first-child
			margin-top: 0
	.section-header
		display: flex
		justify-content: space-between
		align-items: baseline
		gap: 16px
		min-height: 56px
		padding: 0 8px
		h3
			margin: 0
			line-height: 1.3
			font-size: 24px
			font-weight: 600
			text-transform: none
		.section-link.bunt-link-button
			flex: none
			text-transform: none
			font-weight: 500
			letter-spacing: normal
			themed-button-primary()

	.sessions
		min-width: 0
		> *
			width: 100%
			max-width: 100%
			min-width: 0
			margin-right: 0
			box-sizing: border-box
	.split-layout
		display: grid
		grid-template-columns: minmax(0, 1fr)
		gap: 32px
		margin-top: 24px
		@media (min-width: 900px)
			grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)
		.split-left, .split-right
			display: flex
			flex-direction: column
			gap: 24px
			min-width: 0

	.active-rooms-list
		display: flex
		flex-direction: column
		gap: 12px
		padding: 0 8px
		.room-card
			display: flex
			flex-direction: row
			align-items: center
			justify-content: space-between
			background: $clr-white
			border: border-separator()
			border-radius: 6px
			padding: 16px
			text-decoration: none
			color: inherit
			transition: background-color 0.2s
			&:hover
				background-color: $clr-grey-100
			.room-info
				flex: 1
				min-width: 0
			.room-name
				font-size: 18px
				font-weight: 600
				margin-bottom: 8px
				text-transform: none
			.current-session
				font-size: 14px
				color: $clr-secondary-text-light
				white-space: nowrap
				overflow: hidden
				text-overflow: ellipsis
				display: flex
				align-items: center
				.live-badge
					background-color: $clr-danger
					color: $clr-white
					font-size: 10px
					font-weight: 600
					padding: 2px 6px
					border-radius: 4px
					margin-right: 8px
					text-transform: none
			.room-arrow
				width: 20px
				height: 20px
				color: $clr-secondary-text-light
				margin-left: 12px
				flex-shrink: 0

	+below('s')
		.landing-top-bg
			height: calc(480px - 48px)
		.landing-header
			padding-left: 12px
			padding-right: 0
			padding-top: 24px
		.event-home-back
			padding-left: 0
		.event-home-back .event-home-back-icon
			font-size: 19px
		.event-home-back .event-home-back-label
			font-size: 13.5px
		.event-hero
			margin: 0.25rem 0 1.5rem
		.event-hero-overlay
			align-items: flex-start
			min-height: auto
			flex-direction: column
			display: flex
		.event-brand
			display: flex
			flex-direction: column
			gap: 1rem
			align-items: flex-start
		.event-hero-text .event-title
			font-size: 2rem
		.event-date-line
			font-size: 0.9rem
		.hero-logo,
		#event-logo
			max-width: min(72vw, 280px)
			max-height: 120px
		.content
			padding: 16px 8px
		.section-header h3
			font-size: 20px

	@media (max-width: 576px)
		.event-hero-text .event-title
			font-size: 1.6rem
</style>
