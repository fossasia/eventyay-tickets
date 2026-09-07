<template lang="pug">
.c-base-channel-form
	.provider-disabled-warning(v-if="isProviderDisabled")
		i.mdi.mdi-alert-circle-outline
		.warning-text
			strong {{ $t('Feature Disabled') }}
			p {{ $t('This feature is no longer available. Please contact system administrator.') }}

	.provider-overview-card
		.provider-icon-wrapper(:class="providerId")
			i.mdi(:class="providerIcon")
		.provider-info
			.provider-title {{ title }}
			.provider-subtitle {{ subtitle }}

	.provider-settings-section
		slot
</template>
<script>
export default {
	name: 'BaseChannelForm',
	props: {
		providerId: {
			type: String,
			required: true // 'bbb', 'janus', 'jitsi'
		},
		title: {
			type: String,
			required: true
		},
		subtitle: {
			type: String,
			required: true
		},
		providerIcon: {
			type: String,
			default: 'mdi-video'
		},
		config: {
			type: Object,
			required: true
		},
		modules: {
			type: Object,
			required: true
		},
		creating: {
			type: Boolean,
			default: false
		}
	},
	computed: {
		isProviderDisabled() {
			const providers = this.$store?.state?.world?.video_providers
			if (!providers || !this.providerId) return false
			const config = providers[this.providerId]
			return config && config.available === false
		}
	}
}
</script>
<style lang="stylus">
.c-base-channel-form
	display: flex
	flex-direction: column
	gap: 20px

	.provider-disabled-warning
		display: flex
		align-items: flex-start
		gap: 12px
		padding: 14px 16px
		background-color: #fff8f8
		border: 1px solid #fecaca
		border-radius: 8px
		color: #991b1b

		> i.mdi
			font-size: 22px
			color: #dc2626
			flex-shrink: 0
			margin-top: 1px

		.warning-text
			strong
				display: block
				font-size: 14px
				margin-bottom: 2px
			p
				margin: 0
				font-size: 13px
				color: #b91c1c

	.provider-overview-card
		display: flex
		align-items: center
		gap: 16px
		padding: 16px
		background-color: #ffffff
		border-radius: 8px
		border: 1px solid #e2e8f0
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04)

		.provider-icon-wrapper
			display: flex
			align-items: center
			justify-content: center
			width: 48px
			height: 48px
			border-radius: 8px
			font-size: 26px
			flex-shrink: 0

			&.janus
				background-color: #eef2ff
				color: #4f46e5

			&.jitsi
				background-color: #f0f9ff
				color: #0284c7

			&.bbb
				background-color: #fef2f2
				color: #dc2626

			&.zoom
				background-color: #eff6ff
				color: #2563eb

			&.loungemesh
				background-color: #f5f3ff
				color: #7c3aed

		.provider-info
			.provider-title
				font-size: 16px
				font-weight: 700
				color: #1e293b
				margin-bottom: 2px

			.provider-subtitle
				font-size: 13px
				color: #64748b

	.provider-settings-section
		display: flex
		flex-direction: column
		gap: 12px
</style>
