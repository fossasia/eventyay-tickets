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
		bunt-button.btn-save(@click="save", :loading="saving") Save
</template>
<script>
import api from 'lib/api'
import i18n from '../../i18n'
import { required, integer, url } from 'vuelidate/lib/validators'

export default {
	data () {
		return {
			config: null,

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
		}
	},
	async created () {
		// We don't use the global world object since it e.g. currently does not contain locale and timezone
		// TODO: Force reloading if world.updated is received from the server
		try {
			this.config = await api.call('world.config.get')
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
			await api.call('world.config.patch', {
				title: this.config.title,
				locale: this.config.locale,
				dateLocale: this.config.dateLocale,
				timezone: this.config.timezone,
				connection_limit: this.config.connection_limit,
				bbb_defaults: this.config.bbb_defaults,
				pretalx: this.config.pretalx,
			})
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
</style>
