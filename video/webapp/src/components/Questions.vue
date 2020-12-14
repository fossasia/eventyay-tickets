<template lang="pug">
.c-questions
	.asking-form(v-if="showAskingForm")
		bunt-input-outline-container(:label="$t('Questions:asking-form:label')")
			textarea(v-model="question", slot-scope="{focus, blur}", @focus="focus", @blur="blur")
		.actions
			bunt-button#btn-cancel(@click="showAskingForm = false") {{ $t('Prompt:cancel:label') }}
			bunt-button#btn-submit-question(@click="submitQuestion") {{ $t('Questions:asking-form:submit') }}
	template(v-else)
		bunt-button#btn-ask-question(v-if="hasPermission('room:question.ask')", @click="question = ''; showAskingForm = true") {{ $t('Questions:ask-question-button:label') }}
		//- v-else ?
	.questions(v-if="questions", :class="{'can-vote': hasPermission('room:question.vote')}", v-scrollbar.y="")
		.empty-placeholder(v-if="questions.length === 0") {{ $t('Questions:empty-placeholder') }}
		question(v-for="question of questions", :question="question")
		//- TODO sort by state?
</template>
<script>
import { mapState, mapGetters } from 'vuex'
import Question from './Question'

export default {
	components: { Question },
	data () {
		return {
			question: '',
			showAskingForm: false,
			hasLoaded: false
		}
	},
	computed: {
		...mapState('question', ['questions']),
		...mapGetters(['hasPermission'])
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
	#btn-ask-question
		themed-button-primary()
		margin: 16px 0
		padding: 0 32px
		align-self: center
	.empty-placeholder
		margin-top: 16px
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
		//
</style>
