<template lang="pug">
.c-room
	.main
		.room-info
			img(:src="room.picture")
			.room-info-text
				h2 {{ room.name }}
				.description {{ room.description }}
		livestream(v-if="modules['livestream.native']", :room="room", :module="modules['livestream.native']")
	chat(v-if="modules['chat.native']", :room="room", :module="modules['chat.native']")
</template>
<script>
import Chat from 'components/Chat'
import Livestream from 'components/Livestream'

export default {
	props: {
		roomId: String
	},
	components: { Chat, Livestream },
	data () {
		return {
		}
	},
	computed: {
		room () {
			return this.$store.state.rooms.find(room => room.id === this.roomId)
		},
		modules () {
			return this.room.modules.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
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
	background-color: $clr-white
	min-height: 0
	.main
		flex: auto
		display: flex
		flex-direction: column
		min-height: 0
	.room-info
		flex: none
		display: flex
		padding: 16px 16px
		.room-info-text
			margin-left: 16px
	.c-chat
		border-left: border-separator()
		flex: none
		width: 480px
</style>
