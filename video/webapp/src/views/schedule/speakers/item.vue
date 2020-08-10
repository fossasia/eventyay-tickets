<template lang="pug">
.c-schedule-speaker(v-scrollbar.y="")
	.speaker(v-if="speaker")
		h1 {{ speaker.name }}
		img.avatar(v-if="speaker.avatar", :src="speaker.avatar")
		markdown-content.biography(:markdown="speaker.biography")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import MarkdownContent from 'components/MarkdownContent'

export default {
	props: {
		speakerId: String
	},
	components: { MarkdownContent },
	data () {
		return {
			speaker: null
		}
	},
	computed: {},
	async created () {
		console.log(this.speakerId)
		// TODO error handling
		if (!this.$store.getters.pretalxApiBaseUrl) return
		this.speaker = await (await fetch(`${this.$store.getters.pretalxApiBaseUrl}/speakers/${this.speakerId}/`)).json()
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
	flex-direction: column
	background-color: $clr-white
	align-items: center
	.speaker
		display: flex
		flex-direction: column
		padding: 16px
		max-width: 720px
</style>
