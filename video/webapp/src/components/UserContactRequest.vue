<template lang="pug">
.c-user-contact-request
	.exhibitor {{ request.exhibitor.name }}
	.prompt
		.timer(v-if="timer > 0") {{ $t('ContactRequest:request:text') }} {{ timer }}s
		.timer(v-else) {{ $t('ContactRequest:timeout:text') }}
		.controls
			bunt-button#btn-cancel(@click="cancel") {{ $t('ContactRequest:dismiss-button:label') }}
</template>
<script>
import api from 'lib/api'

export default {
	props: {
		request: Object,
	},
	data () {
		return {
			timer: 30,
		}
	},
	methods: {
		async cancel () {
			if (this.timer > 0) await api.call('exhibition.contact_cancel', {contact_request: this.request.id})
			this.$store.dispatch('exhibition/closeContactRequest', this.request)
		},
	},
	watch: {
		timer: {
			async handler (value) {
				if (value > 0) {
					setTimeout(() => { this.timer-- }, 1000)
				} else {
					await api.call('exhibition.contact_cancel', {contact_request: this.request.id})
				}
			},
			immediate: true
		}
	}
}
</script>
<style lang="stylus">
.c-user-contact-request
	position: fixed
	top: 0
	left: calc(50% - 240px)
	width: 480px
	padding: 16px
	box-sizing: border-box
	text-align: center
	font-weight: 600
	font-size: 20px
	background-color:  $clr-grey-50
	border: border-separator()
	border-radius: 0 0 4px 4px
	z-index: 1000
	.exhibitor
		text-align: center
		margin-bottom: 8px
	.prompt
		display: flex
		justify-content: space-between
		.controls
			display: flex
			button
				margin-left: 8px
				align-self: flex-end
			#btn-primary
				background-color: $clr-green-300
			#btn-cancel
				background-color: $clr-red-300

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
