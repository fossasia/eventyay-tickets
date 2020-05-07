<template lang="pug">
.c-create-chat-prompt(@click="$emit('close')")
	.prompt-wrapper(v-scrollbar.y="", @click.stop="")
		.prompt-wrapper-inner
			bunt-icon-button#btn-close(@click="$emit('close')") close
			h1 Create a new chat room
			p Some explanation text
			form(@submit.prevent="create")
				bunt-select(name="type", label="Type", v-model="type", :options="types")
					template(slot-scope="{ option }")
						.mdi(:class="`mdi-${option.icon}`")
						.label {{ option.label }}
				bunt-input(name="name", label="Name", :icon="selectedType.icon", placeholder="fancyawesomechannel")
				bunt-button(type="submit") create
</template>
<script>
export default {
	components: {},
	data () {
		return {
			name: '',
			type: 'text',
			types: [{
				id: 'text',
				label: 'Text chat',
				icon: 'pound'
			}, {
				id: 'video',
				label: 'Video chat',
				icon: 'webcam'
			}]
		}
	},
	computed: {
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
		create () {

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
				.bunt-select
					select-style(size: compact)
					ul li
						display: flex
						.mdi
							margin-right: 8px
</style>
