<template lang="pug">
.c-iframe-page
	bunt-progress-circular(size="huge", :page="true", v-if="loading")
	iframe-blocker(:src="url", allow="camera *; autoplay *; microphone *; fullscreen *; display-capture *", allowfullscreen, allowusermedia, @load="loaded")
</template>
<script>
import {mapState} from 'vuex'
import IframeBlocker from './IframeBlocker'

export default {
	components: { IframeBlocker },
	props: {
		module: {
			type: Object,
			required: true
		}
	},
	data () {
		return {
			loading: false,
		}
	},
	computed: {
		...mapState(['user']),

		url () {
			let url = this.module.config.url
			url = url.replace('{display_name}', encodeURIComponent(this.user.profile.display_name))
			url = url.replace('{id}', encodeURIComponent(this.user.id))
			return url
		}
	},
	mounted () {
		window.addEventListener('message', this.onMessage)
	},
	beforeDestroy () {
		window.removeEventListener('message', this.onMessage)
	},
	methods: {
		loaded () {
			this.loading = false
		},
		onMessage (event) {
			if (event.data.action === 'router.push' && event.data.location) {
				this.$router.push(event.data.location)
			} else {
				console.log('Received unknown message from iframe', event.data)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-iframe-page
	flex: auto
	height: auto  // 100% breaks safari
	display: flex
	flex-direction: column
	position: relative
</style>
