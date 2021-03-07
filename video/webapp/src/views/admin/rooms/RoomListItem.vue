<template lang="pug">
router-link.c-room-list-item.table-row(:to="{name: 'admin:rooms:item', params: {roomId: room.id}}")
	.handle.mdi.mdi-drag-vertical(v-handle)
	.name {{ room.name }}
</template>
<script>
import { ElementMixin, HandleDirective } from 'vue-slicksort'
export default {
	directives: { handle: HandleDirective },
	mixins: [ElementMixin],
	props: {
		room: Object
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
</style>
