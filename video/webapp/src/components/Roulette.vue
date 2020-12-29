<template lang="pug">
.c-roulette
	.room
		janus-videoroom(v-if="server", :server="server", :token="token", :iceServers="iceServers", :roomId="roomId", :key="`janus-videoroom-${roomId}`")
	.next
		bunt-button.btn-next(@click="startNewCall", :error-message="joinError", :loading="loading") {{ $t('Roulette:btn-start:label') }}

</template>
<script>
import {mapState} from 'vuex'
import api from 'lib/api'
import JanusVideoroom from 'components/janus/JanusVideoroom';

export default {
	components: {JanusVideoroom},
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true,
		},
	},
	data () {
		return {
			server: null,
			token: null,
			iceServers: [],
			roomId: null,
			loading: false,
			joinError: null,
		}
	},
	methods: {
		async startNewCall () {
			this.janus = null
			this.server = null
			this.roomId = null
			this.feeds = []
			this.loading = true
			this.joinError = null
			try {
				const {server, roomId, token, iceServers} = await api.call('roulette.start', {room: this.room.id})
				this.roomId = roomId
				this.token = token
				this.iceServers = iceServers
				this.server = server
				this.loading = false
			} catch (e) {
				this.joinError = e.message
				this.loading = false
			}
		},
	},
}
</script>
<style lang="stylus">
	.c-roulette
		flex: auto
		height: auto // 100% breaks safari
		display: flex
		flex-direction: column
		position: relative
	.room
		flex-basis: 100%
		flex-grow: 1
		flex-shrink: 1
	.next
		padding: 16px
		flex-shrink: 1
		text-align: center
		.btn-next
			themed-button-primary(size: large)
</style>
