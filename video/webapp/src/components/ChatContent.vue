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
markdownIt.renderer.rules.link_open = (tokens, idx, options, env, self) => {
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
					if (!store.state.chat.usersLookup[userId]) {
							await store.dispatch('chat/fetchUsers', [userId])
					}
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

function generateHTML(input) {
	if (!input) return
	return markdownIt.renderInline(input)
}

export default function(props, { emit }) {
       const parts = props.content.split(mentionRegex)
       const content = parts.map(string => {
               if (string.match(mentionRegex)) {
                       const user = store.state.chat.usersLookup[string.slice(1)]
                       if (user) {
                               return { user }
                       }
               }
               return { html: generateHTML(string) }
       })
       return content.map(part => {
               if (part.user) {
                       return h('span', {
                               class: 'mention',
                               onClick: event => emit('clickMention', event, part.user, 'top-start')
                       }, getUserName(part.user))
               }
               return h('span', { innerHTML: part.html })
       })
}
</script>
