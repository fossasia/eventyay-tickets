<template lang="pug">
router-link.c-room-list-item.table-row(:to="to", :class="{'mystery': !inferredType}", draggable="false")
	.handle.mdi.mdi-drag-vertical(:class="{disabled}", v-handle, v-tooltip="disabled ? $t('sorting is disabled while searching') : ''")
	.name(v-html="$emojify(room.name)")
	.badge-cell
		.badges-wrapper
			.room-type-badge.unscheduled-room-badge(v-if="room.is_unscheduled")
				.mdi.mdi-calendar-remove
				span {{ $t('Unscheduled') }}
			.room-type-badge(v-if="inferredType", :class="badgeClass")
				.mdi(:class="badgeIcon")
				span {{ badgeLabel }}
			VideoProviderDropdown(
				v-else,
				:label="$t('Add Video')",
				variant="action",
				placement="bottom-end",
				strategy="fixed",
				@select="addVideo"
			)
</template>
<script>
import { ElementMixin, HandleDirective } from 'vue-slicksort'
import { inferType } from 'lib/room-types'
import { getConfiguredRoomLabel } from 'lib/video-providers'
import VideoProviderDropdown from 'components/VideoProviderDropdown'

export default {
	components: { VideoProviderDropdown },
	directives: { handle: HandleDirective },
	mixins: [ElementMixin],
	props: {
		room: Object,
		to: {
			type: Object,
			required: true
		}
	},
	computed: {
		inferredType () {
			// Only treat rooms as configured when they have module_config.
			if (!Array.isArray(this.room?.module_config) || this.room.module_config.length === 0) return null
			return inferType({ module_config: this.room.module_config })
		},
		badgeLabel () {
			const label = getConfiguredRoomLabel(this.inferredType)
			return label ? this.$t(label) : ''
		},
		badgeIcon () {
			return `mdi-${this.inferredType.icon}`
		},
		badgeClass () {
			return `type-${this.inferredType.id}`
		}
	},
	methods: {
		addVideo (provider) {
			this.$router.push({
				name: 'admin:rooms:item',
				params: { roomId: this.room.id },
				query: { provider: provider.roomTypeId }
			})
		}
	}
}
</script>
<style lang="stylus">
.c-room-list-item
	display: flex
	align-items: center
	color: $clr-primary-text-light
	.handle
		user-select: none
		cursor: row-resize
		font-size: 24px
		&.disabled
			cursor: auto
			color: $clr-grey-300
	.name
		flex: auto
		ellipsis()
	.badge-cell
		display: flex
		align-items: center
		justify-content: flex-end
	.badges-wrapper
		display: flex
		flex-direction: row
		align-items: center
		gap: 8px
	.room-type-badge
		display: flex
		align-items: center
		gap: 4px
		flex: none
		max-width: 260px
		padding: 4px 10px
		border-radius: 999px
		font-size: 12px
		line-height: 16px
		background-color: $clr-grey-100
		color: $clr-secondary-text-light
		border: 1px solid $clr-grey-200
		white-space: nowrap
		.mdi
			font-size: 14px
			flex: none
		span
			min-width: 0
			overflow: hidden
			text-overflow: ellipsis
			display: block
		&.unscheduled-room-badge
			background-color: $clr-cyan-100
			color: $clr-cyan-900
			border-color: $clr-cyan-100
		&.type-stage
			background-color: $clr-blue-50
			color: $clr-blue-900
			border-color: $clr-blue-50
		&.type-channel-bbb,
		&.type-channel-janus,
		&.type-channel-jitsi,
		&.type-channel-zoom,
		&.type-channel-loungemesh,
		&.type-channel-roulette
			background-color: $clr-blue-grey-200
			color: $clr-blue-grey-900
			border-color: $clr-blue-grey-200
		&.type-channel-text,
		&.type-page-landing
			background-color: $clr-grey-50
			color: $clr-grey-800
			border-color: $clr-grey-200
</style>
