import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		questions: null
	},
	getters: {
	},
	mutations: {

	},
	actions: {
		async changeRoom ({state}, room) {
			state.questions = null
			if (room.modules.some(module => module.type === 'question')) {
				state.questions = await api.call('question.list', {room: room.id})
			}
		},
		submitQuestion ({state, rootState}, question) {
			return api.call('question.ask', {room: rootState.activeRoom.id, content: question})
		},
		approveQuestion ({state, rootState}, question) {
			return api.call('question.update', {room: rootState.activeRoom.id, id: question.id, state: 'visible'})
			// update handled in create_or_update
			// TODO error handling
		},
		deleteQuestion ({state, rootState}, question) {
			return api.call('question.delete', {room: rootState.activeRoom.id, id: question.id})
			// update handled in api::question.deleted
			// TODO error handling
		},
		'api::question.created_or_updated' ({state}, {question}) {
			const existingQuestion = state.questions.find(q => q.id === question.id)
			if (existingQuestion) {
				// assume all keys are already in place
				Object.assign(existingQuestion, question)
			} else {
				state.questions.push(question)
			}
		},
		'api::question.deleted' ({state}, {id}) {
			const questionIndex = state.questions.findIndex(q => q.id === id)
			if (questionIndex > -1) {
				state.questions.splice(questionIndex, 1)
			}
		}
	}
}
