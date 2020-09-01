<template lang="pug">
.c-admin-config
	bunt-tabs
		bunt-tab(id="main", header="Main")
			main-config(v-scrollbar.y="")
		bunt-tab(id="theme", header="Theme")
			theme-config(v-scrollbar.y="")
		bunt-tab(id="permissions", header="Permissions")
			permission-config(v-scrollbar.y="")
		bunt-tab(id="tokengen", header="Token generator")
			token-generator(v-scrollbar.y="")
		bunt-tab(id="auditlog", header="Audit log")
			audit-log(v-scrollbar.y="")
</template>
<script>
import ThemeConfig from 'components/config/ThemeConfig'
import MainConfig from 'components/config/MainConfig'
import PermissionConfig from 'components/config/PermissionConfig'
import TokenGenerator from 'components/config/TokenGenerator'
import AuditLog from 'components/config/AuditLog'

export default {
	name: 'AdminConfig',
	components: { ThemeConfig, MainConfig, PermissionConfig, TokenGenerator, AuditLog },
}
</script>
<style lang="stylus">
.c-admin-config
	background white
	display: flex
	flex-direction: column
	min-height: 0

	h2
		margin: 16px
	.bunt-tabs
		tabs-style(active-color: var(--clr-primary), indicator-color: var(--clr-primary), background-color: transparent)
		flex-grow: 1
		display: flex
		min-height: 0
		flex-direction: column

	.bunt-tabs-body
		padding: 16px
		flex-grow: 1
		min-height: 0
		display: flex
		flex-direction: column

	.bunt-tab
		flex-grow: 1
		min-height: 0
		display: flex
		flex-direction: column

	.bunt-tab > *
		flex-grow: 1
		min-height: 0
</style>
