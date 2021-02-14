<template lang="pug">
.c-roulette
	.room
		janus-videoroom(v-if="server", :server="server", :token="token", :iceServers="iceServers", :roomId="roomId", :key="`janus-videoroom-${roomId}`", @hangup="stopCall")
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
		...mapState('roulette', ['callId', 'server', 'iceServers', 'token', 'roomId', 'loading', 'error']),
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
	flex: auto
	height: auto // 100% breaks safari
	display: flex
	flex-direction: column
	position: relative
	.room
		flex-basis: 100%
		flex-grow: 1
		flex-shrink: 1
		align-items: center
		justify-content: center
		display: flex
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
