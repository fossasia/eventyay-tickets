<template lang="pug">
.c-trait-grants
	.header
		.role Role
		.traits Required traits (comma separated)
		.actions
	.trait-grant(v-for="(val, key) of traitGrants")
		.role {{ key }}
		bunt-input.traits(name="trait-grant", :value="getTraitGrants(val)", @input="setTraitGrants(key, $event)", placeholder="(everyone)")
		.actions
			bunt-icon-button(@click="removeTraitGrant(key)") delete-outline
	.add-role
		bunt-select(name="remainingRoles", label="New role", :options="remainingRoles", v-model="newRole")
		bunt-button.btn-add-role(@click="addTraitGrant") Add role
</template>
<script>
export default {
	props: {
		traitGrants: Object,
		config: Object
	},
	data () {
		return {
			newRole: null
		}
	},
	computed: {
		remainingRoles () {
			const existingRoles = Object.keys(this.traitGrants)
			return Object.keys(this.config.roles).filter(role => !existingRoles.includes(role))
		}
	},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		getTraitGrants (trait) {
			return trait ? trait.map(i => (Array.isArray(i) ? i.join('|') : i)).join(', ') : ''
		},
		setTraitGrants (role, traits) {
			if (typeof this.traitGrants[role] !== 'undefined') {
				this.$set(this.traitGrants, role, traits.split(',').map(
					(i) => i.trim().split('|').filter((j) => j.length > 0)
				).filter((i) => i.length > 0))
			}
			this.$emit('changed')
		},
		removeTraitGrant (role) {
			this.$delete(this.traitGrants, role)
			this.$emit('changed')
		},
		addTraitGrant () {
			this.$set(this.traitGrants, this.newRole, [])
			this.newRole = null
			this.$emit('changed')
		}
	}
}
</script>
<style lang="stylus">
.c-trait-grants
	display: flex
	flex-direction: column
	.header, .trait-grant
		display: flex
		height: 56px
		flex: none
		align-items: center
		border-bottom: border-separator()
		.bunt-input
			padding-top: 0
		.role, .traits
			flex: 1
		.actions
			width: 56px
		& > *
			box-sizing: border-box
			padding-left: 8px
		> :first-child
			padding-left: 16px
		> :last-child
			padding-right: 8px
	.header
		border-bottom-width: 3px
		& > *
			font-weight: 600
			padding-left: 16px
	.trait-grant
		&:hover
			background-color: $clr-grey-100
	.add-role
		display: flex
		padding: 8px
		align-items: center
		.bunt-input
			padding-top: 0
			height: 36px
			margin-right: 8px
</style>
