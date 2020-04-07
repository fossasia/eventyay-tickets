<template lang="pug">
.c-rooms-sidebar
	.rooms
		.room(v-for="room of rooms")
			router-link(:to="{name: 'room', params: {roomId: room.id}}")
				.name {{ room.name }}
</template>
<script>
import { mapState } from 'vuex'

export default {
	components: {},
	data () {
		return {
		}
	},
	computed: {
		...mapState(['rooms'])
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {}
}
</script>
<style lang="stylus">
.c-rooms-sidebar
	background-color: $clr-white
	box-shadow: 2px 2px 5px 0 rgba(0,0,0,0.16), 2px 12px 10px 0 rgba(0,0,0,0.12)
	z-index: 100
	.rooms
		display: flex
		flex-direction: column
		.room
			flex: none
			height: 36px
			line-height: 36px
			padding: 0 8px
</style>
