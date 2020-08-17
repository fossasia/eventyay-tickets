<template lang="pug">
prompt.c-contact-exhibitor-prompt(@close="cancel", :allowCancel="false")
	.content
		img.logo(:src="exhibitor.logo")
		.exhibitor {{ exhibitor.name }}
		template(v-if="timer > 0")
			.timer-explanation {{ $t('ContactRequest:request:text') }}
			.timer
				svg.timer-ring(:style="{'--timer': 1 - timer / 30}")
					circle(cx="75.5", cy="75.5", r="60")
				.timer-text {{ timer }}s
		.timer-explanation(v-else) {{ $t('ContactRequest:timeout:text') }}
		.actions
			bunt-button#btn-cancel(@click="cancel") {{ $t('ContactRequest:dismiss-button:label') }}
</template>
<script>
import api from 'lib/api'
import Prompt from 'components/Prompt'

export default {
	props: {
		exhibitor: Object,
	},
	components: { Prompt },
	data () {
		return {
			timer: 31,
			request: null
		}
	},
	async created () {
		// TODO error handling
		this.tickTimer()
		this.request = (await api.call('exhibition.contact', {exhibitor: this.exhibitor.id})).contact_request
	},
	beforeDestroy () {
		clearTimeout(this.ticker)
	},
	methods: {
		async tickTimer () {
			if (this.timer > 0) {
				this.timer--
				this.ticker = setTimeout(this.tickTimer, 1000)
			} else {
				await api.call('exhibition.contact_cancel', {contact_request: this.request.id})
			}
		},
		async cancel () {
			if (this.timer > 0) await api.call('exhibition.contact_cancel', {contact_request: this.request.id})
			this.$emit('close')
		},
	}
}
</script>
<style lang="stylus">
.c-contact-exhibitor-prompt
	.content
		display: flex
		flex-direction: column
		padding: 16px
		align-items: center
	img.logo
		object-fit: contain
		width: 280px
		height: 280px
		max-height: 280px
	.exhibitor
		text-align: center
		font-size: 20px
		font-weight: 500
		margin: 8px 0
	.timer-explanation
		text-align: center
		white-space: pre-wrap
		margin: 8px 0
	.timer
		position: relative
		display: flex
		.timer-ring
			width: 150px
			height: @width
			$circumference = 60 * 2 * PI
			circle
				fill: none
				stroke: var(--clr-primary)
				stroke-width: 8.5px
				stroke-dasharray: $circumference $circumference
				stroke-dashoffset: "calc(-1 * var(--timer) * %s)" % $circumference
				transform: rotate(-90deg)
				transform-origin: 50% 50%
				transition: stroke-dashoffset 1s linear
		.timer-text
			position: absolute
			top: 50%
			left: 50%
			transform: translate(-50%, -50%)
			font-size: 18px
	.actions
		align-self: flex-end
		display: flex
		#btn-primary
			background-color: $clr-green-300
		#btn-cancel
			button-style(style: clear, color: $clr-danger)

+below('m')
	.c-user-contact-request
		left: calc(50% - 150px)
		width: 300px
		.prompt
			flex-wrap: wrap
			align-items: center
			.controls
				width: 100%
				justify-content: center

</style>
