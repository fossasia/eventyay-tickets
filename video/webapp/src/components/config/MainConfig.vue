<template lang="pug">
.c-mainconfig
	bunt-progress-circular(size="huge", v-if="error == null && config == null")
	.error(v-if="error") We could not fetch the current configuration.
	.main-form(v-if="config != null")
		bunt-input(v-model="config.title", label="Title", name="title", :validation="$v.config.title")
		bunt-select(v-model="config.locale", label="Language", name="locale", :options="locales")
		bunt-input(v-model="config.dateLocale", label="Date locale", name="dateLocale")
		bunt-input(v-model="config.timezone", label="Time zone", name="timezone", :validation="$v.config.timezone")
		bunt-input(v-model="config.connection_limit", label="Connection limit", name="connection_limit", hint="Set to 0 to allow unlimited connections per user", :validation="$v.config.connection_limit")
		bunt-input(v-model="config.pretalx.domain", label="pretalx domain", name="pretalx_domain", :validation="$v.config.pretalx.domain")
		bunt-input(v-model="config.pretalx.event", label="pretalx event slug", name="pretalx_event", :validation="$v.config.pretalx.event")
		bunt-checkbox(v-model="config.bbb_defaults.record", label="Allow recording in newly-created BBB rooms", name="bbb_defaults_record")
		bunt-input-outline-container(label="hls.js config", :class="{error: $v.hlsConfig.$invalid}")
			textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur", v-model="hlsConfig")
		.json-error-message {{ $v.hlsConfig.$params.isJson.message }}
		bunt-button.btn-save(@click="save", :loading="saving") Save
</template>
<script>
import api from 'lib/api'
import i18n from '../../i18n'
import { required, integer, url } from 'vuelidate/lib/validators'
import { isJson } from 'lib/validators'

export default {
	data () {
		return {
			config: null,
			hlsConfig: '',
			saving: false,
			error: null
		}
	},
	computed: {
		locales () {
			return i18n.availableLocales
		}
	},
	validations: {
		config: {
			title: {
				required
			},
			timezone: {
				required
			},
			connection_limit: {
				required,
				integer
			},
			pretalx: {
				domain: {
					url
				}
			},
		},
		hlsConfig: {
			isJson: isJson()
		}
	},
	async created () {
		// We don't use the global world object since it e.g. currently does not contain locale and timezone
		// TODO: Force reloading if world.updated is received from the server
		try {
			this.config = await api.call('world.config.get')
			this.hlsConfig = JSON.stringify(this.config.videoPlayer?.['hls.js'] || undefined, null, 2)
		} catch (error) {
			this.error = error
			console.log(error)
		}
	},
	methods: {
		async save () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			// TODO validate connection limit is a number
			this.saving = true
			const patch = {
				title: this.config.title,
				locale: this.config.locale,
				dateLocale: this.config.dateLocale,
				timezone: this.config.timezone,
				connection_limit: this.config.connection_limit,
				bbb_defaults: this.config.bbb_defaults,
				pretalx: this.config.pretalx,
			}
			if (this.hlsConfig) {
				patch.videoPlayer = {
					'hls.js': JSON.parse(this.hlsConfig)
				}
			} else {
				patch.videoPlayer = null
			}
			await api.call('world.config.patch', patch)
			this.saving = false
			// TODO error handling
		},
	}
}
</script>
<style lang="stylus">
.c-mainconfig
	.btn-save
		margin-top: 16px
		themed-button-primary(size: large)
	.bunt-input-outline-container
		margin-top: 16px
		&.error
			label
				color: $clr-danger
			.outline
				stroke: $clr-danger
				stroke-width: 2px
		textarea
			background-color: transparent
			border: none
			outline: none
			resize: vertical
			min-height: 120px
			padding: 0 8px
	.json-error-message
		color: $clr-danger
		margin: 4px
</style>
