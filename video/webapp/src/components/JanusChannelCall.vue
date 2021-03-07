<template lang="pug">
.c-januschannelcall(:class="[`size-${size}`]")
	janus-videoroom(v-if="server", :server="server", :token="token", :iceServers="iceServers", :sessionId="sessionId", :roomId="roomId", :size="size", @hangup="$emit('close')")
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
	data () {
		return {
			server: null,
			token: null,
			iceServers: [],
			roomId: null,
			sessionId: null,
		}
	},
	computed: {
	},
	async created () {
		this.server = this.call.parameters.server
		this.token = this.call.parameters.token
		this.iceServers = this.call.parameters.iceServers
		this.roomId = this.call.parameters.roomId
		this.sessionId = this.call.parameters.sessionId
	},
	methods: {
	},
}
</script>
<style lang="stylus">
.c-januschannelcall
	flex: auto
	height: auto // 100% breaks safari
	display: flex
	flex-direction: column
	position: relative
	padding-bottom: 8px

	&.size-tiny
		height: 48px
		width: 86px // TODO total guesstimate
		padding-bottom: 0
		pointer-events: none
		.controls, .mdi
			opacity: 0

</style>
