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
		.alternative(v-for="(a, i) in (modules['livestream.native'].config.alternatives || [])")
			bunt-input(name="label", v-model="a.label", label="Label")
			bunt-input(name="hls_url", v-model="a.hls_url", label="HLS URL")
			bunt-icon-button(@click="modules['livestream.native'].config.alternatives.splice(i, 1)") delete-outline
		bunt-button(@click="$set(modules['livestream.native'].config, 'alternatives', modules['livestream.native'].config.alternatives || []); modules['livestream.native'].config.alternatives.push({label: '', hls_url: ''})") Add alternative stream
	bunt-input(v-else-if="modules['livestream.youtube']", name="ytid", v-model="modules['livestream.youtube'].config.ytid", label="YouTube Video ID")
	bunt-input(v-else-if="modules['livestream.iframe']", name="iframe-player", v-model="modules['livestream.iframe'].config.url", label="Iframe player url", hint="iframe player should be autoplaying and support resizing to small sizes for background playing")
	sidebar-addons(v-bind="$props")
</template>
<script>
import features from 'features'
import UploadUrlInput from 'components/UploadUrlInput'
import mixin from './mixin'
import SidebarAddons from './SidebarAddons'

const STREAM_SOURCE_OPTIONS = [
	{ id: 'hls', label: 'HLS', module: 'livestream.native' },
	{ id: 'youtube', label: 'YouTube', module: 'livestream.youtube' }
]

if (features.enabled('iframe-player')) {
	STREAM_SOURCE_OPTIONS.push({ id: 'iframe', label: 'Iframe player', module: 'livestream.iframe' })
}

export default {
	components: { UploadUrlInput, SidebarAddons },
	mixins: [mixin],
	data () {
		return {
			STREAM_SOURCE_OPTIONS,
			b_streamSource: null,
		}
	},
	computed: {
		streamSource: {
			get () {
				return this.b_streamSource
			},
			set (value) {
				this.b_streamSource = value
				STREAM_SOURCE_OPTIONS.map(option => option.module).forEach(module => this.removeModule(module))
				this.addModule(STREAM_SOURCE_OPTIONS.find(option => option.id === value).module)
			},
		}
	},
	created () {
		if (this.modules['livestream.native']) {
			this.b_streamSource = 'hls'
		} else if (this.modules['livestream.youtube']) {
			this.b_streamSource = 'youtube'
		} else if (this.modules['livestream.iframe']) {
			this.b_streamSource = 'iframe'
		}
	}
}
</script>
<style lang="stylus">
</style>
