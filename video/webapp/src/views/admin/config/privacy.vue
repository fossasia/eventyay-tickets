<template lang="pug">
.c-privacyconfig
	.ui-page-header
		h1 Theme Config
	scrollbars(y)
		bunt-progress-circular(size="huge", v-if="!error && !config")
		.error(v-if="error") We could not fetch the current configuration.
		template(v-if="config")
			.ui-form-body
				h3 IFrame Consent Blocker
				p Enable or disable iframe blocking behaviour for matching domains and the default behaviour if no matching domains are found. Every iframe url domain that ends with a configured domain here will match. For example: configuring "youtube.com" on this page will match all iframes with "www.youtube.com".
			.iframe-domains
				.header
					.enabled Enable block
					.domain For domain
					.policy-link Privacy policy link
					.actions
				.iframe-domain(v-for="iframeDomain of iframeDomains")
					bunt-checkbox.enabled(name="enabled", v-model="iframeDomain.enabled")
					div.domain(v-if="iframeDomain.domain === 'default'") default
					bunt-input.domain(v-else, name="domain", v-model="iframeDomain.domain", placeholder="example.com")
					bunt-input.policy-link(name="policy-link", v-model="iframeDomain.policy_url", placeholder="https://example.com/privacy")
					.actions
						bunt-icon-button(v-if="iframeDomain.domain !== 'default'", @click="removeIframeDomain(iframeDomain)") delete-outline
				bunt-button.btn-add-domain(@click="addIframeDomain") Add domain
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") Save
		.errors {{ validationErrors.join(', ') }}
</template>
<script>
import api from 'lib/api'
import ValidationErrorsMixin from 'components/mixins/validation-errors'

export default {
	components: { },
	mixins: [ValidationErrorsMixin],
	data () {
		return {
			// We do not use the global config object since we cannot rely on it being up to date (theme is only updated
			// during application load).
			config: null,

			saving: false,
			error: null,
			enableBlocker: false,
			iframeDomains: []
		}
	},
	computed: {

	},
	validations: {
		config: {
		}
	},
	async created () {
		// TODO: Force reloading if world.updated is received from the server
		try {
			this.config = await api.call('world.config.get')
			const defaultEntry = this.config.iframe_blockers?.default
			// always have a default first entry
			this.iframeDomains = [{
				domain: 'default',
				enabled: defaultEntry?.enabled ?? false,
				policy_url: defaultEntry?.policy_url ?? ''
			}]
			this.iframeDomains.push(...Object.entries(this.config.iframe_blockers)
				.filter(([domain, domainConfig]) => domain !== 'default')
				.map(([domain, {enabled, policy_url}]) => ({
					domain,
					enabled,
					policy_url
				}))
			)
			// Enforce some defaults
		} catch (error) {
			this.error = error
			console.log(error)
		}
	},
	methods: {
		async save () {
			this.$v.$touch()
			if (this.$v.$invalid) return

			const iframeBlockers = Object.fromEntries(this.iframeDomains.map(({domain, enabled, policy_url}) => [
				domain,
				{
					enabled,
					policy_url
				}
			]))

			this.saving = true
			await api.call('world.config.patch', {iframe_blockers: iframeBlockers})
			this.saving = false
			// TODO error handling
		},
		addIframeDomain () {
			this.iframeDomains.push({
				domain: '',
				enabled: true,
				policy_url: ''
			})
		},
		removeIframeDomain (iframeDomain) {
			const index = this.iframeDomains.indexOf(iframeDomain)
			if (index < 0) return
			this.iframeDomains.splice(index, 1)
		}
	}
}
</script>
<style lang="stylus">
.c-privacyconfig
	flex: auto
	display: flex
	flex-direction: column
	.iframe-domains
		display: flex
		flex-direction: column
		.header, .iframe-domain
			display: flex
			height: 56px
			flex: none
			align-items: center
			border-bottom: border-separator()
			.bunt-input
				input-style(size: compact)
				padding-top: 0
				margin-right: 8px
			.enabled
				width: 100px
			.domain, .policy-link
				flex: 1
			.actions
				width: 56px
			& > *
				box-sizing: border-box
				padding-left: 16px
			> :first-child
				padding-left: 16px
			> :last-child
				padding-right: 8px
		.header
			border-bottom-width: 3px
			& > *
				font-weight: 600
		.trait-grant
			&:hover
				background-color: $clr-grey-100
		.btn-add-domain
			themed-button-secondary()
			align-self: flex-start
			margin: 8px
</style>
