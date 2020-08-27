<template lang="pug">
.c-schedule-talk(v-scrollbar.y="")
	.talk-wrapper(v-if="talk")
		.talk
			h1 {{ talk.title }}
			//- TODO choose locale
			.info {{ datetime }} {{ talk.slot.room.en }}
			section.abstract {{ talk.abstract }}
			p {{ talk.description }}
		.speakers
			.header {{ $tc('schedule/talks/item:speakers:header', talk.speakers.length)}}
			.speakers-list
				.speaker(v-for="speaker of talk.speakers")
					img.avatar(v-if="speaker.avatar", :src="speaker.avatar")
					router-link.name(:to="{name: 'schedule:speaker', params: {speakerId: speaker.code}}") {{ speaker.name }}
					markdown-content.biography(:markdown="speaker.biography")
					//- TODO other talks by this speaker
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import moment from 'lib/timetravelMoment'
import MarkdownContent from 'components/MarkdownContent'

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
		datetime () {
			return moment(this.talk.slot.start).format('L LT') + ' - ' + moment(this.talk.slot.end).format('LT')
		}
	},
	async created () {
		// TODO error handling
		if (!this.$store.getters['schedule/pretalxApiBaseUrl']) return
		this.talk = await (await fetch(`${this.$store.getters['schedule/pretalxApiBaseUrl']}/talks/${this.talkId}/`)).json()
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
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
			.name
				display: block
				margin: 8px 0
				font-weight: 600
</style>
