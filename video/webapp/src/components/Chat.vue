<template lang="pug">
.c-chat
	.timeline
		.message(v-for="message of timeline") {{ message.content.body }}
	bunt-input(name="chat-composer", v-model="composingMessage", @keydown.native.enter="send")
</template>
<script>
import { mapState } from 'vuex'

export default {
	props: {
		room: Object
	},
	components: {},
	data () {
		return {
			composingMessage: ''
		}
	},
	computed: {
		...mapState('chat', ['timeline'])
	},
	created () {
		this.$store.dispatch('chat/join', this.room)
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		send () {
			this.$store.dispatch('chat/sendMessage', {room: this.room, text: this.composingMessage})
			this.composingMessage = ''
		}
	}
}
</script>
<style lang="stylus">
.c-chat
	flex: auto
	background-color: $clr-white
	display: flex
	flex-direction: column
	.timeline
		flex: auto
		margin: 8px 24px
		display: flex
		flex-direction: column
		justify-content: flex-end
		.message
			padding-top: 8px
	.bunt-input
		flex: none
		margin: 0 16px
</style>
