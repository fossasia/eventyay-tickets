<template lang="pug">
.c-iframe-blocker
	iframe(v-if="showIframe", :src="src", v-bind="$attrs", v-on="$listeners")
	.consent-blocker(v-else)
		.warning This content is hosted by a third party on
		.domain {{ domain }}
		.toc(v-if="config.policy_url") By showing this external content you accept their #[a(:href="config.policy_url") terms and conditions].
		bunt-button#btn-show(@click="showOnce") Show external content
		bunt-checkbox(name="remember", v-model="remember") Remember my choice
</template>
<script>
import store from 'store'

export default {
	inheritAttrs: false,
	props: {
		src: String
	},
	data () {
		return {
			showingOnce: false,
			remember: false
		}
	},
	computed: {
		domain () {
			if (typeof this.src !== 'string') return
			return new URL(this.src).host
		},
		config () {
			console.log(store.state.world.iframe_blockers, this.domain)
			for (const [domain, domainConfig] of Object.entries(store.state.world.iframe_blockers)) {
				if (this.domain === domain || this.domain.endsWith('.' + domain)) return domainConfig
			}
			return store.state.world.iframe_blockers.default
		},
		showIframe () {
			return this.showingOnce ||
				store.state.unblockedIframeDomains.has(this.domain) ||
				!this.config.enabled
		}
	},
	async created () {},
	async mounted () {
		await this.$nextTick()
	},
	methods: {
		showOnce () {
			if (this.remember) {
				store.dispatch('unblockIframeDomain', this.domain)
			}
			this.showingOnce = true
		}
	}
}
</script>
<style lang="stylus">
.c-iframe-blocker
	flex: auto
	display: flex
	iframe
		height: 100%
		width: 100%
		position: absolute
		top: 0
		left: 0
		border: none
		flex: auto // because safari
	.consent-blocker
		flex: auto
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		gap: 16px
		background-color: $clr-grey-800
		color: $clr-primary-text-dark
		.warning
			font-size: 20px
		.domain
			font-family: monospace
			font-size: 24px
		.toc
			font-size: 16px
			a
				color: $clr-primary-text-dark
				text-decoration: underline
				&:hover
					color: $clr-secondary-text-dark
		.bunt-checkbox
			label
				font-size: 20px
			&:not(.checked) .bunt-checkbox-box
				border-color: $clr-primary-text-dark
		+above('s')
			#btn-show
				margin-top: 24px
				themed-button-primary(size: large)
		+below('s')
			gap: 8px
			.warning, .domain
				font-size: 12px
			.toc
				font-size: 10px
			#btn-show
				margin-top: 8px
				themed-button-primary()
			.bunt-checkbox
				label
					font-size: 16px
</style>
