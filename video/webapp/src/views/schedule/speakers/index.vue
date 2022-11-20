<template lang="pug">
.c-schedule-speakers
	h1 {{ $t('schedule/speakers/index:header') }}
	bunt-progress-circular(v-if="!speakers || !schedule", size="huge", :page="true")
	scrollbars(v-else, y="")
		.speakers
			router-link.speaker(v-for="speaker of speakers", :to="speaker.attendee ? {name: '', params: {}} : { name: 'schedule:speaker', params: { speakerId: speaker.code } }")
				img.avatar(v-if="speaker.avatar", :src="speaker.avatar")
				identicon(v-else, :user="{id: speaker.name, profile: {display_name: speaker.name}}")
				.content
					.name {{ speaker.name }}
					//- this has html ?
					p.biography {{ speaker.biography }}
					.sessions(v-if="speaker.sessions.length && speaker.sessions.some(s => s)")
						h2 {{ $t('schedule/speakers/index:speaker-sessions:header') }}:
						.session(v-for="session of speaker.sessions", v-if="session")
							.title {{ session.title }}
</template>
<script>
// TODOs
// search
import { mapGetters, mapState } from 'vuex'
import Identicon from 'components/Identicon'

export default {
	components: { Identicon },
	data () {
		return {
			speakers: null
		}
	},
	computed: {
		...mapState('schedule', ['schedule']),
		...mapGetters('schedule', ['sessionsLookup'])
	},
	async created () {
		if (!this.$store.getters['schedule/pretalxApiBaseUrl']) return
		this.speakers = (await (await fetch(`${this.$store.getters['schedule/pretalxApiBaseUrl']}/speakers/?limit=999`)).json()).results.sort((a, b) => a.name.localeCompare(b.name))
		// const speakersToAttendee = await api.call('user.fetch', {pretalx_ids: this.speakers.map(speaker => speaker.code)})
		for (const speaker of this.speakers) {
			speaker.sessions = speaker.submissions.map(submission => this.sessionsLookup[submission])
			// speaker.attendee = speakersToAttendee[speaker.code]
		}
	}
}
</script>
<style lang="stylus">
.c-schedule-speakers
	flex: auto
	min-height: 0
	display: flex
	flex-direction: column
	align-items: center
	.scroll-content
		display: flex
		flex-direction: column
		align-items: center
		> *
			width: @css{min(920px, 100%)}
	.speaker
		color: $clr-primary-text-light
		display: flex
		gap: 16px
		cursor: pointer
		padding: 8px
		border-left: border-separator()
		border-right: border-separator()
		border-bottom: border-separator()
		&:first-child
			border-top: border-separator()
		&:hover
			background-color: $clr-grey-200
		img
			flex: none
			border-radius: 50%
			height: 92px
			width: @height
			object-fit: cover
		.name
			font-weight: 500
			font-size: 16px
		.biography
			display: -webkit-box
			-webkit-box-orient: vertical
			-webkit-line-clamp: 3
			overflow: hidden
	.sessions
		display: flex
		flex-direction: column
		gap: 8px
		margin-bottom: 8px
		h2
			font-weight: 500
			font-size: 16px
			margin: 0
</style>
