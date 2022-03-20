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
				bunt-checkbox(name="iframe-consent-blocker", v-model="enableBlocker", label="Enable consent blocker for all iframes")
			.iframe-domains
				.header
					.domain Domain
					.policy-link Privacy policy link
					.actions
				.iframe-domain(v-for="iframeDomain of iframeDomains")
					bunt-input.domain(name="domain", v-model="iframeDomain.domain", placeholder="example.com")
					bunt-input.policy-link(name="policy-link", v-model="iframeDomain.policyLink", placeholder="https://example.com/privacy")
					.actions
						bunt-icon-button(@click="removeIframeDomain(iframeDomain)") delete-outline
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

			// Cleanup empty strings in text overwrites
			for (const key of Object.keys(this.config.theme.textOverwrites)) {
				if (!this.config.theme.textOverwrites[key]) {
					this.$delete(this.config.theme.textOverwrites, key)
				}
			}

			this.saving = true
			await api.call('world.config.patch', {theme: this.config.theme})
			this.saving = false
			// TODO error handling
		},
		addIframeDomain () {
			this.iframeDomains.push({
				domain: '',
				policyLink: ''
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
			.domain, .policy-link
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
		.btn-add-domain
			themed-button-secondary()
			align-self: flex-start
			margin: 8px
</style>
