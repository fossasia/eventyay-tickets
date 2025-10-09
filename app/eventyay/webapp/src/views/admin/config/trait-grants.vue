<!-- eslint-disable vue/no-mutating-props -->
<template lang="pug">
.c-trait-grants
	.header
		.role Role
		.traits Required traits (comma separated)
		.actions
	.trait-grant(v-for="(val, key) of traitGrants")
		.role {{ key }}
		bunt-input.traits(name="trait-grant", :modelValue="getTraitGrants(val)", @update:modelValue="setTraitGrants(key, $event)", placeholder="(everyone)")
		.actions
			bunt-icon-button(@click="removeTraitGrant(key)") delete-outline
	.add-role
		bunt-select(name="remainingRoles", label="New role", :options="remainingRoles", v-model="newRole")
		bunt-button.btn-add-role(@click="addTraitGrant") Add role
</template>
<script setup>
import { ref, reactive, watch, computed, toRefs } from 'vue'
import { parseTraitGrants, stringifyTraitGrants } from 'lib/traitGrants'

const props = defineProps({
	traitGrants: { type: Object, default: () => ({}) },
	config: { type: Object, default: () => ({ roles: {} }) }
})
const emit = defineEmits(['changed', 'update:traitGrants'])

const newRole = ref(null)
const localTraitGrants = reactive({})

const { traitGrants, config } = toRefs(props)

watch(
	() => props.traitGrants,
	(val) => {
		// Reset reactive object to preserve reactivity references
		Object.keys(localTraitGrants).forEach(k => delete localTraitGrants[k])
		Object.assign(localTraitGrants, JSON.parse(JSON.stringify(val || {})))
	},
	{ immediate: true, deep: true }
)

const remainingRoles = computed(() => {
	const existingRoles = Object.keys(localTraitGrants)
	return Object.keys(config.value.roles || {}).filter(role => !existingRoles.includes(role))
})

function getTraitGrants(traits) {
	return stringifyTraitGrants(traits)
}

function emitUpdate() {
	// Deep clone to avoid exposing internal reactive object
	emit('update:traitGrants', JSON.parse(JSON.stringify(localTraitGrants)))
	emit('changed')
}

function setTraitGrants(role, traits) {
	if (typeof localTraitGrants[role] !== 'undefined') {
		localTraitGrants[role] = parseTraitGrants(traits)
	}
	emitUpdate()
}

function removeTraitGrant(role) {
	if (Object.prototype.hasOwnProperty.call(localTraitGrants, role)) {
		delete localTraitGrants[role]
		emitUpdate()
	}
}

function addTraitGrant() {
	if (!newRole.value) return
	localTraitGrants[newRole.value] = []
	newRole.value = null
	emitUpdate()
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
