<template lang="pug">
.c-januscall(:class="[`size-${size}`]")
	.error(v-if="error") {{ $t('JanusCall:error:text') }}
	janus-conference(v-if="server", :server="server", :token="token", :iceServers="iceServers", :sessionId="sessionId", :roomId="roomId", :size="size", :automute="true", @hangup="roomId = null; $router.push('/')")
</template>
<script>
import api from 'lib/api'
import JanusConference from 'components/janus/JanusConference'

export default {
	components: {JanusConference},
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true
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
			loading: false,
			error: null
		}
	},
	computed: {
	},
	async created () {
		this.loading = true
		this.error = null
		try {
			const {server, roomId, token, sessionId, iceServers} = await api.call('januscall.room_url', {room: this.room.id})
			if (!this.$el || this._isDestroyed) return
			this.roomId = roomId
			this.token = token
			this.iceServers = iceServers
			this.sessionId = sessionId
			this.server = server
		} catch (error) {
			// TODO handle bbb.join.missing_profile
			this.error = error
			this.loading = false
			console.log(error)
		}
	},
	methods: {
	},
}
</script>
<style lang="stylus">
.c-januscall
	flex: auto
	height: auto // 100% breaks safari
	display: flex
	flex-direction: column
	position: relative

	&.size-tiny
		height: 48px
		width: 86px // TODO total guesstimate
		pointer-events: none
		.controls, .mdi
			opacity: 0

</style>
