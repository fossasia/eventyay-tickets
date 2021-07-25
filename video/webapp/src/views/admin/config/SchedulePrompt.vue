<template lang="pug">
prompt.c-schedule-prompt(@close="$emit('close')")
	.content
		bunt-tabs(:active-tab="activeTab")
			bunt-tab(id="pretalx", header="From pretalx")
				p If you use pretalx for your event, enter the domain of the pretalx server you use and the short form name of your event. We'll then pull in the schedule automatically and keep it updated. You must be using pretalx version 2 or later.
				bunt-input(name="domain", label="pretalx domain", v-model="domain", placeholder="e.g. https://pretalx.com", :validation="$v.domain")
				bunt-input(name="event", label="pretalx event slug", v-model="event", placeholder="e.g. democon")
				bunt-button.btn-load(:error-message="error", :loading="loading", @click="savePretalx") Load schedule
			bunt-tab(id="file", header="Upload file")
				p If you don't use pretalx, you can upload your schedule as a Microsoft Excel file (XLSX) with a specific setup.
				p
					a(href="/schedule_ex_en.xlsx", target="_blank") Download English sample file
					| {{ " / " }}
					a(href="/schedule_ex_de.xlsx", target="_blank") Download German sample file
				input(type="file", ref="fileInput")
				bunt-button.btn-load(:error-message="error", :loading="loading", @click="importFile") Load schedule
			bunt-tab(id="url", header="From URL")
				p If you want to automatically load the schedule from an external system, you can enter an URL here. Note that the URL must be a JSON file compliant with the pretalx schedule widget API version 2.
				bunt-input(name="url", label="JSON URL", v-model="url", placeholder="e.g. https://website.com/event.json", :validation="$v.url")
				bunt-button.btn-load(:error-message="error", :loading="loading", @click="saveURL") Load schedule
			bunt-tab(id="conftool", v-if="$features.enabled('conftool')", header="From Conftool")
				p If you want to automatically load the schedule from conftool, just click the button. Make sure your Conftool REST API details are configured.
				bunt-button.btn-load(:error-message="error", :loading="loading", @click="saveConftool") Load schedule
</template>
<script>
import Prompt from 'components/Prompt'
import { url } from 'vuelidate/lib/validators'
import config from 'config'
import api from 'lib/api'

export default {
	components: { Prompt },
	props: {
		currentConfig: Object
	},
	data () {
		return {
			domain: null,
			event: null,
			url: null,
			loading: false,
			error: null
		}
	},
	validations () {
		if (this.url) {
			return {
				url: {
					url
				}
			}
		} else {
			return {
				domain: {
					url
				}
			}
		}
	},
	computed: {
		activeTab () {
			if (this.currentConfig.url) {
				if (this.currentConfig.url.includes('/pub/')) { // this *looks* like our storage
					return 'file'
				}
				if (this.currentConfig.conftool) { // this *looks* like our conftool api
					return 'conftool'
				}
				return 'url'
			}
			return 'pretalx'
		}
	},
	mounted () {
		this.domain = this.currentConfig.domain
		this.event = this.currentConfig.event
		this.url = this.currentConfig.url
	},
	methods: {
		async importFile () {
			if (this.$refs.fileInput.files.length < 1) return
			this.loading = true
			this.error = null
			const file = this.$refs.fileInput.files[0]

			api.uploadFilePromise(file, file.name, config.api.scheduleImport).then(data => {
				this.loading = false
				if (data.error) {
					this.error = data.error
				} else {
					this.$emit('save', {url: data.url})
				}
				this.uploading = false
			}).catch(error => {
				this.loading = false
				this.error = error.toString()
				this.uploading = false
			})
		},
		savePretalx () {
			this.error = null
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.$emit('save', {domain: this.domain, event: this.event})
		},
		saveConftool () {
			this.error = null
			this.$emit('save', {conftool: true, url: this.currentConfig.url})
		},
		saveURL () {
			this.error = null
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.$emit('save', {url: this.url})
		},
	}
}
</script>
<style lang="stylus">
.c-schedule-prompt
	.prompt-wrapper
		width: 600px
	.btn-load
		themed-button-primary()
	.bunt-tabs
		tabs-style(active-color: var(--clr-primary), indicator-color: var(--clr-primary), background-color: transparent)
	.bunt-tab
		padding: 16px
	input[type=file]
		margin-bottom: 16px
</style>
