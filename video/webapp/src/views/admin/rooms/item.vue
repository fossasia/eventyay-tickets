<template lang="pug">
.c-admin-room
	.error(v-if="error") We could not fetch the current configuration.
	template(v-else-if="config")
		.ui-page-header
			bunt-icon-button(@click="$router.push({name: 'admin:rooms:index'})") arrow_left
			h1 {{ inferredType ? inferredType.name : 'Mystery Room' }} : {{ config.name }}
			.actions
				bunt-button.btn-delete-room(@click="showDeletePrompt = true") delete
		edit-form(:config="config")
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		prompt.delete-prompt(v-if="showDeletePrompt", @close="showDeletePrompt = false")
			.content
				.prompt-header
					h3 Are you ABSOLUTELY sure?
				p This action #[b CANNOT] be undone. This will permanently delete the room
				.room-name {{ config.name }}
				p Please type in the name of the Project to confirm.
				bunt-input(name="projectName", label="Room name", v-model="deletingRoomName", @keypress.enter="deleteRoom")
				bunt-button.delete-room(icon="delete", :disabled="deletingRoomName !== config.name", @click="deleteRoom", :loading="deleting", :error-message="deleteError") delete this room
</template>
<script>
import api from 'lib/api'
import Prompt from 'components/Prompt'
import { inferType } from 'lib/room-types'
import EditForm from './EditForm'

export default {
	name: 'AdminRoom',
	components: { EditForm, Prompt },
	props: {
		roomId: String
	},
	data () {
		return {
			error: null,
			config: null,
			showDeletePrompt: false,
			deletingRoomName: '',
			deleting: false,
			deleteError: null
		}
	},
	computed: {
		inferredType () {
			return inferType(this.config)
		}
	},
	async created () {
		try {
			this.config = await api.call('room.config.get', {room: this.roomId})
		} catch (error) {
			this.error = error
			console.error(error)
		}
	},
	methods: {
		async deleteRoom () {
			if (this.deletingRoomName !== this.config.name) return
			this.deleting = true
			this.deleteError = null
			try {
				await api.call('room.delete', {room: this.config.id})
				this.$router.replace({name: 'admin:rooms:index'})
			} catch (error) {
				this.deleteError = this.$t(`error:${error.code}`)
			}
			this.deleting = false
		}
	}
}
</script>
<style lang="stylus">
.c-admin-room
	display: flex
	flex-direction: column
	background: $clr-white
	min-height: 0
	.bunt-icon-button
		icon-button-style(style: clear)
	.ui-page-header
		background-color: $clr-grey-100
		.bunt-icon-button
			margin-right: 8px
		h1
			flex: auto
			font-size: 24px
			font-weight: 500
			margin: 1px 16px 0 0
			ellipsis()
		.actions
			display: flex
			flex: none
			.bunt-button:not(:last-child)
				margin-right: 16px
			.btn-delete-room
				button-style(color: $clr-danger)

	.delete-prompt
		.content
			display: flex
			flex-direction: column
			padding: 16px
		.question-box-header
			margin-top: -10px
			margin-bottom: 15px
			align-items: center
			display: flex
			justify-content: space-between
		.room-name
			font-family: monospace
			font-size: 16px
			border: border-separator()
			border-radius: 4px
			padding: 4px 8px
			background-color: $clr-grey-100
			align-self: center
		.delete-room
			button-style(color: $clr-danger)
</style>
