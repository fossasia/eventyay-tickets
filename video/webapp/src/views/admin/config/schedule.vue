<template lang="pug">
.c-scheduleconfig
	.ui-page-header
	scrollbars(y)
		bunt-progress-circular(size="huge", v-if="!error && !config")
		.error(v-if="error") We could not fetch the current configuration.
		.ui-form-body(v-if="config")
			bunt-select(name="source", label="Schedule source", v-model="source", :options="sourceOptions")
			template(v-if="source === 'pretalx'")
				p To use pretalx for your event, enter the domain of the pretalx server you use and the short form name of your event. We'll then pull in the schedule automatically and keep it updated. You must be using pretalx version 2 or later.
				bunt-input(name="domain", label="pretalx domain", v-model="config.pretalx.domain", placeholder="e.g. https://pretalx.com/", hint="must have the format https://…/", :validation="$v.config.pretalx.domain")
				bunt-input(name="event", label="pretalx event slug", v-model="config.pretalx.event", placeholder="e.g. democon")
				h2 Pretalx Connection
				template(v-if="config.pretalx.connected")
					p Your pretalx instance has successfully connected to venueless.
					p(v-if="lastPush") Last time pretalx pushed a new schedule version: {{ lastPush }}
				template(v-else)
					p To enable automatic schedule update pushes from pretalx to venueless, activate the pretalx-venueless plugin and complete the connection procedure.
					h3 Step 1: Install and activate the pretalx-venueless plugin
					.pretalx-status(v-if="isPretalxPluginInstalled") pretalx-venueless plugin has been detected!
					.pretalx-status.plugin-not-installed(v-if="!isPretalxPluginInstalled")
						| pretalx-venueless plugin not installed/activated or domain + event not a valid pretalx instance.
						br
						| Please install and activate the plugin in #[a(:href="`${pretalxDomain}orga/event/${config.pretalx.event}/settings/plugins`", target="_blank") your pretalx event plugin settings].
					h3 Step 2: Connect pretalx to venueless
					.pretalx-status(v-if="config.pretalx.connected") Pretalx-venueless connection active!
					.pretalx-status.not-connected(v-else) Pretalx is not connected to venueless.
					bunt-button#btn-pretalx-connect(:disabled="!isPretalxPluginInstalled", :loading="connecting", @click="startPretalxConnect") {{ !config.pretalx.connected ? 'Connect to pretalx' : 'Reconnect to pretalx' }}
			template(v-else-if="source === 'url'")
				p To automatically load the schedule from an external system, enter an URL here. Note that the URL must be a JSON file compliant with the pretalx schedule widget API version 2.
				bunt-input(name="url", label="JSON URL", v-model="config.pretalx.url", placeholder="e.g. https://website.com/event.json", :validation="$v.config.pretalx.url")
			template(v-else-if="source === 'file'")
				p If you don't use pretalx, you can upload your schedule as a Microsoft Excel file (XLSX) with a specific setup.
				p
					a(href="/schedule_ex_en.xlsx", target="_blank") Download English sample file
					| {{ " / " }}
					a(href="/schedule_ex_de.xlsx", target="_blank") Download German sample file
				upload-url-input(name="schedule-file", v-model="config.pretalx.url", label="Schedule file", :upload-url="uploadUrl", accept="application/vnd.ms-excel, .xlsx", :validation="$v.config.pretalx.url")
			template(v-else-if="source === 'conftool'")
				p conftool is controlled by the main conftool settings.
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") Save
		.errors {{ validationErrors.join(', ') }}
</template>
<script>
// TODO:
// - trailing slash validation/enforcement for prexalx domain
// - immediately disconnect pretalx here if domain or event changes
import moment from 'moment'
import config from 'config'
import api from 'lib/api'
import { required, url } from 'lib/validators'
import UploadUrlInput from 'components/UploadUrlInput'
import ValidationErrorsMixin from 'components/mixins/validation-errors'

export default {
	components: { UploadUrlInput },
	mixins: [ValidationErrorsMixin],
	data () {
		return {
			uploadUrl: config.api.scheduleImport,
			showUpload: false, // HACK we need an extra flag to show an empty file upload, since url and file use the same config field
			isPretalxPluginInstalled: false,
			config: null,
			saving: false,
			connecting: false,
			error: null
		}
	},
	computed: {
		sourceOptions () {
			const sourceOptions = [
				{id: null, label: 'No Schedule'},
				{id: 'pretalx', label: 'Pretalx'},
				{id: 'file', label: 'File Upload'},
				{id: 'url', label: 'External URL'},
			]
			if (this.$features.enabled('conftool')) {
				sourceOptions.push({id: 'conftool', label: 'Conftool'})
			}
			return sourceOptions
		},
		pretalxDomain () {
			if (!this.config.pretalx.domain) return ''
			if (this.config.pretalx.domain.endsWith('/')) return this.config.pretalx.domain
			return this.config.pretalx.domain + '/'
		},
		lastPush () {
			if (!this.config || !this.config.pretalx || !this.config.pretalx.pushed) return
			return moment(this.config.pretalx.pushed).format('dddd, MMMM Do YYYY, h:mm:ss a')
		},
		source: {
			get () {
				if (!this.config) return
				if (this.config.pretalx.domain !== undefined) return 'pretalx'
				if (this.config.pretalx.conftool) return 'conftool'
				if (this.showUpload) return 'file'
				if (this.config.pretalx.url !== undefined) {
					if (this.config.pretalx.url.includes('/pub/')) { // this *looks* like our storage
						return 'file'
					}
					return 'url'
				}
				return null
			},
			set (value) {
				this.showUpload = false
				switch (value) {
					case 'pretalx':
						this.config.pretalx = {
							domain: '',
							event: ''
						}
						break
					case 'file':
						this.showUpload = true
						this.config.pretalx = {
							url: ''
						}
						break
					case 'url':
						this.config.pretalx = {
							url: ''
						}
						break
					case 'conftool':
						this.config.pretalx = {
							conftool: true,
							url: this.config.pretalx.url
						}
						break
					case null:
						this.config.pretalx = {}
						break
				}
			}
		},
	},
	validations () {
		if (this.source === 'pretalx') {
			return {
				config: {
					pretalx: {
						domain: {
							required: required('domain is required'),
							url: url('domain must be a valid URL')
						},
						event: {
							required: required('event slug is required')
						}
					}
				}
			}
		}
		if (this.source === 'url' || this.source === 'file') {
			return {
				config: {
					pretalx: {
						url: {
							required: required('URL is required'),
							url: url('URL must be a valid URL')
						}
					}
				}
			}
		}
		return {}
	},
	async created () {
		// TODO: Force reloading if world.updated is received from the server
		try {
			this.config = await api.call('world.config.get')
		} catch (error) {
			this.error = error
			console.log(error)
		}
		this.$watch(() => this.config?.pretalx?.domain ? `${this.pretalxDomain}${this.config.pretalx.event}/p/venueless/check` : null, async (url) => {
			this.isPretalxPluginInstalled = false
			console.log(url)
			if (!url || !/^https?:\/\//.test(url)) return
			try {
				const response = await fetch(url)
				console.log(response)
				this.isPretalxPluginInstalled = response.ok
			} catch (error) {
				console.warn('failed pretalx check', error)
			}
		}, {
			immediate: true
		})
	},
	async mounted () {
		await this.$nextTick()
	},
	methods: {
		async startPretalxConnect () {
			// save pretalx config first
			if (!await this.save()) return
			this.connecting = true
			const {results: [token]} = await api.call('world.tokens.generate', {
				number: 1,
				days: 365,
				traits: ['schedule-update'],
				long: true
			})
			const apiUrl = config.api.base.startsWith('http') ? config.api.base : (window.location.origin + config.api.base)
			window.location = `${this.pretalxDomain}orga/event/${this.config.pretalx.event}/settings/p/venueless/?url=${apiUrl}&token=${token}&returnUrl=${window.location.href}`
		},
		async save () {
			this.$v.$touch()
			if (this.$v.$invalid) return false
			this.saving = true
			await api.call('world.config.patch', {pretalx: this.config.pretalx})
			// TODO error handling
			this.saving = false
			return true
		}
	}
}
</script>
<style lang="stylus">
.c-scheduleconfig
	flex: auto
	display: flex
	flex-direction: column
	.scroll-content
		flex: auto // take up more space for select dropdown to position correctly
	.pretalx-status
		font-weight: bold
		color: $clr-success
		&.plugin-not-installed, &.not-connected
			color: $clr-danger
	#btn-pretalx-connect
		margin: 16px 0
		align-self: flex-start
		themed-button-secondary()
</style>
