<template lang="pug">
.c-polls
	.polls(v-if="polls && module.config.active", :class="{'can-vote': hasPermission('room:poll.vote')}", v-scrollbar.y="")
		.empty-placeholder(v-if="sortedPolls.length === 0") {{ $t('Questions:empty-placeholder') }}
		poll(v-for="poll of sortedPolls", :poll="poll")
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import Poll from './Poll'

export default {
	components: { Poll },
	props: {
		module: {
			type: Object,
			required: true
		}
	},
	inject: {
		isManaging: {
			default: false
		}
	},
	data () {
		return {
			hasLoaded: false
		}
	},
	computed: {
		...mapState('poll', ['polls']),
		...mapGetters(['hasPermission']),
		sortedPolls () {
			if (!this.polls) return
			let polls
			if (this.isManaging) {
				polls = this.polls.slice()
			} else {
				// filter polls for moderators looking at the list like a normal attendee
				polls = this.polls.filter(p => ['open', 'closed'].includes(p.state))
			}

			const weight = p => p.is_pinned + (p.state !== 'archived') + (p.state === 'draft') // assume archived and draft cannot be pinned
			polls.sort((a, b) => weight(b) - weight(a) || new Date(b.timestamp) - new Date(a.timestamp))
			return polls
		}
	},
	watch: {
		sortedPolls () {
			// HACK suppress firing event on `poll.list`
			if (this.hasLoaded) {
				this.$emit('change')
			} else {
				this.hasLoaded = true
			}
		}
	}
}
</script>
<style lang="stylus">
.c-polls
	display: flex
	flex-direction: column
	min-height: 0
	flex: auto
	.polls
		display: flex
		flex-direction: column
</style>
