<template lang="pug">
.c-contact-request-notification.ui-notification
	bunt-icon-button#btn-close(@click="close") close
	.details {{ $t('ContactRequest:notification:text') }} #[br] #[span.exhibitor {{ contactRequest.exhibitor.name }}]
	.user
		avatar(:user="contactRequest.user", :size="36")
		.display-name {{ contactRequest.user ? contactRequest.user.profile.display_name : '' }}
	.actions
		bunt-button#btn-accept(@click="accept") {{ $t('ContactRequest:accept-button:label') }}
	.timer(:style="{'--late-start-gap': lateStartGap + 's'}")
</template>
<script>
import Avatar from 'components/Avatar'
import moment from 'moment'

export default {
	components: { Avatar },
	props: {
		contactRequest: Object
	},
	data () {
		return {
			lateStartGap: moment(this.contactRequest.timestamp).diff(moment(), 'seconds')
		}
	},
	methods: {
		close () {
			this.$store.dispatch('exhibition/dismissContactRequest', this.contactRequest)
		},
		accept () {
			this.$store.dispatch('exhibition/acceptContactRequest', this.contactRequest)
		}
	}
}
</script>
<style lang="stylus">
.c-contact-request-notification
	span.exhibitor
		font-weight: 500
	.user
		display: flex
		align-items: center
		margin: 12px 8px 0 8px
		.display-name
			margin-left: 4px
			ellipsis()
	.actions
		display: flex
		justify-content: flex-end
	#btn-accept
		themed-button-secondary()
	.timer
		display: block
		height: 3.5px
		&::before
			content: ''
			display: block
			height: 100%
			background-color: var(--clr-primary)
			animation: timerBar linear
			animation-duration 30s
			animation-fill-mode: forwards
			animation-delay: var(--late-start-gap)
		@keyframes timerBar
			0% { width: 100% }
			100% { width: 0 }
</style>
