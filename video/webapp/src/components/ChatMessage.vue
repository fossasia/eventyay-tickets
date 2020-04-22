<template lang="pug">
.c-chat-message
	img.gravatar-avatar(v-if="gravatarAvatarUrl", :src="gravatarAvatarUrl")
	identicon(v-else, :id="identicon")
	.content-wrapper
		span.display-name {{ user ? user.profile.display_name : this.message.sender }}
		span.content {{ message.content.body }}
</template>
<script>
import { mapState } from 'vuex'
import Identicon from 'components/Identicon'
import { getAvatarUrl } from 'lib/gravatar'

export default {
	props: {
		message: Object
	},
	components: { Identicon },
	data () {
		return {
		}
	},
	computed: {
		...mapState('chat', ['membersLookup']),
		user () {
			return this.membersLookup[this.message.sender]
		},
		gravatarAvatarUrl () {
			if (!this.user?.profile?.gravatar_hash) return
			return getAvatarUrl(this.user.profile.gravatar_hash, 28)
		},
		identicon () {
			return this.user?.profile?.identicon ?? this.user?.id ?? this.message.sender
		}
	}
}
</script>
<style lang="stylus">
.c-chat-message
	display: flex
	align-items: flex-start
	padding: 4px 8px
	.gravatar-avatar, .c-identicon
		width: 28px
		margin-right: 8px
	.content-wrapper
		padding-top: 6px // ???
	.display-name
		font-weight: 600
		color: $clr-secondary-text-light
		margin-right: 4px
</style>
