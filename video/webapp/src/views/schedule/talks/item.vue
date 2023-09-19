<template lang="pug">
.c-schedule-talk(v-scrollbar.y="")
	.talk-wrapper(v-if="talk")
		.talk
			h1 {{ talk.title }}
			//- TODO choose locale
			.info {{ datetime }} {{ roomName }}
			markdown-content.abstract(:markdown="talk.abstract")
			markdown-content.description(:markdown="talk.description")
			.downloads(v-if="talk.resources && talk.resources.length > 0")
				h2 {{ $t("schedule/talks:downloads-headline:text") }}
				a.download(v-for="{resource, description} of talk.resources", :href="resource", target="_blank")
					.mdi(:class="`mdi-${getIconByFileEnding(resource)}`")
					.filename {{ description }}
		.speakers(v-if="talk.speakers.length > 0")
			.header {{ $t('schedule/talks/item:speakers:header', {count: talk.speakers.length})}}
			.speakers-list
				.speaker(v-for="speaker of talk.speakers")
					img.avatar(v-if="speaker.avatar", :src="speaker.avatar")
					router-link.name(v-if="pretalxApiBaseUrl", :to="{name: 'schedule:speaker', params: {speakerId: speaker.code}}") {{ speaker.name }}
					.name(v-else) {{ speaker.name }}
					markdown-content.biography(:markdown="speaker.biography")
					//- TODO other talks by this speaker
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapGetters } from 'vuex'
import moment from 'lib/timetravelMoment'
import MarkdownContent from 'components/MarkdownContent'
import { getIconByFileEnding } from 'lib/filetypes'

export default {
	components: {MarkdownContent},
	props: {
		talkId: String
	},
	data () {
		return {
			talk: null
		}
	},
	computed: {
		...mapGetters('schedule', ['pretalxApiBaseUrl', 'sessions']),
		datetime () {
			return moment(this.talk.slot?.start || this.talk.start).format('L LT') + ' - ' + moment(this.talk.slot?.end || this.talk.end).format('LT')
		},
		roomName () {
			return this.$localize(this.talk.slot?.room || this.talk.room.name)
		}
	},
	watch: {
		sessions: {
			handler () {
				if (!this.sessions) return
				if (this.talk) return
				this.talk = this.sessions.find(session => session.id === this.talkId)
			},
			immediate: true
		}
	},
	async created () {
		// TODO error handling
		if (!this.pretalxApiBaseUrl) return
		this.talk = await (await fetch(`${this.pretalxApiBaseUrl}/talks/${this.talkId}/`)).json()
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		getIconByFileEnding
	}
}
</script>
<style lang="stylus">
// TODO larger font size for body text?
.c-schedule-talk
	display: flex
	flex-direction: column
	background-color: $clr-white
	.talk-wrapper
		flex: auto
		display: flex
		justify-content: center
	.talk
		flex: none
		margin: 16px 0 16px 16px
		max-width: 720px
		h1
			margin-bottom: 0
		.info
			font-size: 18px
			color: $clr-secondary-text-light
		.abstract
			margin: 16px 0 0 0
			font-size: 16px
			font-weight: 600
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
	.speakers
		width: 280px
		margin: 32px 16px
		display: flex
		flex-direction: column
		border: border-separator()
		border-radius: 4px
		align-self: flex-start
		.header
			border-bottom: border-separator()
			padding: 8px
		.speaker
			padding: 8px
			display: flex
			flex-direction: column

			img
				max-width: 100%
				align-self: center
			.name
				display: block
				margin: 8px 0
				font-weight: 600
	+below('m')
		.talk-wrapper
			display: block
		.speakers
			width: auto
		.talk
			max-width: 100%
			margin: 16px
</style>
