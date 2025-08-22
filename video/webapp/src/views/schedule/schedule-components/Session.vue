<template lang="pug">
a.c-linear-schedule-session(:class="{faved}", :style="style", :href="link", @click="onSessionLinkClick($event, session)", :target="linkTarget")
	.time-box
		.start(:class="{'has-ampm': hasAmPm}")
			.time {{ startTime.time }}
			.ampm(v-if="startTime.ampm") {{ startTime.ampm }}
		.duration {{ getPrettyDuration(session.start, session.end) }}
		.buffer
		.is-live(v-if="isLive") live
	.info
		.title {{ getLocalizedString(session.title) }}
		.speakers(v-if="session.speakers")
			.avatars
				template(v-for="speaker of session.speakers")
					.speaker-info
						img(v-if="speaker.avatar || speaker.avatar_url", :src="speaker.avatar || speaker.avatar_url")
						.names {{ speaker.name }}
		.do_not_record
			svg(v-if="session.do_not_record", viewBox="0 -1 24 24", width="22px", height="22px", fill="none", xmlns="http://www.w3.org/2000/svg")
				path(d="M1.29292 20.2929C0.902398 20.6834 0.902398 21.3166 1.29292 21.7071C1.68345 22.0976 2.31661 22.0976 2.70714 21.7071L22.7071 1.70711C23.0977 1.31658 23.0977 0.68342 22.7071 0.29289C22.3166 -0.097631 21.6834 -0.097631 21.2929 0.29289L20.2975 1.28829C20.296 1.28982 20.2944 1.29135 20.2929 1.29289L2.29289 19.2929C2.29136 19.2944 2.28984 19.296 2.28832 19.2975L1.29292 20.2929z", fill="#758CA3")
				path(d="M15 3C15.2339 3 15.4615 3.02676 15.68 3.07739L13.7574 5H3C2.44772 5 2 5.44771 2 6V16C2 16.2142 2.06734 16.4126 2.182 16.5754L0.87868 17.8787C0.839067 17.9183 0.800794 17.9587 0.76386 18C0.28884 17.4692 0 16.7683 0 16V6C0 4.34314 1.34315 3 3 3H15z", fill="#758CA3")
				path(d="M10.2426 17H15C15.5523 17 16 16.5523 16 16V14.0233C15.9996 14.0079 15.9996 13.9924 16 13.9769V11.2426L18 9.2426V13.2792L22 14.6126V7.38742L18.7828 8.45982L21.9451 5.29754L22.6838 5.05132C23.3313 4.83547 24 5.31744 24 6V16C24 16.6826 23.3313 17.1645 22.6838 16.9487L18 15.3874V16C18 17.6569 16.6569 19 15 19H8.24264L10.2426 17z", fill="#758CA3")
		.tags-box
			.tags(v-for="tag_item of session.tags")
				.tag-item(:style="{'background-color': tag_item.color, 'color': getContrastColor(tag_item.color)}") {{ tag_item.tag }}
		.abstract(v-if="showAbstract", v-html="abstract")
		.bottom-info
			.track(v-if="session.track") {{ getLocalizedString(session.track.name) }}
			.room(v-if="showRoom && session.room") {{ getLocalizedString(session.room.name) }}
		.fav-count(v-if="session.fav_count > 0 && isLinearSchedule") {{ session.fav_count > 99 ? "99+" : session.fav_count  }}
	bunt-icon-button.btn-fav-container(@click.prevent.stop="faved ? $emit('unfav', session.id) : $emit('fav', session.id)")
		svg.star(viewBox="0 0 24 24")
			path(d="M12,17.27L18.18,21L16.54,13.97L22,9.24L14.81,8.62L12,2L9.19,8.62L2,9.24L7.45,13.97L5.82,21L12,17.27Z")

</template>
<script>
import moment from 'moment-timezone'
import MarkdownIt from 'markdown-it'
import { getLocalizedString, getPrettyDuration } from 'views/schedule/utils'

const markdownIt = MarkdownIt({
	linkify: true,
	breaks: true
})

export default {
	props: {
		session: Object,
		showAbstract: {
			type: Boolean,
			default: true
		},
		showRoom: {
			type: Boolean,
			default: true
		},
		faved: {
			type: Boolean,
			default: false
		},
		hasAmPm: {
			type: Boolean,
			default: false
		},
		isLinearSchedule: Boolean
	},
	inject: {
		eventUrl: { default: null },
		linkTarget: { default: '_self' },
		generateSessionLinkUrl: {
			default() {
				return ({eventUrl, session}) => `${eventUrl}talk/${session.id}/`
			}
		},
		onSessionLinkClick: {
			default() {
				return () => {}
			}
		}
	},
	data() {
		return {
			getPrettyDuration,
			getLocalizedString
		}
	},
	computed: {
		link() {
			return this.generateSessionLinkUrl({eventUrl: this.eventUrl, session: this.session})
		},
		style() {
			return {
				'--track-color': this.session.track?.color || 'var(--pretalx-clr-primary)'
			}
		},
		startTime() {
			// check if 12h or 24h locale
			if (this.hasAmPm) {
				return {
					time: this.session.start.format('h:mm'),
					ampm: this.session.start.format('A')
				}
			} else {
				return {
					time: moment(this.session.start).format('LT')
				}
			}
		},
		isLive() {
			return moment(this.session.start).isBefore(this.now) && moment(this.session.end).isAfter(this.now)
		},
		abstract() {
			try {
				return markdownIt.renderInline(this.session.abstract)
			} catch (error) {
				return this.session.abstract
			}
		}
	},
	methods: {
		getContrastColor(bgColor) {
			if (!bgColor) {
				return ''
			}

			// Remove the hash if it's there
			bgColor = bgColor.replace('#', '')

			// Convert the color to RGB
			var r = parseInt(bgColor.slice(0, 2), 16)
			var g = parseInt(bgColor.slice(2, 4), 16)
			var b = parseInt(bgColor.slice(4, 6), 16)

			// Calculate the brightness of the color
			var brightness = (r * 299 + g * 587 + b * 114) / 1000

			// If the brightness is over 128, return black. Otherwise, return white
			return brightness > 128 ? 'black' : 'white'
		}
	}
}
</script>
<style lang="stylus">
.c-linear-schedule-session, .break
	z-index: 10
	display: flex
	min-width: 300px
	min-height: 96px
	margin: 8px
	overflow: hidden
	color: $clr-primary-text-light
	position: relative
	.time-box
		width: 69px
		box-sizing: border-box
		background-color: var(--track-color)
		padding: 12px 16px 8px 12px
		border-radius: 6px 0 0 6px
		display: flex
		flex-direction: column
		align-items: center
		.start
			color: $clr-primary-text-dark
			font-size: 16px
			font-weight: 600
			margin-bottom: 8px
			display: flex
			flex-direction: column
			align-items: flex-end
			&.has-ampm
				align-self: stretch
			.ampm
				font-weight: 400
				font-size: 13px
		.duration
			color: $clr-secondary-text-dark
		.buffer
			flex: auto
		.is-live
			align-self: stretch
			text-align: center
			font-weight: 600
			padding: 2px 4px
			border-radius: 4px
			margin: 0 -10px 0 -6px // HACK
			background-color: $clr-danger
			color: $clr-primary-text-dark
			letter-spacing: 0.5px
			text-transform: uppercase
	.info
		flex: auto
		display: flex
		flex-direction: column
		padding: 8px
		border: border-separator()
		border-left: none
		border-radius: 0 6px 6px 0
		background-color: $clr-white
		min-width: 0
		.title
			font-size: 16px
			font-weight: 500
			margin-bottom: 4px
		.speakers
			color: $clr-secondary-text-light
			display: flex
			.avatars
				.speaker-info
					margin-left: 0px !important
					display: flex
					flex: none
					img
						background-color: $clr-white
						border-radius: 50%
						height: 24px
						width: @height
						margin: 0 8px 0 0
						object-fit: cover
					.names
						line-height: 24px
		.abstract
			margin: 8px 0 12px 0
			// TODO make this take up more space if available?
			display: -webkit-box
			-webkit-line-clamp: 3
			-webkit-box-orient: vertical
			overflow: hidden
		.bottom-info
			flex: auto
			display: flex
			align-items: flex-end
			.track
				flex: 1
				color: var(--track-color)
				ellipsis()
				margin-right: 4px
			.room
				flex: 1
				text-align: right
				color: $clr-secondary-text-light
				ellipsis()
	.btn-fav-container
		display: none
		position: absolute
		top: 2px
		right: 2px
		icon-button-style(style: clear)
		svg path
			fill: none
			stroke: $clr-primary-text-light
			stroke-width: 1px
			vector-effect: non-scaling-stroke
	&.faved
		.btn-fav-container
			display: inline-flex
			svg path
				fill: $clr-primary-text-light
	&:hover
		.info
			border: 1px solid var(--track-color)
			border-left: none
			.title
				color: var(--pretalx-clr-primary)
		.btn-fav-container
			display: inline-flex
	// +below('m')
	// 	min-width: 0
	.fav-count
		border: 1px solid
		border-radius: 50%
		position: absolute
		top: 5px
		right: 40px
		width: 25px
		height: 25px
		display: flex
		justify-content: center
		align-items: center
		text-align: center
		background-color: var(--track-color)
		color: $clr-primary-text-dark

	.do_not_record
		margin: 10px 0px
	.tags-box
		display: flex
		margin: 5px 0px
		.tags
			margin: 0px 2px
			.tag-item
				padding: 3px
</style>
