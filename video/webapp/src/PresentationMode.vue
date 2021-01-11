<template lang="pug">
#presentation-mode(:style="[style, themeVariables]")
	.fatal-indicator.mdi.mdi-alert-octagon(v-if="fatalError || fatalConnectionError", :title="errorMessage")
	.content(v-else-if="world")
		template(v-if="pinnedQuestion")
			.question
				| {{ pinnedQuestion.content }}
			.info
				.votes
					.mdi.mdi-thumb-up
					.vote-count {{ pinnedQuestion.score }}
				.user(v-if="sender")
					avatar(:user="sender", :size="64")
					.username {{ senderDisplayName }}

	bunt-progress-circular(v-else, size="small")

</template>
<script>
import { mapState, mapGetters } from 'vuex'
import { themeVariables } from 'theme'
import api from 'lib/api'
import Avatar from 'components/Avatar'

const SLIDE_WIDTH = 960
const SLIDE_HEIGHT = 700

export default {
	components: { Avatar },
	data () {
		return {
			themeVariables,
			scale: 1
		}
	},
	computed: {
		...mapState(['fatalConnectionError', 'fatalError', 'connected', 'world', 'rooms']),
		...mapState('chat', ['usersLookup']),
		...mapGetters('question', ['pinnedQuestion']),
		errorMessage () {
			return this.fatalConnectionError?.code || this.fatalError?.message
		},
		room () {
			return this.rooms?.find(room => room.id === this.$route.params.roomId) || this.rooms?.[0]
		},
		style () {
			return {
				'--scale': this.scale.toFixed(1)
			}
		},
		sender () {
			return this.usersLookup[this.pinnedQuestion.sender]
		},
		senderDisplayName () {
			return this.sender.profile?.display_name ?? this.pinnedQuestion.sender
		},
	},
	watch: {
		room () {
			this.$store.dispatch('changeRoom', this.room)
			api.call('room.enter', {room: this.room.id})
		},
		pinnedQuestion: 'fetchSender'
	},
	mounted () {
		window.addEventListener('resize', this.computeScale)
		this.computeScale()
	},
	beforeDestroy () {
		window.removeEventListener('resize', this.computeScale)
	},
	methods: {
		computeScale () {
			const width = document.body.offsetWidth
			const height = document.body.offsetHeight
			this.scale = Math.min(width / SLIDE_WIDTH, height / SLIDE_HEIGHT)
		},
		fetchSender () {
			console.log(this.pinnedQuestion)
			this.$store.dispatch('chat/fetchUsers', [this.pinnedQuestion.sender])
		}
	}
}
</script>
<style lang="stylus">
#presentation-mode
	height: 100%
	display: flex
	flex-direction: column
	justify-content: center
	align-items: center
	> .bunt-progress-circular, > .fatal-indicator
		position: fixed
		top: 100%
		left: 0
		transform: translate(4px, calc(-100% - 4px))
	> .fatal-indicator
		color: $clr-danger
		font-size: 1vw

	.content
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		width: 960px
		height: 700px
		flex: none
		transform: scale(var(--scale)) translateZ(0)
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
