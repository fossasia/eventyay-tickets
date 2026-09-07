<template lang="pug">
.c-admin-rooms-new
	.ui-page-header
		bunt-icon-button(@click="$router.replace({name: 'admin:rooms:index'})", :tooltip="$t('Back to Rooms & Stages')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h1 {{ $t('New room') }}
			template(v-if="chosenProvider")  : {{ $t(chosenProvider.label) }}
	.provider-disabled-warning(v-if="type && !chosenProvider")
		i.mdi.mdi-alert-circle-outline
		h2 {{ $t('Room Type Disabled') }}
		p {{ $t('This video provider has been disabled by the system administrator.') }}
		bunt-button(@click="$router.replace({name: 'admin:rooms:index'})") {{ $t('Back to Rooms & Stages') }}
	edit-form(v-else-if="config", :config="config", :creating="true")
</template>
<script>
import { mapGetters } from 'vuex'
import features from 'features'
import { getRoomTypeById } from 'lib/room-types'
import {
	applyVideoProviderToConfig,
	getAvailableVideoProviders,
} from 'lib/video-providers'
import EditForm from './EditForm'

export default {
	components: { EditForm },
	data() {
		return {
			type: null,
			config: null
		}
	},
	computed: {
		...mapGetters(['hasPermission', 'isAdminMode']),
		availableProviders() {
			return getAvailableVideoProviders(
				this.hasPermission,
				this.isAdminMode,
				(flag) => features.enabled(flag),
				this.$store.state.world?.video_providers
			)
		},
		chosenProvider() {
			return this.availableProviders.find(provider => provider.roomTypeId === this.type) || null
		},
		chosenType() {
			return this.chosenProvider ? getRoomTypeById(this.chosenProvider.roomTypeId) : null
		},
	},
	watch: {
		$route: 'updateType'
	},
	created() {
		this.updateType()
	},
	methods: {
		updateType() {
			this.type = this.$route.params.type
			if (this.type === 'channel-text') {
				this.$router.replace({name: 'admin:chat:new'})
				return
			}
			this.config = {
				name: '',
				description: '',
				sorting_priority: '',
				pretalx_id: '',
				force_join: false,
				is_unscheduled: false,
				module_config: [],
			}
			if (this.type && this.chosenType) {
				applyVideoProviderToConfig(this.config, this.chosenType)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-admin-rooms-new
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
	.provider-disabled-warning
		margin: 40px auto
		max-width: 500px
		text-align: center
		padding: 32px 24px
		background-color: $clr-grey-50
		border: 1px solid $clr-grey-200
		border-radius: 8px
		i.mdi
			font-size: 48px
			color: $clr-warning
			margin-bottom: 16px
			display: block
		h2
			font-size: 20px
			font-weight: 600
			margin: 0 0 8px
			color: $clr-grey-900
		p
			font-size: 14px
			color: $clr-grey-700
			margin: 0 0 24px
</style>
