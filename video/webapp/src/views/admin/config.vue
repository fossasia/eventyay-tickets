<template lang="pug">
.c-admin-config(v-scrollbar.y="")
	.header
		h2 Configuration
	bunt-tabs
		bunt-tab(id="main", header="Main")
			main-config()
		bunt-tab(id="theme", header="Theme")
			theme-config()
		bunt-tab(id="permissions", header="Permissions")
			permission-config()
		bunt-tab(id="tokengen", header="Token generator")
			token-generator()
</template>
<script>
import ThemeConfig from 'components/config/ThemeConfig'
import MainConfig from 'components/config/MainConfig'
import PermissionConfig from 'components/config/PermissionConfig'
import TokenGenerator from 'components/config/TokenGenerator'

export default {
	name: 'AdminConfig',
	components: { ThemeConfig, MainConfig, PermissionConfig, TokenGenerator },
}
</script>
<style lang="stylus">
.c-admin-config
	background white

	h2
		margin: 16px
	.bunt-tabs
		tabs-style(active-color: var(--clr-primary), indicator-color: var(--clr-primary), background-color: transparent)
	.bunt-tabs-body
		padding: 16px
</style>
