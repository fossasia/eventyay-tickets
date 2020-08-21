<template lang="pug">
.c-themeconfig
	bunt-progress-circular(size="huge", v-if="error == null && config == null")
	.error(v-if="error") We could not fetch the current configuration.
	.theme-form(v-if="config != null")
		bunt-input(v-model="config.theme.colors.primary", label="Primary color", name="colors_primary", :validation="$v.config.theme.colors.primary")
		bunt-input(v-model="config.theme.colors.sidebar", label="Sidebar color", name="colors_sidebar", :validation="$v.config.theme.colors.sidebar")
		bunt-input(v-model="config.theme.colors.bbb_background", label="BBB background color", name="colors_bbb_background", :validation="$v.config.theme.colors.bbb_background")
		upload-url-input(v-model="config.theme.logo.url", label="Logo", name="logo_url", :validation="$v.config.theme.logo.url")
		bunt-checkbox(v-model="config.theme.logo.fitToWidth", label="Fit logo to width", name="logo_fit")
		upload-url-input(v-model="config.theme.streamOfflineImage", label="Stream offline image", name="streamoffline_url", :validation="$v.config.theme.streamOfflineImage")
		table.text-overwrites
			thead
				tr
					th Original
					th Custom translation
			tbody
				tr(v-for="(val, key) in strings")
					td <small>{{ key }}</small><br>{{ val }}
					bunt-input(v-model="config.theme.textOverwrites[key]", :name="key")
		bunt-button.btn-save(@click="save", :loading="saving") Save
</template>
<script>
import api from 'lib/api'
import { DEFAULT_COLORS, DEFAULT_LOGO } from '../../theme'
import i18n from '../../i18n'
import UploadUrlInput from './UploadUrlInput'
import { required, helpers, url } from 'vuelidate/lib/validators'

const color = helpers.regex('color', /^#[a-zA-Z0-9]{3,6}$/)
const relative = helpers.regex('relative', /^\/.*$/)
const urlOrRelative = (value) => (!helpers.req(value) || url(value) || relative(value))

export default {
	components: { UploadUrlInput },
	data () {
		return {
			// We do not use the global config object since we cannot rely on it being up to date (theme is only updated
			// during application load).
			config: null,

			saving: false,
			error: null
		}
	},
	computed: {
		strings () {
			return i18n.messages[i18n.locale]
		},
	},
	validations: {
		config: {
			theme: {
				colors: {
					primary: {
						required,
						color
					},
					sidebar: {
						required,
						color
					},
					bbb_background: {
						required,
						color
					},
				},
				logo: {
					url: {
						urlOrRelative
					}
				},
				streamOfflineImage: {
					url
				}
			},
		}
	},
	async created () {
		// TODO: Force reloading if world.updated is received from the server
		try {
			this.config = await api.call('world.config.get')

			// Enforce some defaults
			this.config.theme = {logo: {}, colors: {}, streamOfflineImage: null, textOverwrites: {}, ...this.config.theme}
			this.config.theme.colors = {...DEFAULT_COLORS, ...this.config.theme.colors}
			this.config.theme.logo = {...DEFAULT_LOGO, ...this.config.theme.logo}
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

			location.reload() // Theme config is only activated after reload
		},
	}
}
</script>
<style lang="stylus">
.c-themeconfig
	.text-overwrites
		th
			text-align: left
			border-bottom: 1px solid #ccc
			padding: 10px
		td
			vertical-align center
			width: 50%
	.btn-save
		margin-top: 16px
		themed-button-primary(size: large)
</style>
