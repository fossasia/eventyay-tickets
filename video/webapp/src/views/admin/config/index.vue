<template lang="pug">
.c-admin-config
	nav.admin-nav
		h1 Configuration
		router-link(:to="{name: 'admin:config'}") Event
		router-link(:to="{name: 'admin:config:theme'}") Theme
		router-link(:to="{name: 'admin:config:permissions'}") Permissions
		router-link(:to="{name: 'admin:config:registration'}") User Profile
		router-link(:to="{name: 'admin:config:token-generator'}") Token Generator
		router-link(:to="{name: 'admin:config:audit-log'}") Audit Log
		router-link(:to="{name: 'admin:config:reports'}") Reports
	router-view
</template>
<script>

export default {
	name: 'AdminConfig'
}
</script>
<style lang="stylus">
.c-admin-config
	background white
	display: flex
	min-height: 0
	.admin-nav
		flex: none
		display: flex
		flex-direction: column
		background-color: $clr-grey-50
		border-right: border-separator()
		width: 218px
		> *:not(h1)
			flex: none
			height: 36px
			line-height: 36px
			padding: 0 24px
			color: $clr-primary-text-light
			&.router-link-exact-active
				background-color: $clr-grey-200
			&:hover
				background-color: $clr-grey-300
		h1
			font-size: 28px
			font-weight: 500
			margin: 0 0 0 24px
			height: 56px
			line-height: 56px

	.ui-page-header
		background-color: $clr-grey-50
		.bunt-icon-button
			margin-right: 8px
		h1
			flex: auto
			font-size: 24px
			font-weight: 500
			margin: 1px 16px 0 0
			ellipsis()
</style>
