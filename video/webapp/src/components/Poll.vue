<template lang="pug">
.c-poll(:class="{draft: poll.state === 'draft', 'has-voted': poll.answers, pinned: poll.is_pinned, archived: poll.state === 'archived', managing: isManaging}", :style="{'--total-votes': totalVotes}")
	.question {{ poll.content }}
	template(v-if="!isManaging && !poll.answers")
		bunt-button.btn-option(v-for="option of poll.options", @click="$store.dispatch('poll/vote', {poll, option})") {{ option.content }}
	template(v-else)
		.option(v-for="option of poll.options", :class="{'most-votes': optionsWithMostVotes.includes(option.id)}")
			.content {{ option.content }}
			.votes(:style="{'--votes': poll.results[option.id]}") {{ totalVotes ? (poll.results[option.id] / totalVotes * 100).toFixed() : 0 }}%
	menu-dropdown(v-if="isManaging && hasPermission('room:poll.manage')", v-model="showModerationMenu", strategy="fixed")
		template(v-slot:button="{toggle}")
			bunt-icon-button(@click="toggle") dots-vertical
		template(v-slot:menu)
			.open-poll(v-if="['draft', 'closed'].includes(poll.state)", @click="doAction('open')") {{ $t('Poll:moderation-menu:open-poll:label') }}
			.close-poll(v-if="poll.state === 'open'", @click="doAction('close')") {{ $t('Poll:moderation-menu:close-poll:label') }}
			.redraft-poll(v-if="poll.state === 'open'", @click="doAction('redraft')") {{ $t('Poll:moderation-menu:redraft-poll:label') }}
			.pin-poll(v-if="poll.state === 'open'", @click="doAction('pin')") {{ $t('Poll:moderation-menu:pin-poll:label') }}
			.archive-poll(v-if="poll.state !== 'archived'", @click="doAction('archive')") {{ $t('Poll:moderation-menu:archive-poll:label') }}
			.unarchive-poll(v-if="poll.state === 'archived'", @click="doAction('unarchive')") {{ $t('Poll:moderation-menu:unarchive-poll:label') }}
			.delete-poll(@click="doAction('delete')") {{ $t('Poll:moderation-menu:delete-poll:label') }}
</template>
<script>
import { mapGetters } from 'vuex'
import MenuDropdown from 'components/MenuDropdown'

export default {
	components: { MenuDropdown },
	props: {
		poll: Object
	},
	inject: {
		isManaging: {
			default: false
		}
	},
	data () {
		return {
			showModerationMenu: false
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		totalVotes () {
			if (!this.poll.results) return 0
			return Object.values(this.poll.results).reduce((acc, result) => acc + result, 0)
		},
		optionsWithMostVotes () {
			const sortedResults = Object.entries(this.poll.results).slice().sort((a, b) => b[1] - a[1])
			const mostVotes = sortedResults[0][1]
			const optionsWithMostVotes = []
			for (const result of sortedResults) {
				if (result[1] !== mostVotes) break
				optionsWithMostVotes.push(result[0])
			}
			return optionsWithMostVotes
		}
	},
	methods: {
		async vote () {
			this.$store.dispatch('question/vote', this.question)
		},
		async doAction (action) {
			await this.$store.dispatch(`poll/${action}Poll`, this.poll)
			this.showModerationMenu = false
		},
	}
}
</script>
<style lang="stylus">
.c-poll
	display: flex
	flex-direction: column
	padding: 16px
	border-bottom: border-separator()
	&.draft
		$clr-queued = alpha($clr-black, .05)
		background: repeating-linear-gradient(-45deg, transparent, transparent 10px, $clr-queued 10px, $clr-queued 20px, transparent 20px)
		&::after
			content: 'draft'
			display: block
			position: absolute
			right: 8px
			top: 8px
			font-size: 12px
			color: $clr-deep-orange
			font-weight: 600
	.question
		font-size: 16px
		font-weight: 500
		margin-bottom: 8px
	.btn-option
		margin-top: 8px
		button-style()
	.option
		.votes
			display: flex
			padding: 8px 0
			&::before
				content: ''
				display: block
				height: 16px
				background-color: $clr-grey-300
				width: calc(var(--votes) / var(--total-votes) * 100%)
				min-width: 4px
				margin-right: 4px
				border-radius: 8px
		&.most-votes
			.votes::before
				background-color: var(--clr-primary)
	.c-menu-dropdown
		position: absolute
		top: 4px
		right: 0
		display: none
		z-index: 102
		.bunt-icon-button
			icon-button-style()
			background-color: $clr-white
		.delete-poll
			color: $clr-danger
			&:hover
				background-color: $clr-danger
				color: $clr-primary-text-dark
	&.managing
		position: relative
		&:hover
			background-color: $clr-grey-100
			.c-menu-dropdown
				display: block
</style>
