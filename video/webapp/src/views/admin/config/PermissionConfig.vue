<template lang="pug">
.c-permissionconfig
	bunt-progress-circular(size="huge", v-if="error == null && config == null")
	.error(v-if="error") We could not fetch the current configuration.
	div(v-if="config != null")
		h3 Roles
		div.role(v-for="(val, key, index) of config.roles")
			.role-head
				bunt-icon-button.chevron(@click.prevent="toggleRole(key)") {{ expandedRoles.includes(key) ? 'chevron-down' : 'chevron-right' }}
				h4(@click.prevent="toggleRole(key)") {{ key }}
				bunt-icon-button(@click.prevent="deleteRole(key)") delete
			.role-config-permissions(v-if="expandedRoles.includes(key)")
				bunt-checkbox(v-for="p of config.available_permissions", :label="p", :value="val.includes(p)", name="p",
											@input="togglePermission(key, p, $event)")
		div.role
			div.role-head
				bunt-input(label="role name", v-model="newRoleName", name="newRoleName")
				bunt-button.btn-add-role(@click="addRole", :disabled="!newRoleName || newRoleName in config.roles") Add new role
		h3 Roles assigned to traits globally (valid for ALL rooms)
		table.trait-grants
			thead
				tr
					th Role
					th Required traits
					th
			tbody
				tr(v-for="(val, key, index) of config.trait_grants")
					td: bunt-input(:value="key", label="Role name", @input="setTraitGrantRoleName(config, key, $event)", name="n", :disabled="index < Object.keys(config.trait_grants).length - 1")
					td: bunt-input(label="Required traits (comma-separated)", @input="setTraitGrants(config, key, $event)", name="g"
											:value="val ? val.map(i => (Array.isArray(i) ? i.join('|') : i)).join(', ') : ''")
					td.actions
						bunt-icon-button(@click="removeTraitGrant(config, key)") delete-outline
			tfoot
				tr
					td: bunt-button.btn-add-role(@click="addTraitGrant(config)") Add role
					td
					td
		h3 Roles assigned to traits PER ROOM
		.room-traits(v-for="room of rooms")
			h4 {{ room.name }}
			table.trait-grants
				thead
					tr
						th Role
						th Required traits
						th
				tbody
					tr(v-for="(val, key, index) of room.trait_grants")
						td: bunt-input(:value="key", label="Role name", @input="setTraitGrantRoleName(room, key, $event)", name="n", :disabled="index < Object.keys(room.trait_grants).length - 1")
						td: bunt-input(label="Required traits (comma-separated)", @input="setTraitGrants(room, key, $event)", name="g"
												:value="val ? val.map(i => (Array.isArray(i) ? i.join('|') : i)).join(', ') : ''")
						td.actions: bunt-icon-button(@click="removeTraitGrant(room, key)") delete-outline
				tfoot
					tr
						td: bunt-button.btn-add-role(@click="addTraitGrant(room)") Add role
						td
						td
		bunt-button.btn-save(@click="save", :loading="saving") Save
</template>
<script>
import api from 'lib/api'
import i18n from 'i18n'
// TODO: validate color / id values

export default {
	data () {
		return {
			config: null,
			expandedRoles: [],
			newRoleName: '',
			rooms: null,
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
			this.rooms = await api.call('room.config.list')
		} catch (error) {
			this.error = error
			console.log(error)
		}
	},
	methods: {
		toggleRole (role) {
			if (this.expandedRoles.includes(role)) {
				this.expandedRoles = this.expandedRoles.filter((r) => r !== role)
			} else {
				this.expandedRoles.push(role)
			}
		},
		deleteRole (role) {
			this.$delete(this.config.roles, role)
		},
		addRole () {
			if (this.newRoleName) {
				this.$set(this.config.roles, this.newRoleName, [])
				this.expandedRoles.push(this.newRoleName)
				this.newRoleName = ''
			}
		},
		togglePermission (role, perm, toggle) {
			if (toggle) {
				this.config.roles[role].push(perm)
			} else {
				this.$set(this.config.roles, role, this.config.roles[role].filter((i) => i !== perm))
			}
		},
		setTraitGrants (target, role, traits) {
			if (typeof target.trait_grants[role] !== 'undefined') {
				this.$set(target.trait_grants, role, traits.split(',').map(
					(i) => i.trim().split('|').filter((j) => j.length > 0)
				).filter((i) => i.length > 0))
			}
		},
		removeTraitGrant (target, role) {
			this.$delete(target.trait_grants, role)
		},
		addTraitGrant (target) {
			this.$set(target.trait_grants, '', [])
		},
		setTraitGrantRoleName (target, old, n) {
			this.$set(target.trait_grants, n, target.trait_grants[old])
			this.$delete(target.trait_grants, old)
		},
		async save () {
			// TODO validate connection limit is a number
			this.saving = true
			await api.call('world.config.patch', {
				roles: this.config.roles,
				trait_grants: this.config.trait_grants,
			})
			// TODO only patch changed rooms
			for (const room of this.rooms) {
				await api.call('room.config.patch', {
					room: room.id,
					trait_grants: room.trait_grants
				})
			}
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
