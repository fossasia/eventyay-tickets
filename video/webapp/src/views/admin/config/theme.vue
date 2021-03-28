<template lang="pug">
.c-themeconfig
	.ui-page-header
		h1 Theme Config
	scrollbars(y)
		bunt-progress-circular(size="huge", v-if="!error && !config")
		.error(v-if="error") We could not fetch the current configuration.
		template(v-if="config")
			.ui-form-body
				color-picker(name="colors_primary", v-model="config.theme.colors.primary", label="Primary color", :validation="$v.config.theme.colors.primary")
				color-picker(name="colors_sidebar", v-model="config.theme.colors.sidebar", label="Sidebar color", :validation="$v.config.theme.colors.sidebar")
				color-picker(name="colors_bbb_background", v-model="config.theme.colors.bbb_background", label="BBB background color", :validation="$v.config.theme.colors.bbb_background")
				upload-url-input(name="logo_url", v-model="config.theme.logo.url", label="Logo", :validation="$v.config.theme.logo.url")
				bunt-checkbox(name="logo_fit", v-model="config.theme.logo.fitToWidth", label="Fit logo to width")
				upload-url-input(name="streamoffline_url", v-model="config.theme.streamOfflineImage", label="Stream offline image", :validation="$v.config.theme.streamOfflineImage")
			.text-overwrites
				.header
					div Original
					div Custom translation
				tr.overwrite(v-for="(val, key) in strings")
					.source
						.key {{ key }}
						.value {{ val }}
					bunt-input(v-model="config.theme.textOverwrites[key]", :name="key")
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") Save
		.errors {{ validationErrors.join(', ') }}
</template>
<script>
import api from 'lib/api'
import { DEFAULT_COLORS, DEFAULT_LOGO } from 'theme'
import i18n from 'i18n'
import ColorPicker from 'components/ColorPicker'
import UploadUrlInput from 'components/UploadUrlInput'
import ValidationErrorsMixin from 'components/mixins/validation-errors'
import { required, color, url } from 'lib/validators'

export default {
	components: { ColorPicker, UploadUrlInput },
	mixins: [ValidationErrorsMixin],
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
						required: required('primary color is required'),
						color: color('color must be in 3 or 6 digit hex format')
					},
					sidebar: {
						required: required('sidebar color is required'),
						color: color('color must be in 3 or 6 digit hex format')
					},
					bbb_background: {
						required: required('BBB background color is required'),
						color: color('color must be in 3 or 6 digit hex format')
					},
				},
				logo: {
					url: {
						url: url('must be a valid url')
					}
				},
				streamOfflineImage: {
					url: url('must be a valid url')
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
	flex: auto
	display: flex
	flex-direction: column
	.text-overwrites
		display: flex
		flex-direction: column
		> *
			display: flex
			align-items: center
			height: 52px
			> *
				width: 50%
		.header
			text-align: left
			border-bottom: border-separator()
			padding: 10px
			font-weight: 600
			font-size: 18px
			position: sticky
			top: 0
			background-color: $clr-white
			z-index: 1
		.overwrite
			&:hover
				background-color: $clr-grey-100
			.source
				display: flex
				flex-direction: column
				justify-content: space-around
				padding-left: 8px
				.key
					color: $clr-secondary-text-light
					font-size: 12px
					font-style: italic
			.bunt-input
				input-style(size: compact)
				padding-top: 0
				margin-right: 8px
</style>
