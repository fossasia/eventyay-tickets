<template lang="pug">
.c-permissionconfig
	bunt-progress-circular(size="huge", v-if="error == null && config == null")
	.error(v-if="error") We could not fetch the current configuration.
	div(v-if="config != null")
		h3 Roles
		div.role(v-for="(val, key, index) in config.roles")
			.role-head
				bunt-icon-button.chevron(@click.prevent="toggle_role(key)") {{ expandedRoles.includes(key) ? 'chevron-down' : 'chevron-right' }}
				h4(@click.prevent="toggle_role(key)") {{ key }}
				bunt-icon-button(@click.prevent="delete_role(key)") delete
			.role-config-permissions(v-if="expandedRoles.includes(key)")
				bunt-checkbox(v-for="p in config.available_permissions", :label="p", :value="val.includes(p)", name="p",
											@input="toggle_permission(key, p, $event)")
		div.role
			div.role-head
				bunt-input(label="role name", v-model="newRoleName", name="newRoleName")
				bunt-button.btn-add-role(@click="add_role", :disabled="!newRoleName || newRoleName in config.roles") Add new role
		h3 Roles assigned to traits globally (valid for ALL rooms)
		table.trait-grants
			thead
				tr
					th Role
					th Required traits
					th
			tbody
				tr(v-for="(val, key, index) in config.trait_grants")
					td
						bunt-input(:value="key", label="Role name", @input="set_trait_grant_role_name(key, $event)", name="n", :disabled="index < Object.keys(config.trait_grants).length - 1")
					td
						bunt-input(label="Required traits (comma-separated)", @input="set_trait_grants(key, $event)", name="g"
											:value="val ? val.map(i => (Array.isArray(i) ? i.join('|') : i)).join(', ') : ''")
					td.actions
						bunt-icon-button(@click="remove_trait_grant(key)") delete-outline
			tfoot
				tr
					td
						bunt-button.btn-add-role(@click="add_trait_grant") Add role
					td
					td
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
			expandedRoles: [],
			newRoleName: '',

			saving: false,
			error: null
		}
	},
	computed: {
		locales () {
			return i18n.availableLocales
		}
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
	},
	methods: {
		toggle_role (role) {
			if (this.expandedRoles.includes(role)) {
				this.expandedRoles = this.expandedRoles.filter((r) => r !== role)
			} else {
				this.expandedRoles.push(role)
			}
		},
		delete_role (role) {
			this.$delete(this.config.roles, role)
		},
		add_role () {
			if (this.newRoleName) {
				console.log(this.newRoleName)
				this.$set(this.config.roles, this.newRoleName, [])
				this.expandedRoles.push(this.newRoleName)
				this.newRoleName = ''
			}
		},
		toggle_permission (role, perm, toggle) {
			if (toggle) {
				this.config.roles[role].push(perm)
			} else {
				this.$set(this.config.roles, role, this.config.roles[role].filter((i) => i !== perm))
			}
		},
		set_trait_grants (role, traits) {
			if (typeof this.config.trait_grants[role] !== 'undefined') {
				this.$set(this.config.trait_grants, role, traits.split(',').map(
					(i) => i.trim().split('|').filter((j) => j.length > 0)
				).filter((i) => i.length > 0))
			}
		},
		remove_trait_grant (role) {
			this.$delete(this.config.trait_grants, role)
		},
		add_trait_grant () {
			this.$set(this.config.trait_grants, '', [])
		},
		set_trait_grant_role_name (old, n) {
			this.$set(this.config.trait_grants, n, this.config.trait_grants[old])
			this.$delete(this.config.trait_grants, old)
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
	.role-head
		display: flex
		flex-direction: row
		align-items: center
		.bunt-icon-button.chevron
			position: relative
			left: -6px
		h4, .bunt-input
			flex: auto 1 1
	.role-config-permissions
		display: flex
		flex-direction: row
		flex-wrap: wrap
		.bunt-checkbox
			width: 25%
	.trait-grants
		width: 100%
	.btn-save
		margin-top: 16px
		margin-left: 16px
		themed-button-primary(size: large)
	.btn-add-role
		themed-button-secondary()
</style>
