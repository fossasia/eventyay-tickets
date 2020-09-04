<template lang="pug">
.c-registrationconfig
	bunt-progress-circular(size="huge", v-if="error == null && config == null")
	.error(v-if="error") We could not fetch the current configuration.
	.additional-fields-form(v-if="config != null")
		h2 User profile fields
		table.additional-fields
				thead
					tr
						th Name
						th Type
						th
						th
				tbody
					tr(v-for="(field, index) in config.profile_fields")
						td
							bunt-input(v-model="field.label", label="Label", name="label")
						td
							bunt-select(v-model="field.type", label="Type", name="type", :options="['text', 'textarea', 'select']")
						td
							bunt-input(v-if="field.type === 'select'", v-model="field.choices", label="Choices (comma seperated)", name="choices")
						td.actions
							bunt-icon-button(@click="removeField(index)") delete-outline
				tfoot
					tr
						td
							bunt-button(@click="addField") Add field
						td
						td
						td
		bunt-button.btn-save(@click="save", :loading="saving") Save
</template>
<script>
import api from 'lib/api'
import { v4 as uuid } from 'uuid'

export default {
	data () {
		return {
			config: null,

			saving: false,
			error: null
		}
	},
	async created () {
		// TODO: Force reloading if world.updated is received from the server
		try {
			this.config = await api.call('world.config.get')
		} catch (error) {
			this.error = error
			console.log(error)
		}
	},
	validations: {},
	methods: {
		addField () {
			this.config.profile_fields.push({label: '', type: 'text', choices: ''})
		},
		removeField (field) {
			this.$delete(this.config.profile_fields, field)
		},
		async save () {
			this.$v.$touch()
			if (this.$v.$invalid) return

			this.saving = true
			await api.call('world.config.patch', {profile_fields: this.config.profile_fields})
			this.saving = false
			// TODO error handling
		},
	}
}
</script>
<style lang="stylus">
.c-registrationconfig
	h2
		margin: 16px
	.additional-fields-form
		.additional-fields
			width 100%
			th
				text-align: left
				border-bottom: 1px solid #ccc
				padding: 10px
			td
				vertical-align center
		.btn-save
			margin-top: 16px
			themed-button-primary(size: large)
</style>
