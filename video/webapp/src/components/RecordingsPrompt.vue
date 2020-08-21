<template lang="pug">
prompt.c-recordings-prompt(@close="$emit('close')")
	.content
		bunt-icon-button#btn-close(@click="$emit('close')") close
		h1 {{ $t('RecordingsPrompt:headline:text') }}
		p {{ $t('RecordingsPrompt:info:text') }}
		bunt-progress-circular(v-if="recordings == null && error == null")
		p(v-if="error != null") {{ $t('RecordingsPrompt:error:text') }}
		.recordings(v-if="recordings != null")
			.recording(v-for="r in recordings")
				.recording-dates {{ moment(r.start).format('l, LT') }} – {{ moment(r.end).format('LT') }}
				a.link.bunt-button(v-if="r.url && r.state == 'published'", :href="r.url", target="_blank") {{ $t('RecordingsPrompt:view:label') }}
				span(v-else) {{ r.state }}
</template>
<script>
import api from 'lib/api'
import Prompt from 'components/Prompt'
import moment from 'moment'

export default {
	components: { Prompt },
	props: {
		room: Object
	},
	data () {
		return {
			recordings: null,
			error: null,
		}
	},
	computed: {},
	async created () {
		try {
			this.recordings = (await api.call('bbb.recordings', {room: this.room.id})).results
			this.error = null
		} catch (error) {
			this.error = error
			this.recordings = null
			console.error(error)
		}
	},
	methods: {
		moment: moment
	}
}
</script>
<style lang="stylus">
.c-recordings-prompt
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
		h1
			margin: 0
			text-align: center
		.bunt-progress-circular
			margin: auto
		.recording
			border-bottom: 1px solid #ccc
			display: flex
			justify-content: space-between
			align-items: center
			padding: 8px 0
			.bunt-button
				themed-button-primary()

</style>
