<template lang="pug">
.c-admin-rooms-new
	.ui-page-header
		bunt-icon-button(@click="$router.replace({name: 'admin:rooms:index'})", :tooltip="$t('Back to Rooms & Stages')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h1 {{ $t('New room') }}
			template(v-if="chosenProvider")  : {{ $t(chosenProvider.label) }}
	edit-form(v-if="config", :config="config", :creating="true")
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
				(flag) => features.enabled(flag)
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
</style>
