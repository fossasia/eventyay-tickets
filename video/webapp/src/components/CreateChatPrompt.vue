<template lang="pug">
.c-create-chat-prompt(@click="$emit('close')")
	.prompt-wrapper(v-scrollbar.y="", @click.stop="")
		.prompt-wrapper-inner
			bunt-icon-button#btn-close(@click="$emit('close')") close
			h1 Create a new channel
			p Some explanation text
			form(@submit.prevent="create")
				bunt-select(name="type", label="Type", v-model="type", :options="types")
					template(slot-scope="{ option }")
						.mdi(:class="`mdi-${option.icon}`")
						.label {{ option.label }}
				bunt-input(name="name", label="Name", :icon="selectedType.icon", placeholder="fancyawesomechannel", v-model="name")
				bunt-input-outline-container(label="Description")
					textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur")
				bunt-button(type="submit", :loading="loading") create
</template>
<script>
import {mapGetters} from "vuex";

export default {
	components: {},
	data () {
		return {
			name: '',
			type: 'text',
			loading: false
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		types () {
			let types = []
			if (this.hasPermission('world:rooms.create.chat')) {
				types.push({
					id: 'text',
					label: 'Text chat',
					icon: 'pound'
				})
			}
			if (this.hasPermission('world:rooms.create.bbb')) {
				types.push({
					id: 'video',
					label: 'Video chat',
					icon: 'webcam'
				})
			}
			return types;
		},
		selectedType () {
			return this.types.find(type => type.id === this.type)
		}
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		async create () {
			this.loading = true
			const modules = []
			if (this.type === 'text') {
				modules.push({
					type: 'chat.native'
				})
			} else {
				modules.push({
					type: 'call.bigbluebutton'
				})
			}
			const { room } = await this.$store.dispatch('createRoom', {
				name: this.name,
				modules
			})
			// TODO error handling
			this.loading = false
			this.$router.push({name: 'room', params: {roomId: room}})
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-create-chat-prompt
	position: fixed
	top: 0
	left: 0
	width: 100vw
	height: 100vh
	z-index: 1000
	background-color: $clr-secondary-text-light
	display: flex
	justify-content: center
	align-items: center
	.prompt-wrapper
		card()
		display: flex
		flex-direction: column
		width: 480px
		max-height: 80vh
		.prompt-wrapper-inner
			display: flex
			flex-direction: column
			padding: 32px
			position: relative
			#btn-close
				icon-button-style(style: clear)
				position: absolute
				top: 8px
				right: 8px
			h1
				margin: 0
				text-align: center
			p
				max-width: 320px
			form
				display: flex
				flex-direction: column
				align-self: stretch
				.bunt-button
					button-style(color: $clr-primary)
					margin-top: 16px
				.bunt-select
					select-style(size: compact)
					ul li
						display: flex
						.mdi
							margin-right: 8px
				.bunt-input-outline-container
					textarea
						background-color: transparent
						border: none
						outline: none
						resize: vertical
						min-height: 64px
						padding: 0 8px
</style>
