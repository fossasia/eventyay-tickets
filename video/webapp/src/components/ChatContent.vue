<script>
import { h } from 'vue'
import MarkdownIt from 'markdown-it'
import store from 'store'
import { markdownEmoji } from 'lib/emoji'
import { getUserName } from 'lib/profile'

const markdownIt = MarkdownIt('zero', {
	linkify: true
})
markdownIt.enable('linkify')
markdownIt.renderer.rules.link_open = function (tokens, idx, options, env, self) {
	tokens[idx].attrPush(['target', '_blank'])
	tokens[idx].attrPush(['rel', 'noopener noreferrer'])
	return self.renderToken(tokens, idx, options)
}
markdownIt.use(markdownEmoji)

const mentionRegex = /(@[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12})/g

export async function contentToPlainText(content) {
	const parts = content.split(mentionRegex)
	let plaintext = ''

	for (const string of parts) {
		if (string.match(mentionRegex)) {
			const userId = string.slice(1)
			if (!store.state.chat.usersLookup[userId]) await store.dispatch('chat/fetchUsers', [userId])
			const user = store.state.chat.usersLookup[userId]
			if (user) {
				plaintext += `@${getUserName(user)}`
			}
		} else {
			plaintext += string
		}
	}
	return plaintext
}

const generateHTML = function(input) {
	if (!input) return ''
	return markdownIt.renderInline(input)
}

export default {
	components: {
		'user-modal': {
			props: ['selectedUser'],
			template: `
        <modal name="user-modal" height="auto" @before-close="closeUserModal">
          <div class="modal-content">
            <h3>User Information</h3>
            <p v-if="selectedUser">Name: {{ selectedUser.profile?.display_name || selectedUser.sender }}</p>
            <p v-if="selectedUser">Email: {{ selectedUser.email }}</p>
            <p v-if="selectedUser">Status: {{ selectedUser.status }}</p>
            <button @click="closeUserModal">Close</button>
          </div>
        </modal>
      `,
			methods: {
				closeUserModal() {
					this.$emit('close')
				}
			}
		}
	},
	props: {
		content: String
	},
	data() {
		return {
			selectedUser: null
		}
	},
	methods: {
		showUserModal(user) {
			this.selectedUser = user
			this.$modal.show('user-modal')
		},
		closeUserModal() {
			this.$modal.hide('user-modal')
		}
	},
	render() {
		const parts = this.content.split(mentionRegex)
		const content = parts.map(string => {
			if (string.match(mentionRegex)) {
				const userId = string.slice(1)
				const user = this.$store.state.chat.usersLookup[userId]
				if (user) {
					return { user }
				}
			}
			return { html: generateHTML(string) }
		})
		return h('span', {},
			content.map(part => {
				if (part.user) {
					return h('span', {
						class: 'mention',
						onClick: () => this.showUserModal(part.user)
					}, getUserName(part.user))
				}
				return h('span', { innerHTML: part.html })
			})
		)
	}
}
</script>
