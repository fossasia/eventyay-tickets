<template lang="pug">
.c-bigbluebutton
	iframe(v-if="url", :src="url", allow="camera; autoplay; microphone; fullscreen; display-capture", allowfullscreen, allowusermedia)
	.error(v-else-if="error") {{ $t('BigBlueButton:error:text') }}
</template>
<script>
import api from 'lib/api'
export default {
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true
		}
	},
	data () {
		return {
			url: null, // YOUR TEST URL HERE
			error: null
		}
	},
	computed: {},
	async created () {
		try {
			const {url} = await api.call('bbb.url', {room: this.room.id})
			this.url = url
		} catch (error) {
			// TODO handle bbb.join.missing_profile
			this.error = error
			console.log(error)
		}
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-bigbluebutton
	flex: auto
	height: 100%
	display: flex
	flex-direction: column
	iframe
		height: 100%
		width: 100%
		border: none
		flex: auto // because safari
</style>
