<template lang="pug">
.c-contact-requests
	.header
		h2 {{ $t("ContactRequests:headline:text") }}
	.contact-requests-list
		.header
			.user {{ $t("ContactRequests:from:label") }}
			.exhibitor {{ $t("ContactRequests:to:label") }}
			.timestamp {{ $t("ContactRequests:at:label") }}
			.state {{ $t("ContactRequests:state:label") }}
			.staff {{ $t("ContactRequests:staff:label") }}
			.actions
		.tbody(v-scrollbar.y="")
			.contact-request.table-row(v-for="contactRequest of sortedContactRequests")
				.user
					avatar.avatar(:user="contactRequest.user", :size="32")
					.name {{ contactRequest.user.profile.display_name }}
				.exhibitor {{ contactRequest.exhibitor.name }}
				.timestamp {{ moment(contactRequest.timestamp).format('L LT') }}
				.state {{ contactRequest.state }}
				.staff
					template(v-if="contactRequest.answered_by")
						avatar.avatar(:user="contactRequest.answered_by", :size="32")
						.name {{ contactRequest.answered_by.profile.display_name }}
					span(v-else) –
				.actions
					.placeholder.mdi.mdi-dots-horizontal
					bunt-button.btn-open-dm(@click="$store.dispatch('chat/openDirectMessage', {users: [contactRequest.user]})") {{ $t("ContactRequests:message:label") }}
</template>
<script>
import { mapState } from 'vuex'
import Avatar from 'components/Avatar'
import moment from 'moment'
export default {
	components: { Avatar },
	data () {
		return {
			moment
		}
	},
	computed: {
		...mapState('exhibition', ['contactRequests']),
		sortedContactRequests () {
			return this.contactRequests.slice().sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
		}
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
@import '~styles/flex-table'

.c-contact-requests
	display: flex
	flex-direction: column
	background-color: $clr-white
	min-height: 0
	.header
		height: 56px
		border-bottom: border-separator()
		padding: 0 16px
		display: flex
		align-items: center
		> *
			margin: 0
	.contact-requests-list
		flex-table()
		.user, .staff
			flex: 1
			display: flex
			align-items: center
			.avatar
				width: 32px
				margin: 0 4px 0 0
			.name
				flex: auto
		.exhibitor
			width: 160px
			ellipsis()
		.timestamp
			width: 160px
		.state
			width: 64px
		.actions
			flex: none
			width: 260px
			padding: 0 24px 0 0
			display: flex
			align-items: center
			justify-content: flex-end
			.placeholder
				flex: none
				color: $clr-secondary-text-light
			.btn-open-dm
				button-style(style: clear)
		.contact-request:not(:hover)
			.actions .bunt-button
				display: none
		.contact-request:hover
			.actions .placeholder
				display: none
</style>
