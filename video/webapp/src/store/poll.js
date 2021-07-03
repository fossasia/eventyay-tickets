import Vue from 'vue'
import api from 'lib/api'

export default {
	namespaced: true,
	state: {
		polls: null
	},
	getters: {
		pinnedPoll (state) {
			return state.polls?.find(q => q.is_pinned)
		}
	},
	actions: {
		async changeRoom ({state}, room) {
			state.polls = null
			if (!room) return
			if (room.modules.some(module => module.type === 'poll')) {
				state.polls = await api.call('poll.list', {room: room.id})
			}
		},
		createPoll ({state, rootState}, {content, options}) {
			// enumerate poll options order attributes
			options.forEach((option, index) => option.order = index + 1)
			return api.call('poll.create', {room: rootState.activeRoom.id, content, options})
		},
		async vote ({state, rootState}, {poll, option}) {
			await api.call('poll.vote', {room: rootState.activeRoom.id, id: poll.id, options: [option.id]})
			Vue.set(poll, 'answers', [option.id])
		},
		openPoll ({state, rootState}, poll) {
			return api.call('poll.update', {room: rootState.activeRoom.id, id: poll.id, state: 'open'})
			// update handled in create_or_update
			// TODO error handling
		},
		closePoll ({state, rootState}, poll) {
			return api.call('poll.update', {room: rootState.activeRoom.id, id: poll.id, state: 'closed'})
			// update handled in create_or_update
			// TODO error handling
		},
		redraftPoll ({state, rootState}, poll) {
			return api.call('poll.update', {room: rootState.activeRoom.id, id: poll.id, state: 'draft'})
			// update handled in create_or_update
			// TODO error handling
		},
		archivePoll ({state, rootState}, poll) {
			return api.call('poll.update', {room: rootState.activeRoom.id, id: poll.id, state: 'archived', is_pinned: false})
			// update handled in create_or_update
			// TODO error handling
		},
		unarchivePoll ({state, rootState}, poll) {
			return api.call('poll.update', {room: rootState.activeRoom.id, id: poll.id, state: 'open'})
			// update handled in create_or_update
			// TODO error handling
		},
		archiveAll ({state, rootState}) {
			// just send all updates in parallel
			for (const poll of state.polls) {
				api.call('poll.update', {room: rootState.activeRoom.id, id: poll.id, state: 'archived', is_pinned: false})
			}
		},
		deletePoll ({state, rootState}, poll) {
			return api.call('poll.delete', {room: rootState.activeRoom.id, id: poll.id})
			// update handled in api::poll.deleted
			// TODO error handling
		},
		pinPoll ({state, rootState}, poll) {
			return api.call('poll.pin', {room: rootState.activeRoom.id, id: poll.id})
		},
		// redirect per poll menu unpin to global unpin
		unpinPoll ({dispatch}) {
			return dispatch('unpinAllPolls')
		},
		unpinAllPolls ({state, rootState}) {
			return api.call('poll.unpin', {room: rootState.activeRoom.id})
		},
		'api::poll.created_or_updated' ({state}, {poll}) {
			const existingPoll = state.polls.find(q => q.id === poll.id)
			if (existingPoll) {
				for (const [key, value] of Object.entries(poll)) {
					Vue.set(existingPoll, key, value)
				}
			} else {
				state.polls.push(poll)
			}
		},
		'api::poll.deleted' ({state}, {id}) {
			const pollIndex = state.polls.findIndex(q => q.id === id)
			if (pollIndex > -1) {
				state.polls.splice(pollIndex, 1)
			}
		},
		'api::poll.pinned' ({state}, {id}) {
			for (const poll of state.polls) {
				// unpin all other polls
				poll.is_pinned = poll.id === id
			}
		},
		'api::poll.unpinned' ({state}) {
			// TODO check room
			for (const poll of state.polls) {
				// unpin all polls
				poll.is_pinned = false
			}
		}
	}
}
