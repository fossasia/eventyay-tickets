<template lang="pug">
.c-permissionconfig
	bunt-progress-circular(size="huge", v-if="error == null && config == null")
	.error(v-if="error") We could not fetch the current configuration.
	div(v-if="config != null")
		div.role(v-for="(val, key, index) in config.roles")
			bunt-input(:value="key", label="role name", @input="set_role_name(key, $event)", name="n", :disabled="index < Object.keys(config.roles).length - 1")
			.role-config-permissions
				bunt-checkbox(v-for="p in config.available_permissions", :label="p", :value="val.includes(p)", name="p",
											@input="toggle_permission(key, p, $event)")
			bunt-checkbox(label="Grant role based on traits", :value="typeof config.trait_grants[key] !== 'undefined'", name="p",
										@input="toggle_trait_grants(key, $event)")
			bunt-input(label="Required traits (comma-separated)", @input="set_trait_grants(key, $event)",
									:disabled="typeof config.trait_grants[key] === 'undefined'", name="g"
									:value="config.trait_grants[key] ? config.trait_grants[key].join(', ') : ''")
		bunt-button.btn-add-role(@click="add_role") Add new role
		bunt-button.btn-save(@click="save", :loading="saving") Save

</template>
<script>
import api from 'lib/api'
import i18n from '../../i18n'

// TODO: validate color / id values

export default {
	data () {
		return {
			config: null,

			saving: false,
			error: null
		}
	},
	computed: {
		locales () {
			return i18n.availableLocales
		}
	},
	methods: {
		toggle_permission (role, perm, toggle) {
			if (toggle) {
				this.config.roles[role].push(perm)
			} else {
				this.$set(this.config.roles, role, this.config.roles[role].filter((i) => i !== perm))
			}
		},
		set_trait_grants (role, traits) {
			if (typeof this.config.trait_grants[role] !== 'undefined') {
				this.$set(this.config.trait_grants, role, traits.split(',').map((i) => i.trim()))
			}
		},
		add_role () {
			this.$set(this.config.roles, '', [])
		},
		toggle_trait_grants (role, toggle) {
			if (toggle) {
				this.$set(this.config.trait_grants, role, [])
			} else {
				this.$delete(this.config.trait_grants, role)
			}
		},
		set_role_name (old, n) {
			this.$set(this.config.roles, n, this.config.roles[old])
			this.$delete(this.config.roles, old)
			if (typeof this.config.trait_grants[old] !== 'undefined') {
				this.$set(this.config.trait_grants, n, this.config.trait_grants[old])
				this.$delete(this.config.trait_grants, old)
			}
		},
		async save () {
			// TODO validate connection limit is a number
			this.saving = true
			await api.call('world.config.patch', {
				roles: this.config.roles,
				trait_grants: this.config.trait_grants,
			})
			this.saving = false
			// TODO error handling
		},
	},
	async created () {
		// We don't use the global world object since it e.g. currently does not contain roles etc
		// TODO: Force reloading if world.updated is received from the server
		try {
			this.config = await api.call('world.config.get')
		} catch (error) {
			this.error = error
			console.log(error)
		}
	}
}
</script>
<style lang="stylus">
.c-permissionconfig
	.role
		border: 1px solid #cccccc
		border-radius: 4px
		padding: 5px 15px
		margin-bottom 15px
	.role-config-permissions
		display: flex
		flex-direction: row
		flex-wrap: wrap
		.bunt-checkbox
			width: 25%
	.btn-save
		margin-top: 16px
		margin-left: 16px
		themed-button-primary(size: large)
	.btn-add-role
		margin-top: 16px
		themed-button-secondary(size: large)
</style>
