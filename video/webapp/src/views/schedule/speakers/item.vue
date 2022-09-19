<template lang="pug">
.c-schedule-speaker(v-scrollbar.y="")
	bunt-progress-circular(v-if="!speaker", size="huge", :page="true")
	template(v-else)
		.speaker
			img.avatar(v-if="speaker.avatar", :src="speaker.avatar")
			.content
				h1 {{ speaker.name }}
				markdown-content.biography(:markdown="speaker.biography")
		.sessions
			h2 Sessions
			session-list(:sessions="sessions")
</template>
<script>
import { mapGetters } from 'vuex'
import MarkdownContent from 'components/MarkdownContent'
// TODO remove this again
import SessionList from 'components/SessionList'

export default {
	components: { MarkdownContent, SessionList },
	props: {
		speakerId: String
	},
	data () {
		return {
			speaker: null
		}
	},
	computed: {
		...mapGetters('schedule', ['sessionsLookup']),
		sessions () {
			return this.speaker.submissions.map(submission => this.sessionsLookup[submission])
		}
	},
	async created () {
		// TODO error handling
		if (!this.$store.getters['schedule/pretalxApiBaseUrl']) return
		this.speaker = await (await fetch(`${this.$store.getters['schedule/pretalxApiBaseUrl']}/speakers/${this.speakerId}/`)).json()
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-schedule-speaker
	display: flex
	background-color: $clr-white
	flex-direction: column
	align-items: center
	gap: 16px
	.speaker
		display: flex
		max-width: 920px
		gap: 16px
		img
			border-radius: 50%
			height: 256px
			width: @height
			object-fit: cover
			padding: 16px
		h1
			margin: 24px 0 16px
</style>
