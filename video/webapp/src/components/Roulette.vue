<template lang="pug">
.c-roulette
	.call(v-if="server")
		janus-videoroom(:server="server", :token="token", :iceServers="iceServers", :sessionId="sessionId", :roomId="roomId", size="normal", :automute="false", :key="`janus-videoroom-${roomId}`", @hangup="stopCall")
	.status(v-else-if="loading && !callId") {{ $t('Roulette:waiting:text') }}
	.status(v-else-if="loading && callId") {{ $t('Roulette:connecting:text') }}
	.status(v-else) {{ $t('Roulette:instructions:text') }}
	.next
		bunt-button.btn-next(@click="findNewCall", :error-message="error", :loading="loading") {{ $t('Roulette:btn-start:label') }}

</template>
<script>
import JanusVideoroom from 'components/janus/JanusVideoroom'
import {mapActions, mapMutations, mapState} from 'vuex'

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
		}
	},
	computed: {
		...mapState(['connected']),
		...mapState('roulette', ['callId', 'server', 'iceServers', 'token', 'roomId', 'sessionId', 'loading', 'error']),
	},
	watch: {
		connected (value) {
			if (value) {
				// resubscribe
				this.$store.dispatch('roulette/reconnect')
			}
		}
	},
	destroyed () {
		this.stopRequesting()
		this.stopCall()
	},
	methods: {
		...mapMutations('roulette', ['setLoading']),
		...mapActions('roulette', ['startCall', 'stopCall', 'startRequesting', 'stopRequesting']),

		findNewCall () {
			this.stopCall()
			this.startRequesting({room: this.room})
		},
	},
}
</script>
<style lang="stylus">
.c-roulette
	flex: 100% 0 0
	max-height: 100%
	height: auto // 100% breaks safari
	display: flex
	flex-direction: column
	align-items: center
	justify-content: center
	.call
		width: 100%
		flex: auto 1 1
		position: relative
		.c-janusvideoroom
			position: absolute
			left: 0
			top: 0
			width: 100%
			height: 100%
	.status
		text-align: center
		padding: 16px
		font-size: 24px
	.next
		padding: 16px
		flex-shrink: 1
		text-align: center
		.btn-next
			themed-button-primary(size: large)
</style>
