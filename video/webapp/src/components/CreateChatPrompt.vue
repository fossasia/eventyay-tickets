<template lang="pug">
prompt.c-create-chat-prompt(@close="$emit('close')")
	.content
		bunt-icon-button#btn-close(@click="$emit('close')") close
		h1 {{ $t('CreateChatPrompt:headline:text') }}
		p {{ $t('CreateChatPrompt:intro:text') }}
		form(@submit.prevent="create")
			bunt-select(name="type", :label="$t('CreateChatPrompt:type:label')", v-model="type", :options="types")
				template(slot-scope="{ option }")
					.mdi(:class="`mdi-${option.icon}`")
					.label {{ option.label }}
			bunt-input(name="name", :label="$t('CreateChatPrompt:name:label')", :icon="selectedType.icon", :placeholder="$t('CreateChatPrompt:name:placeholder')", v-model="name")
			bunt-input-outline-container(:label="$t('CreateChatPrompt:description:label')")
				textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur")
			bunt-button(type="submit", :loading="loading") {{ $t('CreateChatPrompt:submit:label') }}
</template>
<script>
import {mapGetters} from 'vuex'
import Prompt from 'components/Prompt'

export default {
	components: { Prompt },
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
			const types = []
			if (this.hasPermission('world:rooms.create.chat')) {
				types.push({
					id: 'text',
					label: this.$t('CreateChatPrompt:type.text:label'),
					icon: 'pound'
				})
			}
			if (this.hasPermission('world:rooms.create.bbb')) {
				types.push({
					id: 'video',
					label: this.$t('CreateChatPrompt:type.video:label'),
					icon: 'webcam'
				})
			}
			return types
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
	.content
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
				themed-button-primary()
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
