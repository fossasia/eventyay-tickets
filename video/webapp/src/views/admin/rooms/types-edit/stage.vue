<template lang="pug">
.c-stage-settings
	h2 Stream
	bunt-select(name="stream-source", v-model="streamSource", :options="STREAM_SOURCE_OPTIONS", label="Stream source")
	template(v-if="modules['livestream.native']")
		bunt-input(name="url", v-model="modules['livestream.native'].config.hls_url", label="HLS URL")
		upload-url-input(name="streamOfflineImage", v-model="modules['livestream.native'].config.streamOfflineImage", label="Stream offline image")
		bunt-input(name="muxenvkey", v-if="$features.enabled('muxdata')", v-model="modules['livestream.native'].config.mux_env_key", label="MUX data environment key")
		bunt-input(name="subtitle_url", v-model="modules['livestream.native'].config.subtitle_url", label="URL for external subtitles")
		h4 Alternative Streams
		.alternative(v-for="(a, i) in (modules['livestream.native'].config.alternatives || [])" :key="i")
			bunt-input(name="label", v-model="a.label", label="Label")
			bunt-input(name="hls_url", v-model="a.hls_url", label="HLS URL")
			bunt-icon-button(@click="deleteAlternativeStream(i)") delete-outline
		bunt-button(@click="modules['livestream.native'].config.alternatives = [...(modules['livestream.native'].config.alternatives || []), {label: '', hls_url: ''}]") Add alternative stream
	bunt-input(v-else-if="modules['livestream.youtube']", name="ytid", v-model="modules['livestream.youtube'].config.ytid", label="YouTube Video ID", :validation="v$.modules['livestream.youtube'].config.ytid")
	// Language and URL input for YouTube stream
	.language-urls(v-if="modules['livestream.youtube']")
		h4 Languages and YouTube ID
		.language-url-entry(v-for="(entry, index) in modules['livestream.youtube'].config.languageUrls" :key="index")
			bunt-select(name="language", v-model="entry.language", :options="ISO_LANGUAGE_OPTIONS", label="Language")
			bunt-input(name="youtube_id" v-model="entry.youtube_id" label="YouTube Video ID")
			bunt-icon-button(@click="deleteLanguageUrl(index)") delete-outline
		bunt-button(@click="addLanguageUrl") + Add Language and Youtube ID
		// Switch button for no-cookies domain
		.bunt-switch-container
			bunt-switch(name="enablePrivacyEnhancedMode", v-model="enablePrivacyEnhancedMode", label="Enable No-Cookies")
			bunt-switch(name="loop", v-model="loop", label="Loop")
			bunt-switch(name="modestBranding", v-model="modestBranding", label=" Enable Modest Branding")
			bunt-switch(name="hideControls", v-model="hideControls", label="Enable Hide Controls")
			bunt-switch(name="noRelated", v-model="noRelated", label=" Enable No Related info")
			bunt-switch(name="disableKb", v-model="disableKb", label="Enable Keyboard Controls")
			bunt-switch(name="showInfo", v-model="showInfo", label="Enable No Show Info")
	bunt-input(v-else-if="modules['livestream.iframe']", name="iframe-player", v-model="modules['livestream.iframe'].config.url", label="Iframe player url", hint="iframe player should be autoplaying and support resizing to small sizes for background playing")
	sidebar-addons(v-bind="$props")
</template>
<script>
import { defineComponent } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import features from 'features'
import UploadUrlInput from 'components/UploadUrlInput'
import mixin from './mixin'
import SidebarAddons from './SidebarAddons'
import {youtubeid} from 'lib/validators'
import ISO6391 from 'iso-639-1'

const STREAM_SOURCE_OPTIONS = [
	{ id: 'hls', label: 'HLS', module: 'livestream.native' },
	{ id: 'youtube', label: 'YouTube', module: 'livestream.youtube' }
]

if (features.enabled('iframe-player')) {
	STREAM_SOURCE_OPTIONS.push({ id: 'iframe', label: 'Iframe player', module: 'livestream.iframe' })
}

export default defineComponent({
	components: { UploadUrlInput, SidebarAddons },
	mixins: [mixin],
	setup: () => ({ v$: useVuelidate() }),
	data() {
		return {
			STREAM_SOURCE_OPTIONS,
			ISO_LANGUAGE_OPTIONS: [],
			b_streamSource: null
		}
	},
	validations() {
		return {
			modules: {
				'livestream.youtube': {
					config: {
						ytid: {
							youtubeid: youtubeid('not a valid YouTube video ID (do not supply the full URL)')
						}
					}
				}
			}
		}
	},
	computed: {
		streamSource: {
			get() {
				return this.b_streamSource
			},
			set(value) {
				this.b_streamSource = value
				STREAM_SOURCE_OPTIONS.map(option => option.module).forEach(module => this.removeModule(module))
				this.addModule(STREAM_SOURCE_OPTIONS.find(option => option.id === value).module)
			}
		},
		enablePrivacyEnhancedMode: {
			get() {
				return !!this.modules['livestream.youtube']?.config.enablePrivacyEnhancedMode
			},
			set(value) {
				this.setYoutubeConfigProp('enablePrivacyEnhancedMode', value)
			}
		},
		loop: {
			get() {
				return !!this.modules['livestream.youtube']?.config.loop
			},
			set(value) {
				this.setYoutubeConfigProp('loop', value)
			}
		},
		modestBranding: {
			get() {
				return !!this.modules['livestream.youtube']?.config.modestBranding
			},
			set(value) {
				this.setYoutubeConfigProp('modestBranding', value)
			}
		},
		hideControls: {
			get() {
				return !!this.modules['livestream.youtube']?.config.hideControls
			},
			set(value) {
				this.setYoutubeConfigProp('hideControls', value)
			}
		},
		noRelated: {
			get() {
				return !!this.modules['livestream.youtube']?.config.noRelated
			},
			set(value) {
				this.setYoutubeConfigProp('noRelated', value)
			}
		},
		disableKb: {
			get() {
				return !!this.modules['livestream.youtube']?.config.disableKb
			},
			set(value) {
				this.setYoutubeConfigProp('disableKb', value)
			}
		},
		showInfo: {
			get() {
				return !!this.modules['livestream.youtube']?.config.showInfo
			},
			set(value) {
				this.setYoutubeConfigProp('showInfo', value)
			}
		}
	},
	created() {
		// Initialize language options
		this.ISO_LANGUAGE_OPTIONS = this.getLanguageOptions()
		
		if (this.modules['livestream.native']) {
			this.b_streamSource = 'hls'
		} else if (this.modules['livestream.youtube']) {
			this.b_streamSource = 'youtube'
			// languageUrls is set in the created lifecycle hook
			if (!this.modules['livestream.youtube'].config.languageUrls) {
				this.modules['livestream.youtube'].config.languageUrls = []
			}
		} else if (this.modules['livestream.iframe']) {
			this.b_streamSource = 'iframe'
		}
	},
	methods: {
		setYoutubeConfigProp(prop, value) {
			if (!this.modules['livestream.youtube']) return
			
			if (value) {
				this.modules['livestream.youtube'].config[prop] = true
			} else {
				delete this.modules['livestream.youtube'].config[prop]
			}
		},
		addLanguageUrl() {
			if (!this.modules['livestream.youtube']) return
			if (!this.modules['livestream.youtube'].config.languageUrls) {
				this.modules['livestream.youtube'].config.languageUrls = []
			}
			this.modules['livestream.youtube'].config.languageUrls.push({ language: '', youtube_id: '' })
		},
		deleteLanguageUrl(index) {
			if (!this.modules['livestream.youtube']?.config.languageUrls) return
			this.modules['livestream.youtube'].config.languageUrls.splice(index, 1)
		},
		deleteAlternativeStream(index) {
			if (!this.modules['livestream.native']?.config.alternatives) return
			this.modules['livestream.native'].config.alternatives.splice(index, 1)
			if (this.modules['livestream.native'].config.alternatives.length === 0) {
				this.modules['livestream.native'].config.alternatives = undefined
			}
		},
		getLanguageOptions() {
			return ISO6391.getAllCodes().map(code => ({
				id: ISO6391.getName(code),
				label: ISO6391.getName(code),
			}))
		}
	}
})
</script>
<style lang="stylus">
.bunt-switch-container
	margin-top: 16px
</style>
