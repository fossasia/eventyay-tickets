<template lang="pug">
.c-admin-config
	bunt-tabs
		bunt-tab(id="main", header="Main", v-scrollbar.y="")
			main-config
		bunt-tab(id="theme", header="Theme", v-scrollbar.y="")
			theme-config
		bunt-tab(id="permissions", header="Permissions", v-scrollbar.y="")
			permission-config
		bunt-tab(id="tokengen", header="Token generator", v-scrollbar.y="")
			token-generator
		bunt-tab(id="registration", header="Registration", v-scrollbar.y="")
			registration-config
		bunt-tab(id="auditlog", header="Audit log", v-scrollbar.y="")
			audit-log
		bunt-tab(id="reports", header="Reports", v-scrollbar.y="")
			reports(v-scrollbar.y="")
</template>
<script>
import ThemeConfig from './ThemeConfig'
import MainConfig from './MainConfig'
import PermissionConfig from './PermissionConfig'
import TokenGenerator from './TokenGenerator'
import AuditLog from './AuditLog'
import RegistrationConfig from './RegistrationConfig'
import Reports from './Reports'

export default {
	name: 'AdminConfig',
	components: { ThemeConfig, MainConfig, PermissionConfig, TokenGenerator, AuditLog, RegistrationConfig, Reports },
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
		margin: 0
		flex: auto
		display: flex
		min-height: 0
		flex-direction: column
	.bunt-tabs-header
		border-bottom: border-separator()

	.bunt-tabs-body
		flex: auto
		min-height: 0
		display: flex
		flex-direction: column

	.bunt-tab
		flex: auto
		min-height: 0
		display: flex
		flex-direction: column
		> :not(.bunt-scrollbar-rail-wrapper-y)
			padding: 16px
			display: flex
			flex: auto
			flex-direction: column
</style>
