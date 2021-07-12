<template lang="pug">
.v-presentation-poll(v-if="pinnedPoll", :style="{'--total-votes': totalVotes}")
	.question
		| {{ pinnedPoll.content }}
	.option(v-for="option of pinnedPoll.options", :class="{'most-votes': optionsWithMostVotes.includes(option.id)}")
		.content {{ option.content }}
		.votes(:style="{'--votes': pinnedPoll.results[option.id]}") {{ totalVotes ? (pinnedPoll.results[option.id] / totalVotes * 100).toFixed() : 0 }}%
</template>
<script>
import { mapGetters } from 'vuex'
import Avatar from 'components/Avatar'

export default {
	components: { Avatar },
	props: {
		room: Object
	},
	computed: {
		...mapGetters('poll', ['pinnedPoll']),
		// TODO copypasta
		totalVotes () {
			if (!this.pinnedPoll.results) return 0
			return Object.values(this.pinnedPoll.results).reduce((acc, result) => acc + result, 0)
		},
		optionsWithMostVotes () {
			const sortedResults = Object.entries(this.pinnedPoll.results).slice().sort((a, b) => b[1] - a[1])
			const mostVotes = sortedResults[0][1]
			const optionsWithMostVotes = []
			for (const result of sortedResults) {
				if (result[1] !== mostVotes) break
				optionsWithMostVotes.push(result[0])
			}
			return optionsWithMostVotes
		}
	}
}
</script>
<style lang="stylus">
.v-presentation-poll
	.question
		font-size: 36px
		font-weight: 500
		margin-bottom: 32px
	.option
		font-size: 18px
		margin-bottom: 16px
		.votes
			display: flex
			padding: 8px 0
			align-items: center
			&::before
				content: ''
				display: block
				height: 20px
				background-color: $clr-grey-300
				width: calc(var(--votes) / var(--total-votes) * 100%)
				min-width: 4px
				margin-right: 4px
				border-radius: 8px
		&.most-votes
			.votes::before
				background-color: var(--clr-primary)
</style>
