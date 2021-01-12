<template lang="pug">
.c-questions
	.deactivated(v-if="!module.config.active")
		| {{ $t('Questions:deactivated-placeholder') }}
	template(v-else)
		.asking-form(v-if="showAskingForm")
			bunt-input-outline-container(:label="$t('Questions:asking-form:label')")
				textarea(v-model="question", slot-scope="{focus, blur}", @focus="focus", @blur="blur")
			.actions
				bunt-button#btn-cancel(@click="showAskingForm = false") {{ $t('Prompt:cancel:label') }}
				bunt-button#btn-submit-question(@click="submitQuestion") {{ $t('Questions:asking-form:submit') }}
		template(v-else)
			bunt-button#btn-ask-question(v-if="hasPermission('room:question.ask')", @click="question = ''; showAskingForm = true") {{ $t('Questions:ask-question-button:label') }}
			//- v-else ?
	.questions(v-if="questions && (module.config.active || hasPermission('room:question.moderate'))", :class="{'can-vote': hasPermission('room:question.vote')}", v-scrollbar.y="")
		.empty-placeholder(v-if="questions.length === 0") {{ $t('Questions:empty-placeholder') }}
		question(v-for="question of sortedQuestions", :question="question")
	.moderator-actions(v-if="hasPermission('room:question.moderate')")
		bunt-button.btn-archive-all(@click="$store.dispatch('question/archiveAll')") {{ $t('Questions:moderator-actions:archive-all:label') }}
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import Question from './Question'

export default {
	components: { Question },
	props: {
		module: {
			type: Object,
			required: true
		}
	},
	data () {
		return {
			question: '',
			showAskingForm: false,
			hasLoaded: false
		}
	},
	computed: {
		...mapState('question', ['questions']),
		...mapGetters(['hasPermission']),
		sortedQuestions () {
			const questions = this.questions.slice()
			const weight = q => q.is_pinned + (q.state !== 'archived') + (q.state === 'mod_queue') // assume archived and mod_queue cannot be pinned
			questions.sort((a, b) => weight(b) - weight(a) || new Date(b.timestamp) - new Date(a.timestamp))
			return questions
		}
	},
	watch: {
		questions () {
			// HACK suppress firing event on `question.list`
			if (this.hasLoaded) {
				this.$emit('change')
			} else {
				this.hasLoaded = true
			}
		}
	},
	methods: {
		async submitQuestion () {
			await this.$store.dispatch('question/submitQuestion', this.question) // TODO error handling
			this.question = ''
			this.showAskingForm = false
		}
	}
}
</script>
<style lang="stylus">
.c-questions
	display: flex
	flex-direction: column
	min-height: 0
	flex: auto
	.deactivated
		text-align: center
		margin: 32px 0
		color: $clr-secondary-text-light
	#btn-ask-question
		themed-button-primary()
		margin: 16px 0
		padding: 0 32px
		align-self: center
	.empty-placeholder
		margin-top: 16px
		padding: 0 16px
		color: $clr-secondary-text-light
		align-self: center
	.asking-form
		margin: 8px 0
		padding: 0 8px
		display: flex
		flex-direction: column
		border-bottom: border-separator()
		.bunt-input-outline-container
			textarea
				background-color: transparent
				border: none
				outline: none
				resize: vertical
				min-height: 64px
				padding: 0 8px
				font-family: $font-stack
		.actions
			align-self: flex-end
			margin: 16px 0
		#btn-cancel
			themed-button-secondary()
			margin: 0 16px
		#btn-submit-question
			themed-button-primary()
	.questions
		flex: auto
	.moderator-actions
		flex: none
		border-top: border-separator()
		display: flex
		height: 56px
		justify-content: flex-end
		align-items: center
		padding: 0 8px
</style>
