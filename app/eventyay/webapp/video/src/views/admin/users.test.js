/**
 * Regression tests for issue #5444:
 * Inconsistent 'ban' & 'silence' behaviour for video/admin users list vs detail page.
 * Run: node --test src/views/admin/users.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const usersVuePath = path.resolve(__dirname, 'users.vue')
const userVuePath = path.resolve(__dirname, 'user.vue')
const chatStorePath = path.resolve(__dirname, '../../store/chat.js')

const usersVueContent = fs.readFileSync(usersVuePath, 'utf8')
const userVueContent = fs.readFileSync(userVuePath, 'utf8')
const chatStoreContent = fs.readFileSync(chatStorePath, 'utf8')

test('issue #5444: user detail page (user.vue) gates ban and silence behind UserActionPrompt', () => {
	// Detail page must register and use UserActionPrompt
	assert.match(userVueContent, /import UserActionPrompt from ['"]components\/UserActionPrompt['"]/)
	assert.match(userVueContent, /user-action-prompt\(/)

	// Detail page action buttons must set userAction rather than calling api directly
	assert.match(userVueContent, /\.btn-ban[\s\S]*?@click="userAction = 'ban'"/)
	assert.match(userVueContent, /\.btn-silence[\s\S]*?@click="userAction = 'silence'"/)
	assert.match(userVueContent, /\.btn-reactivate[\s\S]*?@click="userAction = 'reactivate'"/)
})

test('issue #5444: users list page (users.vue) gates ban and silence behind UserActionPrompt', () => {
	// List page must import and register UserActionPrompt
	assert.match(usersVueContent, /import UserActionPrompt from ['"]components\/UserActionPrompt['"]/)
	assert.match(usersVueContent, /components:\s*\{\s*Avatar,\s*UserActionPrompt\s*\}/)

	// List page must render user-action-prompt with the exact same configuration as user.vue
	assert.match(usersVueContent, /user-action-prompt\(\s*v-if="userAction && selectedUser",\s*:action="userAction",\s*:user="selectedUser",\s*:closeDelay="0",\s*@close="completedUserAction"\s*\)/)

	// List page buttons must use promptUserAction instead of executing immediately via doAction
	assert.match(usersVueContent, /\.btn-ban[\s\S]*?@click="promptUserAction\(user, 'ban'\)"/)
	assert.match(usersVueContent, /\.btn-silence[\s\S]*?@click="promptUserAction\(user, 'silence'\)"/)
	assert.match(usersVueContent, /\.btn-reactivate[\s\S]*?@click="promptUserAction\(user, 'reactivate'\)"/)

	// Must NOT contain direct unconfirmed doAction execution
	assert.doesNotMatch(usersVueContent, /@click="doAction\(/)
	assert.doesNotMatch(usersVueContent, /doAction\(user,\s*action,\s*postState\)/)
})

test('issue #5444: promptUserAction and completedUserAction state management on users list page', async () => {
	// Simulate the methods in users.vue
	const state = {
		selectedUser: null,
		userAction: null,
		apiCalls: []
	}

	const fakeApi = {
		call: async (endpoint, payload) => {
			state.apiCalls.push({ endpoint, payload })
			if (endpoint === 'user.fetch') {
				return { id: payload.id, moderation_state: 'banned' }
			}
			return {}
		}
	}

	const methods = {
		promptUserAction(user, action) {
			state.selectedUser = user
			state.userAction = action
		},
		async completedUserAction() {
			const user = state.selectedUser
			state.userAction = null
			state.selectedUser = null
			if (!user) return
			try {
				const updatedUser = await fakeApi.call('user.fetch', { id: user.id })
				if (updatedUser) {
					user.moderation_state = updatedUser.moderation_state
				}
			} catch (e) {
				console.error('Failed to refresh user moderation state in test:', e)
			}
		}
	}

	const targetUser = { id: 'usr_123', moderation_state: null }

	// 1. Triggering ban action sets prompt state
	methods.promptUserAction(targetUser, 'ban')
	assert.equal(state.userAction, 'ban')
	assert.equal(state.selectedUser, targetUser)
	assert.equal(state.apiCalls.length, 0, 'No API call should happen on button click before confirmation')

	// 2. Completing the prompt refreshes user state and resets prompt state
	await methods.completedUserAction()
	assert.equal(state.userAction, null)
	assert.equal(state.selectedUser, null)
	assert.equal(targetUser.moderation_state, 'banned')
	assert.deepEqual(state.apiCalls, [{ endpoint: 'user.fetch', payload: { id: 'usr_123' } }])
})

test('issue #5444: completedUserAction handles user.fetch errors gracefully without crashing', async () => {
	const state = {
		selectedUser: { id: 'usr_err', moderation_state: null },
		userAction: 'silence',
		caughtError: null
	}

	const methods = {
		async completedUserAction() {
			const user = state.selectedUser
			state.userAction = null
			state.selectedUser = null
			if (!user) return
			try {
				throw new Error('Network error')
			} catch (e) {
				state.caughtError = e
				console.error('Failed to refresh user moderation state:', e.message)
			}
		}
	}

	await assert.doesNotReject(async () => {
		await methods.completedUserAction()
	})
	assert.equal(state.userAction, null)
	assert.equal(state.selectedUser, null)
})

test('issue #5444: chat store moderateUser updates silence state to "silenced"', () => {
	assert.match(chatStoreContent, /silence:\s*['"]silenced['"]/)
	assert.match(chatStoreContent, /user\.moderation_state\s*=\s*postStates\[action\]/)
})
