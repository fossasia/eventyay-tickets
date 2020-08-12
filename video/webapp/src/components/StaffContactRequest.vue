<template lang="pug">
.c-staff-contact-request
	.exhibitor {{ request.exhibitor.name }}
	.prompt
		.user
			avatar(:user="request.user", :size="28")
			span.display-name {{ request.user ? request.user.profile.display_name : '' }}
		.controls
			bunt-button#btn-cancel(@click="$store.dispatch('exhibition/dismissContactRequest', request)") {{ $t('ContactRequest:dismiss-button:label') }}
			bunt-button#btn-primary(@click="$store.dispatch('exhibition/acceptContactRequest', request)") {{ $t('ContactRequest:accept-button:label') }}
</template>
<script>
import Avatar from 'components/Avatar'

export default {
	props: {
		request: Object,
	},
	components: { Avatar },
}
</script>
<style lang="stylus">
.c-staff-contact-request
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
		.user
			display: flex
			align-items: center
			padding: 2px 16px 2px 0
			.display-name
				font-weight: 600
				color: $clr-secondary-text-light
				margin-left: 8px
		.controls
			display: flex
			button
				margin-left: 8px
			#btn-primary
				background-color: $clr-green-300
			#btn-cancel
				background-color: $clr-red-300

+below('m')
	.c-staff-contact-request
		left: calc(50% - 150px)
		width: 300px
		.prompt
			flex-wrap: wrap
			align-items: center
			.user
				width: 100%
				justify-content: center
			.controls
				width: 100%
				justify-content: center

</style>
