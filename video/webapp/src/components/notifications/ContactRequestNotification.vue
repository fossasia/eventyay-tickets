<template lang="pug">
.c-contact-request-notification(v-if="showNotification")
	bunt-icon-button#btn-close(@click="close") close
	.details {{ $t('ContactRequest:notification:text') }} #[br] #[span.exhibitor {{ contactRequest.exhibitor.name }}]
	.user
		avatar(:user="contactRequest.user", :size="36")
		.display-name {{ contactRequest.user ? contactRequest.user.profile.display_name : '' }}
	.actions
		bunt-button#btn-accept(@click="accept") {{ $t('ContactRequest:accept-button:label') }}
	.timer
		#timer-bar
</template>
<script>
import Avatar from 'components/Avatar'
import moment from 'moment'
import notification from 'lib/notification'
import { getIdenticonSvgUrl } from 'lib/identicon'

export default {
	components: { Avatar },
	props: {
		contactRequest: Object
	},
	data () {
		return {
			showNotification: true,
			timer: moment(this.contactRequest.timestamp).diff(moment(), 'seconds'),
			desktopNotification: null
		}
	},
	computed: {},
	created () {},
	mounted () {
		this.$nextTick(() => {
			document.getElementById('timer-bar').style.animationDelay = this.timer + 's'
		})
		this.handleDesktopNotification()
	},
	destroyed () {
		this.desktopNotification?.close()
	},
	methods: {
		close () {
			this.showNotification = false
			this.desktopNotification?.close()
		},
		accept () {
			this.$store.dispatch('exhibition/acceptContactRequest', this.contactRequest)
		},
		handleDesktopNotification () {
			const title = (this.contactRequest.user ? this.contactRequest.user.profile.display_name : '')
			const text = this.$t('ContactRequest:notification:text') + ' ' + this.contactRequest.exhibitor.name
			const img = this.getAvatar()
			this.desktopNotification = notification(title, text, () => { this.close() }, () => { this.accept() }, img)
		},
		getAvatar () {
			if (this.contactRequest.user.profile?.avatar?.url) {
				return this.contactRequest.user.profile?.avatar?.url
			} else {
				const canvas = document.createElement('canvas')
				canvas.height = 192
				canvas.width = 192
				const img = document.createElement('img')
				img.src = getIdenticonSvgUrl(this.contactRequest.user.profile?.avatar?.identicon ?? this.contactRequest.user.profile?.identicon ?? this.contactRequest.user.id)
				const ctx = canvas.getContext('2d')
				// TODO use onload?
				ctx.drawImage(img, 0, 0, 192, 192)
				return canvas.toDataURL()
			}
		}
	}
}
</script>
<style lang="stylus">
.c-contact-request-notification
	card()
	display: flex
	flex-direction: column
	margin: 4px 0
	padding: 8px
	#btn-close
		icon-button-style(style: clear)
		position: absolute
		right: 8px
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
		#timer-bar
			height: 100%
			background-color: $clr-primary
			animation: timerBar linear
			animation-duration 30s
			animation-fill-mode: forwards
		@keyframes timerBar
			0% { width: 100% }
			100% { width: 0 }
</style>
