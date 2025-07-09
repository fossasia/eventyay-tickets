import api from 'lib/api'

export default {
    namespaced: true,
    state: () => ({
        polls: null
    }),
    getters: {
        pinnedPoll: (state) => state.polls?.find(q => q.is_pinned)
    },
    actions: {
        async changeRoom({ state }, room) {
            state.polls = null
            if (!room) return
            if (room.modules.some(module => module.type === 'poll')) {
                state.polls = await api.call('poll.list', { room: room.id })
            }
        },
        createPoll({ rootState }, { content, options }) {
            options.forEach((option, index) => option.order = index + 1)
            return api.call('poll.create', {
                room: rootState.activeRoom.id,
                content,
                options
            })
        },
        updatePoll({ rootState }, { poll, update }) {
            return api.call('poll.update', {
                room: rootState.activeRoom.id,
                id: poll.id,
                ...update
            })
        },
        async vote({ rootState }, { poll, option }) {
            await api.call('poll.vote', {
                room: rootState.activeRoom.id,
                id: poll.id,
                options: [option.id]
            })
            poll.answers = [option.id]
        },
        openPoll({ rootState }, poll) {
            return api.call('poll.update', {
                room: rootState.activeRoom.id,
                id: poll.id,
                state: 'open'
            })
        },
        closePoll({ rootState }, poll) {
            return api.call('poll.update', {
                room: rootState.activeRoom.id,
                id: poll.id,
                state: 'closed'
            })
        },
        redraftPoll({ rootState }, poll) {
            return api.call('poll.update', {
                room: rootState.activeRoom.id,
                id: poll.id,
                state: 'draft'
            })
        },
        archivePoll({ rootState }, poll) {
            return api.call('poll.update', {
                room: rootState.activeRoom.id,
                id: poll.id,
                state: 'archived',
                is_pinned: false
            })
        },
        unarchivePoll({ rootState }, poll) {
            return api.call('poll.update', {
                room: rootState.activeRoom.id,
                id: poll.id,
                state: 'open'
            })
        },
        archiveAll({ state, rootState }) {
            return Promise.all(
                state.polls.map(poll => 
                    api.call('poll.update', {
                        room: rootState.activeRoom.id,
                        id: poll.id,
                        state: 'archived',
                        is_pinned: false
                    })
                )
            )
        },
        deletePoll({ rootState }, poll) {
            return api.call('poll.delete', {
                room: rootState.activeRoom.id,
                id: poll.id
            })
        },
        pinPoll({ rootState }, poll) {
            return api.call('poll.pin', {
                room: rootState.activeRoom.id,
                id: poll.id
            })
        },
        unpinPoll({ dispatch }) {
            return dispatch('unpinAllPolls')
        },
        unpinAllPolls({ rootState }) {
            return api.call('poll.unpin', {
                room: rootState.activeRoom.id
            })
        },
        'api::poll.created_or_updated'({ state }, { poll }) {
            const existingIndex = state.polls?.findIndex(q => q.id === poll.id) ?? -1
            if (existingIndex > -1 && state.polls) {
                state.polls[existingIndex] = { 
                    ...state.polls[existingIndex], 
                    ...poll 
                }
            } else if (state.polls) {
                state.polls.push(poll)
            } else {
                state.polls = [poll]
            }
        },
        'api::poll.deleted'({ state }, { id }) {
            if (!state.polls) return
            const pollIndex = state.polls.findIndex(q => q.id === id)
            if (pollIndex > -1) {
                state.polls.splice(pollIndex, 1)
            }
        },
        'api::poll.pinned'({ state }, { id }) {
            if (!state.polls) return
            state.polls.forEach(poll => {
                poll.is_pinned = poll.id === id
            })
        },
        'api::poll.unpinned'({ state }) {
            if (!state.polls) return
            state.polls.forEach(poll => {
                poll.is_pinned = false
            })
        }
    }
}
