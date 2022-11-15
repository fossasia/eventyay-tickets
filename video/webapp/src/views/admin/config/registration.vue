<template lang="pug">
.c-registrationconfig
	.ui-page-header
		h1 User Profile
	scrollbars(y)
		bunt-progress-circular(size="huge", v-if="!error && !config")
		.error(v-if="error") We could not fetch the current configuration.
		bunt-tabs(v-if="config")
			bunt-tab(header="Social Connections", v-scrollbar.y="")
				.ui-form-body
					p Let users connect to the following social networks when they first visit your event. Connecting to a social network fills the user's profile with data available from the social connection, like name, avatar and link to the social network profile.
					bunt-checkbox(name="social-twitter", v-model="socialTwitter") Twitter
					bunt-checkbox(name="social-linkedin", v-model="socialLinkedIn") LinkedIn
					bunt-checkbox(name="social-gravatar", v-model="socialGravatar") Gravatar
			bunt-tab(header="Additional Fields", v-scrollbar.y="")
				.additional-fields-form(v-if="config")
					// TODO REORDER
					table.additional-fields
							thead
								tr
									th Name
									th Type
									th ID
									th
									th Include in search queries
									th
							tbody
								tr(v-for="(field, index) in config.profile_fields")
									td
										bunt-input(v-model="field.label", label="Label", name="label")
									td
										bunt-select(v-model="field.type", label="Type", name="type", :options="['text', 'textarea', 'select', 'link']")
									td
										//- ids are needed to match external tools' (pretix) supplied fields
										bunt-input(v-model="field.id", label="ID", name="id")
									td
										bunt-input(v-if="field.type === 'select'", v-model="field.choices", label="Choices (comma seperated)", name="choices")
										bunt-select.link-network(v-if="field.type === 'link'", v-model="field.network", label="Link Type", name="link-type", :options="socialNetworks")
											template(slot-scope="{ option }")
												.mdi(:class="`mdi-${option}`")
												.label {{ option }}
									td
										bunt-checkbox(v-model="field.searchable", name="searchable")
									td.actions
										bunt-icon-button(@click="removeField(index)") delete-outline
							tfoot
								tr
									td
										bunt-button(@click="addField") Add field
									td
									td
									td
									td
									td
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") Save
</template>
<script>
import api from 'lib/api'
import { v4 as uuid } from 'uuid'

const socialNetworks = [
	'website',
	'facebook',
	'github',
	'instagram',
	'linkedin',
	'mastodon',
	'pinterest',
	'twitter',
	'vimeo',
	'xing',
	'youtube',
]

function generateSocialComputed (network) {
	return {
		get () {
			return this.config?.social_logins.includes(network)
		},
		set (value) {
			if (value) {
				this.config.social_logins.push(network)
			} else {
				this.config.social_logins.splice(this.config.social_logins.indexOf(network), 1)
			}
		}
	}
}

export default {
	data () {
		return {
			config: null,
			saving: false,
			error: null,
			socialNetworks
		}
	},
	computed: {
		socialTwitter: generateSocialComputed('twitter'),
		socialLinkedIn: generateSocialComputed('linkedin'),
		socialGravatar: generateSocialComputed('gravatar')
	},
	async created () {
		// TODO: Force reloading if world.updated is received from the server
		try {
			this.config = await api.call('world.config.get')
		} catch (error) {
			this.error = error
			console.log(error)
		}
	},
	methods: {
		addField () {
			this.config.profile_fields.push({id: uuid(), label: '', type: 'text', searchable: false})
		},
		removeField (field) {
			this.$delete(this.config.profile_fields, field)
		},
		async save () {
			this.saving = true
			try {
				await api.call('world.config.patch', {
					profile_fields: this.config.profile_fields,
					social_logins: this.config.social_logins
				})
			} catch (error) {
				console.error(error.apiError || error)
				this.error = error.apiError?.details?.social_logins?.join(', ') || error.apiError?.code || error
			} finally {
				this.saving = false
			}
		},
	}
}
</script>
<style lang="stylus">
.c-registrationconfig
	flex: auto
	display: flex
	flex-direction: column
	.bunt-tabs
		tabs-style(active-color: var(--clr-primary), indicator-color: var(--clr-primary), background-color: transparent)
		margin-bottom: 0
	.bunt-tabs-header
		border-bottom: border-separator()
	.bunt-tabs, .bunt-tabs-body, .bunt-tab
		flex: auto
		display: flex
		flex-direction: column
		min-height: 0
	h2
		margin: 16px
	.bunt-checkbox
		margin-bottom: 8px
	.additional-fields-form
		.additional-fields
			width 100%
			th
				text-align: left
				border-bottom: 1px solid #ccc
				padding: 10px
			td
				vertical-align center
		.link-network
				ul li
					display: flex
					.mdi
						margin-right: 8px
		.btn-save
			margin-top: 16px
			themed-button-primary(size: large)

// hack specificity to create fallback icon for things not in mdi
:where(.c-registrationconfig .link-network .mdi)::before
	content: "\F0339"
</style>
