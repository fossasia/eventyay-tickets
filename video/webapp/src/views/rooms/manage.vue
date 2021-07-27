<template lang="pug">
.c-room-manager
	dashboard-layout
		panel.media
			media-source-placeholder
		panel.polls(v-if="modules['poll']")
			.header
				h3 Polls
				.actions
					bunt-button#btn-create-poll(@click="showCreatePollPrompt") Create Poll
					bunt-icon-button(@click="showUrlPopup('poll')") presentation
			polls(:module="modules['poll']", @edit="startEditingPoll")
		panel.questions(v-if="modules['question']")
			.header
				h3 Questions
				.actions
					bunt-icon-button(@click="showUrlPopup('question')") presentation
					menu-dropdown(v-if="hasPermission('room:question.moderate')", v-model="showingQuestionsMenu", strategy="fixed")
						template(v-slot:button="{toggle}")
							bunt-icon-button(@click="toggle") dots-vertical
						template(v-slot:menu)
							.archive-all(@click="$store.dispatch('question/archiveAll')") {{ $t('Questions:moderator-actions:archive-all:label') }}
			questions(:module="modules['question']")
		panel.chat(v-if="modules['chat.native']")
			.header
				h3 Chat
				bunt-icon-button(@click="showUrlPopup('chat')") presentation
			chat(:room="room", :module="modules['chat.native']", mode="compact", :key="room.id")
		panel.no-modules(v-if="Object.keys(modules).length === 1")
			p No modules to manage in this room
	.ui-background-blocker(v-if="showingPresentationUrlFor", @click="showingPresentationUrlFor = null")
	.url-popup(v-if="showingPresentationUrlFor", ref="urlPopup", :class="{'url-copied': copiedUrl}")
		.copy-success(v-if="copiedUrl") Copied!
		template(v-else)
			.copy-url
				bunt-input(ref="urlInput", name="presentation-url", :readonly="true", :value="getPresentationUrl(showingPresentationUrlFor)")
				bunt-button(@click="copyUrl") Copy
			.hint This url contains your personal token.
				br
				| Don't make this url publicly accessible!
	transition(name="prompt")
		// TODO less hacks
		prompt.create-poll-prompt(v-if="editedPoll", @close="editedPoll = null")
			.content
				h1 {{ editedPoll.id ? 'Edit Poll' : 'Create a Poll' }}
				.form-content
					bunt-input-outline-container(name="poll-question", label="Question")
						textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur", v-model="editedPoll.content")
					.option(v-for="(option, index) of editedPoll.options")
						bunt-input(:name="`poll-option-${index}`", :label="`Option ${index + 1}`", v-model="option.content")
						bunt-icon-button.btn-delete-poll-option(@click="editedPoll.options.splice(index, 1)") delete-outline
					bunt-button#btn-add-poll-option(@click="editedPoll.options.push({content: ''})") Add Option
				bunt-button#btn-submit-poll(@click="submitPoll") {{ editedPoll.id ? 'Save Poll' : 'Create Poll' }}
</template>
<script>
// TODO
// - handle video better (pause, completely cancel? preserve bandwidth?)

import {mapGetters, mapState} from 'vuex'
import { createPopper } from '@popperjs/core'
import DashboardLayout from 'components/dashboard-layout'
import Panel from 'components/dashboard-layout/Panel'
import Chat from 'components/Chat'
import MediaSourcePlaceholder from 'components/MediaSourcePlaceholder'
import MenuDropdown from 'components/MenuDropdown'
import Polls from 'components/Polls'
import Prompt from 'components/Prompt'
import Questions from 'components/Questions'

export default {
	name: 'RoomManager',
	components: { Chat, DashboardLayout, MediaSourcePlaceholder, MenuDropdown, Panel, Polls, Prompt, Questions },
	props: {
		room: Object,
		modules: Object
	},
	provide: {
		isManaging: true
	},
	data () {
		return {
			showingPresentationUrlFor: null,
			copiedUrl: false,
			showingQuestionsMenu: false,
			editedPoll: null
		}
	},
	computed: {
		...mapState(['world', 'token']),
		...mapGetters(['hasPermission']),
		...mapGetters('schedule', ['sessions', 'sessionsScheduledNow'])
	},
	methods: {
		async showUrlPopup (type) {
			this.showingPresentationUrlFor = type
			await this.$nextTick()
			createPopper(event.target, this.$refs.urlPopup, {
				placement: 'bottom-end',
				modifiers: [
					{name: 'offset', options: {offset: [16, 12]}}
				]
			})
		},
		showCreatePollPrompt () {
			this.editedPoll = {
				content: '',
				options: [{
					content: ''
				}, {
					content: ''
				}]
			}
		},
		startEditingPoll (poll) {
			// only clone relevant parts of the poll to not update too much
			this.editedPoll = {
				id: poll.id,
				content: poll.content,
				options: poll.options.map(o => Object.assign({}, o))
			}
		},
		submitPoll () {
			if (this.editedPoll.id) {
				this.$store.dispatch('poll/updatePoll', {
					poll: this.editedPoll,
					update: {
						content: this.editedPoll.content,
						options: this.editedPoll.options
					}
				})
			} else {
				this.$store.dispatch('poll/createPoll', this.editedPoll)
			}
			this.editedPoll = null
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
				this.showingPresentationUrlFor = null
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
		// margin-top: 360px
		// padding: 16px
		h3
			margin: 0
	.modules
		display: flex
		min-height: 0
	.chat, .questions, .polls, .no-modules
		display: flex
		flex-direction: column
		min-height: 0
		flex: 1 1 0px
		// width: var(--chatbar-width)
		// border-left: border-separator()
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
	.media .c-media-source-placeholder
		height: 360px
	.polls
		#btn-create-poll
			themed-button-primary()

	.no-modules
		align-items: center
		p
			color: $clr-secondary-text-light
			margin: 32px
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
		h1
			margin: 16px 0 8px 0
		.form-content
			display: flex
			flex-direction: column
			width: 336px
		.bunt-input-outline-container
			// TODO decopypaste
			textarea
				font-family: $font-stack
				font-size: 16px
				background-color: transparent
				border: none
				outline: none
				resize: vertical
				min-height: 64px

				padding: 0 8px
		.option
			display: flex
			align-items: baseline
			.bunt-input
				flex: auto
				input-style(size: compact)
			.btn-delete-poll-option
				icon-button-style()
				margin-left: 4px

		#btn-add-poll-option
			align-self: flex-start
			themed-button-secondary()
			margin: 16px 0 0 0
		#btn-submit-poll
			align-self: flex-end
			themed-button-primary()
			margin: 16px
	+below(1800px) // total guess
		flex-direction: column
		.schedule
			flex: none
			height: 56px
			border-bottom: border-separator()
		.modules
			justify-content: flex-end
</style>
