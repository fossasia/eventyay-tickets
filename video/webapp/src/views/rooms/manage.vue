<template lang="pug">
.c-room-manager
	.schedule
	.polls(v-if="modules['poll']")
		.header
			h3 Polls
			.actions
				bunt-button#btn-create-poll(@click="pollQuestion = ''; pollOptions = []; showCreatePollPrompt = true") Create Poll
				bunt-icon-button(@click="showUrlPopup('poll')") presentation

		polls(:module="modules['poll']")
	.questions(v-if="modules['question']")
		.header
			h3 Questions
			.actions
				bunt-icon-button(@click="showUrlPopup('question')") presentation
				menu-dropdown(v-if="hasPermission('room:question.moderate')", v-model="showQuestionsMenu", strategy="fixed")
					template(v-slot:button="{toggle}")
						bunt-icon-button(@click="toggle") dots-vertical
					template(v-slot:menu)
						.archive-all(@click="$store.dispatch('question/archiveAll')") {{ $t('Questions:moderator-actions:archive-all:label') }}
		questions(:module="modules['question']")
	.chat(v-if="modules['chat.native']")
		.header
			h3 Chat
			bunt-icon-button(@click="showUrlPopup('chat')") presentation
		chat(:room="room", :module="modules['chat.native']", mode="compact", :key="room.id")
	.ui-background-blocker(v-if="showPresentationUrlFor", @click="showPresentationUrlFor = null")
	.url-popup(v-if="showPresentationUrlFor", ref="urlPopup", :class="{'url-copied': copiedUrl}")
		.copy-success(v-if="copiedUrl") Copied!
		template(v-else)
			.copy-url
				bunt-input(ref="urlInput", name="presentation-url", :readonly="true", :value="getPresentationUrl(showPresentationUrlFor)")
				bunt-button(@click="copyUrl") Copy
			.hint This url contains your personal token.
				br
				| Don't make this url publicly accessible!
	transition(name="prompt")
		// TODO less hacks
		prompt.create-poll-prompt(v-if="showCreatePollPrompt")
			.content
				h1 Create a Poll
				bunt-input(name="poll-question", label="Question", v-model="pollQuestion")
				bunt-input(v-for="(option, index) of pollOptions", :name="`poll-option-${index}`", :label="`Option ${index + 1}`", v-model="option.content")
				bunt-button(@click="pollOptions.push({content: ''})") Add Option
				bunt-button#btn-create-poll(@click="$store.dispatch('poll/createPoll', {content: pollQuestion, options: pollOptions}) ; showCreatePollPrompt = false") Create Poll
</template>
<script>
// TODO
// - handle video better (pause, completely cancel? preserve bandwidth?)

import {mapGetters, mapState} from 'vuex'
import { createPopper } from '@popperjs/core'
import Chat from 'components/Chat'
import MenuDropdown from 'components/MenuDropdown'
import Polls from 'components/Polls'
import Prompt from 'components/Prompt'
import Questions from 'components/Questions'

export default {
	name: 'RoomManager',
	components: { Chat, MenuDropdown, Polls, Prompt, Questions },
	props: {
		room: Object,
		modules: Object
	},
	provide: {
		isManaging: true
	},
	data () {
		return {
			showPresentationUrlFor: null,
			copiedUrl: false,
			showQuestionsMenu: false,
			showCreatePollPrompt: false,
			pollQuestion: '',
			pollOptions: []
		}
	},
	computed: {
		...mapState(['world', 'token']),
		...mapGetters(['hasPermission']),
		...mapGetters('schedule', ['sessions', 'sessionsScheduledNow'])
	},
	methods: {
		async showUrlPopup (type) {
			this.showPresentationUrlFor = type
			await this.$nextTick()
			createPopper(event.target, this.$refs.urlPopup, {
				placement: 'bottom-end',
				modifiers: [
					{name: 'offset', options: {offset: [16, 12]}}
				]
			})
		},
		getPresentationUrl (type) {
			console.log(type)
			return window.location.origin + this.$router.resolve({name: `presentation-mode:${type}`}).href + '#token=' + this.token
		},
		copyUrl () {
			this.$refs.urlInput.$refs.input.select()
			document.execCommand('copy')
			this.copiedUrl = true
			setTimeout(() => {
				this.copiedUrl = false
				this.showPresentationUrlFor = null
			}, 600)
		}
	}
}
</script>
<style lang="stylus">
.c-room-manager
	display: flex
	min-height: 0
	flex: auto
	.schedule
		flex: auto
		margin-top: 360px
		padding: 16px
		h3
			margin: 0
	.chat, .questions, .polls
		display: flex
		flex-direction: column
		min-height: 0
		width: var(--chatbar-width)
		border-left: border-separator()
		.header
			display: flex
			justify-content: space-between
			align-items: center
			height: 56px
			border-bottom: border-separator()
			padding: 0 16px
			.actions
				display: flex
				gap: 8px
				align-items: center
			.bunt-icon-button
				icon-button-style(style: clear)
		.c-chat
			min-height: 0
	.polls
		#btn-create-poll
			themed-button-primary()

	.url-popup
		card()
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		width: var(--chatbar-width)
		height: 140px
		z-index: 1000
		transition: background-color .2s ease
		.copy-url
			display: flex
			align-items: center
			gap: 8px
			margin-bottom: 16px
			.bunt-input
				input-style(size: compact)
				padding: 0
				flex: auto
			.bunt-button
				themed-button-primary()
				flex: none
		.hint
			text-align: center
			color: $clr-secondary-text-light
		&.url-copied
			background-color: $clr-success
			color: $clr-primary-text-dark
		.copy-success
			font-size: 24px
			font-weight: 500
	.create-poll-prompt .content
		display: flex
		flex-direction: column
		align-items: center
		#btn-create-poll
			themed-button-primary()
			margin: 16px
</style>
