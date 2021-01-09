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
			if (!room) return
			if (room.modules.some(module => module.type === 'question')) {
				state.questions = await api.call('question.list', {room: room.id})
			}
		},
		submitQuestion ({state, rootState}, question) {
			return api.call('question.ask', {room: rootState.activeRoom.id, content: question})
		},
		async vote ({state, rootState}, question) {
			await api.call('question.vote', {room: rootState.activeRoom.id, id: question.id, vote: !question.voted})
			question.voted = !question.voted
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
		pinQuestion ({state, rootState}, question) {
			return api.call('question.pin', {room: rootState.activeRoom.id, id: question.id})
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
		},
		'api::question.pinned' ({state}, {id}) {
			for (const question of state.questions) {
				// unpin all other questions
				question.is_pinned = question.id === id
			}
		}
	}
}
