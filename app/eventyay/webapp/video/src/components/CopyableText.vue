<template lang="pug">
.c-copyable-text(:class="{'is-compact': compact, 'is-card': isCard}")
	.card-header(v-if="label || hint || showLaunchHeader")
		.header-main
			label.url-label(v-if="label") {{ label }}
			a.open-link(v-if="showLaunch && !launchLabel && displayValue", :href="displayValue", target="_blank", rel="noopener", :title="launchTitle || $t('Open in new tab')")
				i.mdi.mdi-open-in-new
		span.url-hint(v-if="hint") {{ hint }}
	.url-input-group
		.input-wrapper
			i.mdi.input-icon(:class="icon")
			input.url-input(ref="inputEl", type="text", readonly, :value="displayValue", @click="onInputClick")
		bunt-button.btn-copy(@click="copy", :class="{'is-copied': copied}")
			i.mdi(:class="copied ? 'mdi-check' : 'mdi-content-copy'")
			span {{ copied ? $t('Copied!') : $t('Copy') }}
		a.btn-launch(v-if="showLaunch && launchLabel && displayValue", :href="displayValue", target="_blank", rel="noopener", :title="launchTitle || $t('Open in new tab')")
			i.mdi.mdi-open-in-new
			span {{ launchLabel }}
</template>
<script>
export default {
	name: 'CopyableText',
	props: {
		url: {
			type: String,
			default: ''
		},
		text: {
			type: String,
			default: ''
		},
		label: {
			type: String,
			default: ''
		},
		hint: {
			type: String,
			default: ''
		},
		icon: {
			type: String,
			default: 'mdi-link-variant'
		},
		showLaunch: {
			type: Boolean,
			default: false
		},
		launchLabel: {
			type: String,
			default: ''
		},
		launchTitle: {
			type: String,
			default: ''
		},
		compact: {
			type: Boolean,
			default: false
		},
		isCard: {
			type: Boolean,
			default: false
		}
	},
	emits: ['copied'],
	data() {
		return {
			copied: false
		}
	},
	computed: {
		displayValue() {
			return this.url || this.text || ''
		},
		showLaunchHeader() {
			return this.showLaunch && !this.launchLabel && !!this.displayValue
		}
	},
	methods: {
		onInputClick(event) {
			if (event?.target?.select) {
				event.target.select()
			}
		},
		async copy() {
			if (!this.displayValue) return
			try {
				await navigator.clipboard.writeText(this.displayValue)
				this.copied = true
				this.$emit('copied', this.displayValue)
				setTimeout(() => {
					this.copied = false
				}, 2500)
			} catch (err) {
				console.error('Failed to copy to clipboard:', err)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-copyable-text
	display: flex
	flex-direction: column
	gap: 8px
	box-sizing: border-box

	&.is-card
		padding: 16px
		background-color: #f8fafc
		border: 1px solid #e2e8f0
		border-radius: 8px
		margin-bottom: 24px

	&.is-compact
		gap: 6px
		.card-header
			margin-bottom: 4px
		.url-input-group
			gap: 6px
			.input-wrapper
				height: 36px
				padding: 0 8px
				.url-input
					font-size: 12px
			.btn-copy
				height: 36px
				padding: 0 12px
				font-size: 12px

	.card-header
		display: flex
		flex-direction: column
		gap: 4px

		.header-main
			display: flex
			justify-content: space-between
			align-items: center

			.url-label
				font-weight: 600
				font-size: 13px
				color: $clr-primary-text-light
				letter-spacing: 0.01em

			.open-link
				color: var(--clr-primary, #3b82f6)
				font-size: 18px
				display: flex
				align-items: center
				justify-content: center
				width: 28px
				height: 28px
				border-radius: 4px
				text-decoration: none
				transition: background-color 0.15s ease
				&:hover
					background-color: $clr-grey-100
				.mdi
					font-size: 18px

		.url-hint
			font-size: 12px
			color: $clr-secondary-text-light
			line-height: 1.4

	.url-input-group
		display: flex
		align-items: center
		gap: 8px
		+below('m')
			flex-wrap: wrap

		.input-wrapper
			display: flex
			align-items: center
			flex: 1
			min-width: 0
			height: 40px
			background: #ffffff
			border: 1px solid #cbd5e1
			border-radius: 6px
			padding: 0 12px
			gap: 8px
			box-sizing: border-box
			transition: border-color 0.15s ease, box-shadow 0.15s ease

			&:focus-within
				border-color: $clr-primary
				box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12)

			.input-icon
				color: $clr-secondary-text-light
				font-size: 18px
				flex: none

			.url-input
				flex: 1
				min-width: 0
				height: 100%
				border: none
				outline: none
				background: transparent
				font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace
				font-size: 13px
				color: $clr-primary-text-light
				cursor: pointer
				white-space: nowrap
				overflow: hidden
				text-overflow: ellipsis

		.btn-copy
			display: inline-flex
			align-items: center
			justify-content: center
			gap: 6px
			height: 40px
			padding: 0 16px
			border-radius: 6px
			font-size: 13px
			font-weight: 600
			background-color: $clr-primary
			color: #ffffff
			border: none
			cursor: pointer
			flex: none
			box-sizing: border-box
			transition: background-color 0.15s ease, transform 0.1s ease

			&:hover
				opacity: 0.92

			&.is-copied
				background-color: $clr-success

			.mdi
				font-size: 16px

		.btn-launch
			display: inline-flex
			align-items: center
			justify-content: center
			gap: 6px
			height: 40px
			padding: 0 16px
			border-radius: 6px
			font-size: 13px
			font-weight: 500
			background-color: #ffffff
			color: $clr-primary-text-light
			border: 1px solid #cbd5e1
			text-decoration: none
			flex: none
			box-sizing: border-box
			transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease

			&:hover
				background-color: #f1f5f9
				border-color: #94a3b8
				color: $clr-primary

			.mdi
				font-size: 16px
</style>
