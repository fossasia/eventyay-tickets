<template lang="pug">
.c-question(:class="{queued: question.state === 'mod_queue', 'has-voted': question.voted, pinned: question.is_pinned, archived: question.state === 'archived', managing: isManaging}")
	.moderation-block(v-if="question.state === 'mod_queue'")
		bunt-icon-button(:disabled="!isManaging", :tooltip="isManaging ? $t('Question:moderation-approve-button:label') : $t('Question:attendee-awaiting-approval:label')", tooltip-placement="right", :tooltip-fixed="true", @click="doAction('approve')") {{ isManaging ? 'eye-check' : 'eye-off' }}
	.votes(v-else, @click="vote")
		.mdi.mdi-menu-up.upvote(v-if="!isManaging")
		.vote-count {{ question.score }}
		| {{ $t('Question:vote-count:label') }}
	.content {{ question.content }}
	menu-dropdown(v-if="isManaging && hasPermission('room:question.moderate')", v-model="showModerationMenu", strategy="fixed")
		template(v-slot:button="{toggle}")
			bunt-icon-button#btn-menu-toggle(@click="toggle") dots-vertical
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
	min-height: 72px
	.moderation-block
		flex: none
		width: 56px
		box-sizing: border-box
		display: flex
		align-items: center
		justify-content: center
		.bunt-icon-button
			icon-button-style(style: clear)
			height: 48px
			line-height: @height
			width: @height
			.bunt-icon
				color: $clr-deep-orange-800
				font-size: 28px
				height: 48px
				line-height: @height
				opacity: 1
	.votes
		flex: none
		width: 56px
		box-sizing: border-box
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
	&.has-voted
		.votes
			color: $clr-green-700
			.vote-count
				color: $clr-green-800
	&.pinned
		border: 4px solid var(--clr-primary)
		border-bottom: border-separator()
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
		z-index: 102
		#btn-menu-toggle
			display: none
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
			#btn-menu-toggle
				display: block
</style>
