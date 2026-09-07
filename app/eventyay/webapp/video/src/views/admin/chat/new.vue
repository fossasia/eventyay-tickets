<template lang="pug">
.c-admin-chat-new
	.ui-page-header
		bunt-icon-button(@click="$router.replace({name: 'admin:chat:index'})", :tooltip="$t('Back to Chat Channels')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h1 {{ $t('New channel') }}
	.error(v-if="connected && !canCreate")
		span {{ $t('You do not have permission to create chat channels.') }}
	edit-form(v-else-if="config", :config="config", :creating="true")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script>
import { mapGetters, mapState } from 'vuex'
import { CHAT_CHANNEL_TYPE_ID, getRoomTypeById } from 'lib/room-types'
import EditForm from 'views/admin/rooms/EditForm'

export default {
	components: { EditForm },
	data() {
		return {
			config: null
		}
	},
	computed: {
		...mapState(['connected']),
		...mapGetters(['hasPermission']),
		canCreate() {
			return this.hasPermission('world:rooms.create.chat')
		}
	},
	watch: {
		connected: 'ensureConfig',
		canCreate: 'ensureConfig'
	},
	created() {
		this.ensureConfig()
	},
	methods: {
		ensureConfig() {
			if (!this.connected || !this.canCreate) return
			if (this.config?.module_config?.[0]?.type === 'chat.native') return
			const channelType = getRoomTypeById(CHAT_CHANNEL_TYPE_ID)
			if (!channelType) return
			this.config = {
				name: '',
				description: '',
				sorting_priority: '',
				pretalx_id: '',
				force_join: false,
				module_config: [{type: channelType.startingModule, config: {}}],
			}
		}
	}
}
</script>
<style lang="stylus">
.c-admin-chat-new
	background-color: $clr-white
	display: flex
	flex-direction: column
	min-height: 0
	height: 100%
	.bunt-icon-button
		icon-button-style(style: clear)
	.ui-page-header
		background-color: $clr-grey-100
		.bunt-icon-button
			margin-right: 8px
	h1
		font-size: 24px
		font-weight: 500
	.error
		padding: 24px 16px
		color: $clr-secondary-text-light
</style>
