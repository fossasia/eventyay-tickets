<template lang="pug">
.v-presentation-question(v-if="pinnedQuestion")
	.question
		| {{ pinnedQuestion.content }}
	.info
		.votes
			.mdi.mdi-thumb-up
			.vote-count {{ pinnedQuestion.score }}
		.user(v-if="sender")
			avatar(:user="sender", :size="64")
			.username {{ senderDisplayName }}
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import Avatar from 'components/Avatar'

export default {
	components: { Avatar },
	props: {
		room: Object
	},
	data () {
		return {
		}
	},
	computed: {
		...mapState('chat', ['usersLookup']),
		...mapGetters('question', ['pinnedQuestion']),
		sender () {
			return this.usersLookup[this.pinnedQuestion.sender]
		},
		senderDisplayName () {
			return this.sender.profile?.display_name ?? this.pinnedQuestion.sender
		},
	},
	watch: {
		pinnedQuestion: 'fetchSender'
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		fetchSender () {
			console.log(this.pinnedQuestion)
			this.$store.dispatch('chat/fetchUsers', [this.pinnedQuestion.sender])
		}
	}
}
</script>
<style lang="stylus">
.v-presentation-question
	.question
		font-size: 36px
		font-weight: 500
	.info
		display: flex
		justify-content: space-between
		align-items: center
		align-self: stretch
		padding: 8px 16px
		.votes
			display: flex
			.mdi
				font-size: 24px
				color: $clr-secondary-text-light
			.vote-count
				margin: 0 0 0 8px
				font-size: 24px
		.user
			display: flex
			align-items: center
			.username
				margin: 0 0 0 8px
</style>
