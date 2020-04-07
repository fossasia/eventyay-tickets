<template lang="pug">
.c-room
	chat(v-if="room.modules.some(module => module.type === 'chat.native')", :room="room")
</template>
<script>
import Chat from 'components/Chat'

export default {
	props: {
		roomId: String
	},
	components: { Chat },
	data () {
		return {
		}
	},
	computed: {
		room () {
			return this.$store.state.rooms.find(room => room.id === this.roomId)
		}
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
.c-room
	flex: auto
	display: flex
</style>
