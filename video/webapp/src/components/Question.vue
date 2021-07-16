<template lang="pug">
.c-question(:class="{queued: hasPermission('room:question.moderate') && question.state === 'mod_queue', 'has-voted': question.voted, pinned: question.is_pinned, archived: question.state === 'archived', managing: isManaging}")
	.votes(@click="vote")
		.mdi.mdi-menu-up.upvote(v-if="!isManaging")
		.vote-count {{ question.score }}
		| {{ $t('Question:vote-count:label') }}
	.content {{ question.content }}
	menu-dropdown(v-if="isManaging && hasPermission('room:question.moderate')", v-model="showModerationMenu", strategy="fixed")
		template(v-slot:button="{toggle}")
			bunt-icon-button(@click="toggle") dots-vertical
		template(v-slot:menu)
			.approve-question(v-if="question.state === 'mod_queue'", @click="doAction('approve')") {{ $t('Question:moderation-menu:approve-question:label') }}
			.pin-question(v-if="question.state === 'visible' && !question.is_pinned", @click="doAction('pin')") {{ $t('Question:moderation-menu:pin-question:label') }}
			.unpin-question(v-if="question.state === 'visible' && question.is_pinned", @click="doAction('unpin')") {{ $t('Question:moderation-menu:unpin-question:label') }}
			.archive-question(v-if="question.state !== 'archived'", @click="doAction('archive')") {{ $t('Question:moderation-menu:archive-question:label') }}
			.unarchive-question(v-if="question.state === 'archived'", @click="doAction('unarchive')") {{ $t('Question:moderation-menu:unarchive-question:label') }}
			.delete-question(@click="doAction('delete')") {{ $t('Question:moderation-menu:delete-question:label') }}
</template>
<script>
import { mapGetters } from 'vuex'
import MenuDropdown from 'components/MenuDropdown'

export default {
	components: { MenuDropdown },
	props: {
		question: Object
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
		...mapGetters(['hasPermission'])
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		async vote () {
			this.$store.dispatch('question/vote', this.question)
		},
		async doAction (action) {
			await this.$store.dispatch(`question/${action}Question`, this.question)
			this.showModerationMenu = false
		}
	}
}
</script>
<style lang="stylus">
.c-question
	flex: none
	display: flex
	align-items: center
	border-bottom: border-separator()
	position: relative
	.votes
		display: flex
		flex-direction: column
		align-items: center
		padding: 8px
		color: $clr-secondary-text-light
		text-transform: uppercase
		font-size: 12px
		cursor: pointer
		user-select: none
		.mdi
			font-size: 38px
			line-height: 8px
		.vote-count
			font-family: 'Roboto-Condensed'
			font-weight: 200
			font-size: 32px
			line-height: 32px
			color: $clr-primary-text-light
			// TODO scaling for digits
	.content
		flex: auto
		margin: 8px
	&.queued
		$clr-queued = alpha($clr-black, .05)
		background: repeating-linear-gradient(-45deg, transparent, transparent 10px, $clr-queued 10px, $clr-queued 20px, transparent 20px)
		&::after
			content: 'needs approval'
			display: block
			position: absolute
			right: 8px
			top: 8px
			font-size: 12px
			color: $clr-deep-orange
			font-weight: 600
	&.has-voted
		.votes
			color: $clr-green-700
			.vote-count
				color: $clr-green-800
	&.pinned
		border: 4px solid var(--clr-primary)
		border-bottom: none
		border-top: none
	&.archived
		background-color: $clr-grey-200
		color: $clr-disabled-text-light
		.votes, .vote-count
			color: $clr-disabled-text-light
		&::after
			content: 'archived'
			display: block
			position: absolute
			right: 8px
			top: 8px
			font-size: 12px
			color: $clr-secondary-text-light
			font-weight: 600
	.c-menu-dropdown
		position: absolute
		top: 4px
		right: 4px
		display: none
		z-index: 102
		.bunt-icon-button
			icon-button-style()
			background-color: $clr-white
		.delete-question
			color: $clr-danger
			&:hover
				background-color: $clr-danger
				color: $clr-primary-text-dark
	&.managing
		position: relative
		.votes
			pointer-events: none
		&:hover
			background-color: $clr-grey-100
			.c-menu-dropdown
				display: block
</style>
