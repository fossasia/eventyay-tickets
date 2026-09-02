<template lang="pug">
.c-audio-translation(:class="{open: menuOpen}")
	.ui-background-blocker(v-if="menuOpen", @click="closeMenu")
	.field-shell(v-if="!icon")
		span.floating-label {{ resolvedLabel }}
		button.language-toggle(
			ref="toggle",
			type="button",
			:aria-label="resolvedLabel",
			aria-haspopup="listbox",
			:aria-expanded="menuOpen ? 'true' : 'false'",
			:aria-controls="menuId",
			@click="toggleMenu",
			@keydown="onToggleKeydown"
		)
			span.value {{ internalSelectedLanguage }}
			i.mdi.mdi-menu-down(aria-hidden="true")
	button.stage-tool(
		v-else,
		ref="toggle",
		type="button",
		:class="{ active: menuOpen }",
		:aria-label="resolvedLabel",
		aria-haspopup="listbox",
		:aria-expanded="menuOpen ? 'true' : 'false'",
		:aria-controls="menuId",
		@click="toggleMenu",
		@keydown="onToggleKeydown",
		style="margin: 0; background: transparent; border: none;"
	)
		i.mdi(:class="icon")
	ul.language-menu(
		v-if="menuOpen",
		ref="menu",
		:id="menuId",
		role="listbox",
		:aria-label="resolvedLabel"
	)
		li(
			v-for="(language, index) of languageOptions",
			:key="language",
			role="option",
			:aria-selected="language === internalSelectedLanguage ? 'true' : 'false'",
			:class="{active: language === internalSelectedLanguage, highlight: index === highlightedIndex}",
			@click="selectLanguage(language)",
			@mouseenter="highlightedIndex = index"
		) {{ language }}
</template>
<script>
import { createPopper } from '@popperjs/core'
import { normalizeAudioTranslationSource } from 'lib/validators'

let dropdownId = 0

export default {
	name: 'AudioTranslationDropdown',
	emits: ['languageChanged'],
	props: {
		languages: {
			type: Array,
			required: true
		},
		selectedLanguage: {
			type: String,
			default: 'Original'
		},
		label: {
			type: String,
			default: null
		},
		icon: {
			type: String,
			default: null
		}
	},
	data() {
		return {
			internalSelectedLanguage: null,
			languageOptions: [],
			isSyncingSelection: false,
			menuOpen: false,
			highlightedIndex: 0,
			menuId: `audio-translation-menu-${++dropdownId}`,
			popper: null
		}
	},
	computed: {
		resolvedLabel() {
			return this.label || this.$t('Interpretation')
		},
	},
	watch: {
		languages: {
			immediate: true,
			handler(newLanguages) {
				this.languageOptions = newLanguages.map(entry => entry.language)
				this.syncSelectedLanguage()
			}
		},
		selectedLanguage: {
			immediate: true,
			handler() {
				this.syncSelectedLanguage()
			}
		},
		internalSelectedLanguage(newLanguage) {
			if (this.isSyncingSelection) return
			if (newLanguage) {
				this.sendLanguageChange()
			}
		}
	},
	beforeUnmount() {
		this.destroyPopper()
	},
	methods: {
		syncSelectedLanguage() {
			const fallback = this.languageOptions.includes('Original') ? 'Original' : null
			const nextLanguage = this.languageOptions.includes(this.selectedLanguage) ? this.selectedLanguage : fallback
			if (this.internalSelectedLanguage === nextLanguage) return
			this.isSyncingSelection = true
			this.internalSelectedLanguage = nextLanguage
			this.$nextTick(() => {
				this.isSyncingSelection = false
			})
		},
		sendLanguageChange() {
			const selected = this.languages.find(item => item.language === this.internalSelectedLanguage)
			const audioSource = normalizeAudioTranslationSource(selected?.url || selected?.youtube_id)
			const useVideo = selected?.use_video || false

			this.$emit('languageChanged', { ...(selected || {}), url: audioSource, useVideo })
		},
		async toggleMenu() {
			if (this.menuOpen) {
				this.closeMenu()
				return
			}
			this.highlightedIndex = Math.max(this.languageOptions.indexOf(this.internalSelectedLanguage), 0)
			this.menuOpen = true
			await this.$nextTick()
			if (!this.$refs.toggle || !this.$refs.menu) {
				this.menuOpen = false
				return
			}
			try {
				this.popper = createPopper(this.$refs.toggle, this.$refs.menu, {
					placement: 'bottom-end',
					strategy: 'fixed',
					modifiers: [{ name: 'offset', options: { offset: [0, 4] } }]
				})
			} catch (error) {
				console.error('Failed to position interpretation language menu', error)
			}
		},
		closeMenu() {
			this.menuOpen = false
			this.destroyPopper()
		},
		destroyPopper() {
			this.popper?.destroy()
			this.popper = null
		},
		selectLanguage(language) {
			this.internalSelectedLanguage = language
			this.closeMenu()
		},
		onToggleKeydown(event) {
			if (event.key === 'Escape' && this.menuOpen) {
				event.preventDefault()
				this.closeMenu()
				return
			}
			if (event.key === 'Enter' || event.key === ' ') {
				event.preventDefault()
				if (!this.menuOpen) {
					this.toggleMenu()
					return
				}
				const language = this.languageOptions[this.highlightedIndex]
				if (language) this.selectLanguage(language)
				return
			}
			if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
				event.preventDefault()
				if (!this.menuOpen) {
					this.toggleMenu()
					return
				}
				const delta = event.key === 'ArrowDown' ? 1 : -1
				const count = this.languageOptions.length
				if (!count) return
				this.highlightedIndex = (this.highlightedIndex + delta + count) % count
			}
		}
	}
}
</script>
<style lang="stylus">
.c-audio-translation
	position: relative
	display: inline-flex
	align-items: center
	flex: none
	z-index: 1
	&.open
		z-index: 1200
	.ui-background-blocker
		position: fixed
		inset: 0
		z-index: 1199
	.field-shell
		position: relative
		display: inline-flex
		align-items: center
		height: 32px
		padding: 0 2px 0 8px
		border: 1px solid $clr-grey-400
		border-radius: 4px
		background: $clr-white
		box-sizing: border-box
	.floating-label
		position: absolute
		top: 0
		left: 6px
		transform: translateY(-50%)
		padding: 0 3px
		background: $clr-white
		color: $clr-secondary-text-light
		font-size: 11px
		line-height: 1
		pointer-events: none
		white-space: nowrap
	.language-toggle
		display: inline-flex
		align-items: center
		gap: 0
		margin: 0
		padding: 0
		border: 0
		background: transparent
		color: inherit
		font: inherit
		font-size: 14px
		line-height: 20px
		cursor: pointer
		.value
			white-space: nowrap
		.mdi-menu-down
			font-size: 18px
			line-height: 18px
			color: $clr-secondary-text-light
	.language-menu
		card()
		position: absolute
		z-index: 1200
		display: inline-flex
		flex-direction: column
		align-items: stretch
		width: max-content
		min-width: 0
		max-height: 240px
		margin: 0
		padding: 4px 0
		list-style: none
		overflow-y: auto
		box-sizing: border-box
		li
			box-sizing: border-box
			height: 32px
			padding: 0 12px
			font-size: 14px
			line-height: 32px
			white-space: nowrap
			cursor: pointer
			&:hover,
			&.highlight
				background-color: var(--clr-input-primary-bg, $clr-grey-50)
			&.active
				font-weight: 600
</style>
