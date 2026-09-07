<template lang="pug">
.c-januschannelcall(:class="[`size-${size}`]")
	janus-videoroom(
		v-if="server",
		ref="videoroom",
		:server="server",
		:token="token",
		:iceServers="iceServers",
		:sessionId="sessionId",
		:audioSessionId="audioSessionId",
		:videoSessionId="videoSessionId",
		:screenShareSessionId="screenShareSessionId",
		:roomId="roomId",
		:size="size",
		@hangup="$emit('close')"
	)
</template>
<script>
import JanusVideoroom from 'components/janus/JanusVideoroom'

export default {
	components: {JanusVideoroom},
	props: {
		call: {
			type: Object,
			required: false
		},
		size: {
			type: String, // 'normal', 'tiny'
			default: 'normal'
		},
		background: Boolean
	},
	emits: ['close'],
	data() {
		return {
			server: null,
			token: null,
			iceServers: [],
			roomId: null,
			sessionId: null,
			audioSessionId: null,
			videoSessionId: null,
			screenShareSessionId: null,
		}
	},
	computed: {
	},
	async created() {
		this.server = this.call.parameters.server
		this.token = this.call.parameters.token
		this.iceServers = this.call.parameters.iceServers
		this.roomId = this.call.parameters.roomId
		this.sessionId = this.call.parameters.sessionId
		this.audioSessionId = this.call.parameters.audioSessionId
		this.videoSessionId = this.call.parameters.videoSessionId
		this.screenShareSessionId = this.call.parameters.screenShareSessionId
	},
	methods: {
		toggleMic() {
			return this.$refs.videoroom?.toggleMic?.()
		},
		toggleCamera() {
			return this.$refs.videoroom?.toggleCamera?.()
		},
		cleanupMedia() {
			return this.$refs.videoroom?.hangup?.()
		},
		hangup() {
			return this.$refs.videoroom?.hangup?.()
		},
	},
}
</script>
<style lang="stylus">
.c-januschannelcall
	flex: auto
	height: 100%
	width: 100%
	display: flex
	flex-direction: column
	position: relative
	overflow: hidden

	&.size-tiny
		height: 100%
		width: 100%
		padding: 0
		overflow: hidden

</style>
