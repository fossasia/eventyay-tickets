<template lang="pug">
.c-contact-request-notification
	.details Unanswered contact request to #[br] #[span.exhibitor {{ contactRequest.exhibitor.name }}] from:
	.user
		avatar(:user="contactRequest.user", :size="36")
		.display-name {{ contactRequest.user ? contactRequest.user.profile.display_name : '' }}
	.actions
		bunt-button#btn-accept(@click="$store.dispatch('exhibition/acceptContactRequest', contactRequest)") {{ $t('ContactRequest:accept-button:label') }}
</template>
<script>
import Avatar from 'components/Avatar'

export default {
	props: {
		contactRequest: Object
	},
	components: { Avatar },
	data () {
		return {
		}
	},
	computed: {},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-contact-request-notification
	card()
	display: flex
	flex-direction: column
	margin: 4px 0
	padding: 8px
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
</style>
