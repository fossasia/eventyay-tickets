<template lang="pug">
.c-iframe-blocker
	iframe(v-if="showIframe", :src="src", v-bind="$attrs", v-on="$listeners")
	.consent-blocker(v-else)
		.warning This content is hosted by a third party on
		.domain {{ domain }}
		.toc By showing this external content you accept their #[a(href="#") terms and conditions].
		bunt-button#btn-show(@click="showOnce") Show external content
		bunt-checkbox(name="remember", v-model="remember") Remember my choice
</template>
<script>
// external content
export default {
	inheritAttrs: false,
	props: {
		src: String
	},
	data () {
		return {
			showIframe: false,
			remember: false
		}
	},
	computed: {
		domain () {
			if (typeof this.src !== 'string') return
			return new URL(this.src).host
		}
	},
	async created () {},
	async mounted () {
		await this.$nextTick()
		console.log(this)
	},
	methods: {
		showOnce () {
			this.showIframe = true
		},
		showAlways () {

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
		#btn-show
			margin-top: 24px
			themed-button-primary(size: large)
		.bunt-checkbox
			label
				font-size: 20px
			&:not(.checked) .bunt-checkbox-box
				border-color: $clr-primary-text-dark
</style>
