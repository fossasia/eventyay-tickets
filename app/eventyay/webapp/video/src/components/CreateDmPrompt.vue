<template lang="pug">
prompt.c-create-dm-prompt(:scrollable="false", @close="$emit('close')")
	.content
		h1 {{ $t('Chat with another person') }}
		p {{ $t('Start typing the name of one or more persons you want to talk to!') }}
		user-select(:button-label="$t('Start chat')", @selected="create", :exclude="[user.id]")
</template>
<script>
import {mapGetters, mapState} from 'vuex'
import Prompt from 'components/Prompt'
import UserSelect from 'components/UserSelect'

export default {
	components: { Prompt, UserSelect },
	emits: ['close'],
	data() {
		return {
			selectedUser: null
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		...mapState(['user', 'world']),
		liveFeatures() {
			return Object.assign({
				chat_rooms: false,
				kiosks: false,
				direct_messaging: false,
				announcements: true
			}, this.world?.live_features || window.eventyay?.liveFeatures || {})
		}
	},
	methods: {
		async create(users) {
			// Check permission and feature flag before creating direct message
			if (!this.hasPermission('world:chat.direct') || !this.liveFeatures.direct_messaging) {
				this.$emit('close')
				return
			}
			// TODO error handling, progress
			await this.$store.dispatch('chat/openDirectMessage', {users: users})
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-create-dm-prompt
	.prompt-wrapper
		height: 80vh
		width: 600px
	.content
		display: flex
		flex-direction: column
		position: relative
		box-sizing: border-box
		min-height: 0
		.c-user-select
			flex: 1
			min-height: 0
		#btn-close
			icon-button-style(style: clear)
			position: absolute
			top: 8px
			right: 8px
		h1
			font-size: 24px
			margin: 16px 16px 8px 16px
		p
			margin: 0 16px 16px 16px
			color: $clr-secondary-text-light
		form
			display: flex
			flex-direction: column
			align-self: stretch
			.bunt-button
				themed-button-primary()
				margin-top: 16px
			.bunt-select
				select-style(size: compact)
				ul li
					display: flex
					.mdi
						margin-right: 8px
			.bunt-input-outline-container
				textarea
					background-color: transparent
					border: none
					outline: none
					resize: vertical
					min-height: 64px
					padding: 0 8px
</style>
