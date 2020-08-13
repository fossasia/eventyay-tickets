<template lang="pug">
.c-notifications(:class="{'has-background-media': hasBackgroundMedia}")
	contact-request-notification(v-for="contactRequest of openContactRequests", :contactRequest="contactRequest")
</template>
<script>
// TODO
// - scrolling
import { mapGetters } from 'vuex'
import ContactRequestNotification from './ContactRequestNotification'
export default {
	props: {
		hasBackgroundMedia: Boolean
	},
	components: { ContactRequestNotification },
	data () {
		return {
		}
	},
	computed: {
		...mapGetters('exhibition', ['openContactRequests'])
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-notifications
	position: fixed
	top: 3px
	right: 4px
	display: flex
	flex-direction: column
	width: 280px
	&.has-background-media
		top: 3px + 48px
</style>
