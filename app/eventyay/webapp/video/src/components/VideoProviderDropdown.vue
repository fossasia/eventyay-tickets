<template lang="pug">
.c-video-provider-dropdown(v-if="canManage", :class="{open}", @click.prevent.stop, @keydown.stop)
	template(v-if="providers.length")
		menu-dropdown(v-model="open", :placement="placement", :strategy="strategy", :offset="offset")
			template(#button="{toggle}")
				bunt-button.dropdown-toggle(
					:class="buttonClass",
					:aria-haspopup="'menu'",
					:aria-expanded="open ? 'true' : 'false'",
					:aria-controls="menuId",
					@click="onToggle($event, toggle)",
					@keydown="onButtonKeydown($event, toggle)"
				)
					span {{ label }}
					i.mdi.mdi-menu-down(aria-hidden="true")
			template(#menu)
				.provider-menu.not-menu-item(:id="menuId", role="menu", :aria-label="label")
					button.provider-option(
						v-for="(provider, index) of providers",
						:key="provider.id",
						type="button",
						role="menuitem",
						:ref="el => setItemRef(el, index)",
						@click="selectProvider(provider)",
						@keydown="onItemKeydown($event, index)"
					)
						i.mdi(:class="`mdi-${provider.icon}`", aria-hidden="true")
						span {{ $t(provider.label) }}
	template(v-else)
		bunt-button.dropdown-toggle(
			:class="buttonClass",
			disabled,
			:title="emptyMessage"
		)
			span {{ label }}
			i.mdi.mdi-menu-down(aria-hidden="true")
		p.empty-message(v-if="showEmptyMessage") {{ emptyMessage }}
</template>
<script>
import { mapGetters } from 'vuex'
import features from 'features'
import MenuDropdown from 'components/MenuDropdown'
import {
	canManageVideoRooms,
	getAvailableVideoProviders
} from 'lib/video-providers'

let dropdownId = 0

export default {
	name: 'VideoProviderDropdown',
	components: { MenuDropdown },
	props: {
		label: {
			type: String,
			required: true
		},
		variant: {
			type: String,
			default: 'primary'
		},
		showEmptyMessage: {
			type: Boolean,
			default: false
		},
		placement: {
			type: String,
			default: 'bottom-start'
		},
		strategy: {
			type: String,
			default: 'absolute'
		}
	},
	emits: ['select'],
	data() {
		return {
			open: false,
			menuId: `video-provider-menu-${++dropdownId}`,
			itemRefs: []
		}
	},
	computed: {
		...mapGetters(['hasPermission', 'isAdminMode']),
		canManage() {
			return canManageVideoRooms(this.hasPermission)
		},
		providers() {
			return getAvailableVideoProviders(
				this.hasPermission,
				this.isAdminMode,
				(flag) => features.enabled(flag),
				this.$store.state.world?.video_providers
			)
		},
		buttonClass() {
			return this.variant === 'action' ? 'btn-add-video' : 'btn-create'
		},
		emptyMessage() {
			return this.$t('No video options are enabled for this event.')
		},
		offset() {
			return [0, 4]
		}
	},
	methods: {
		setItemRef(el, index) {
			if (el) this.itemRefs[index] = el
		},
		onToggle(event, toggle) {
			const wasOpen = this.open
			toggle(event)
			if (!wasOpen) {
				this.$nextTick(() => this.focusItem(0))
			}
		},
		onButtonKeydown(event, toggle) {
			if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
				event.preventDefault()
				if (!this.open) toggle(event)
				this.$nextTick(() => this.focusItem(0))
			}
			if (event.key === 'Escape' && this.open) {
				event.preventDefault()
				this.open = false
			}
		},
		onItemKeydown(event, index) {
			if (event.key === 'Escape') {
				event.preventDefault()
				this.open = false
				this.$el.querySelector('.dropdown-toggle')?.focus?.()
				return
			}
			if (event.key === 'ArrowDown') {
				event.preventDefault()
				this.focusItem(index + 1)
				return
			}
			if (event.key === 'ArrowUp') {
				event.preventDefault()
				this.focusItem(index - 1)
				return
			}
			if (event.key === 'Home') {
				event.preventDefault()
				this.focusItem(0)
				return
			}
			if (event.key === 'End') {
				event.preventDefault()
				this.focusItem(this.providers.length - 1)
				return
			}
			if (event.key === 'Enter' || event.key === ' ') {
				event.preventDefault()
				this.selectProvider(this.providers[index])
			}
		},
		focusItem(index) {
			if (!this.providers.length) return
			const nextIndex = (index + this.providers.length) % this.providers.length
			this.itemRefs[nextIndex]?.focus?.()
		},
		selectProvider(provider) {
			this.open = false
			this.$emit('select', provider)
		}
	}
}
</script>
<style lang="stylus">
.c-video-provider-dropdown
	position: relative
	display: inline-flex
	flex-direction: column
	align-items: flex-end
	z-index: 1
	&.open
		z-index: 1200
	.dropdown-toggle
		display: inline-flex
		align-items: center
		gap: 4px
		&.btn-create
			themed-button-primary()
		&.btn-add-video
			themed-button-secondary()
			height: 28px
			padding: 0 10px
			font-size: 12px
			line-height: 28px
		.mdi-menu-down
			font-size: 18px
			margin-right: -4px
	.empty-message
		margin: 8px 0 0
		max-width: 280px
		font-size: 12px
		line-height: 16px
		color: $clr-secondary-text-light
		text-align: right
	.provider-menu
		display: flex
		flex-direction: column
		min-width: 220px
		position: relative
		z-index: 1200
	.provider-option
		display: flex
		align-items: center
		gap: 8px
		width: 100%
		height: 36px
		padding: 0 16px
		border: 0
		background: transparent
		color: inherit
		font: inherit
		text-align: left
		cursor: pointer
		&:hover,
		&:focus
			background-color: var(--clr-input-primary-bg, $clr-grey-50)
			color: var(--clr-input-primary-fg, $clr-primary-text-light)
			outline: none
		.mdi
			font-size: 18px
</style>
