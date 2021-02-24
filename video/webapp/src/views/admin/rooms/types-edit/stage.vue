<template lang="pug">
.c-stage-settings
	h3 Stream
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
	template(v-else-if="modules['livestream.youtube']")
		bunt-input(name="ytid", v-model="modules['livestream.youtube'].config.ytid", label="YouTube Video ID")
	h2 Sidebar features
	bunt-switch(name="enable-chat", v-model="hasChat", label="Enable Chat")
	bunt-switch(name="enable-qa", v-model="hasQuestions", label="Enable Q&A")
	template(v-if="hasQuestions")
		bunt-checkbox(v-model="modules['question'].config.active", label="Active", name="active")
		bunt-checkbox(v-model="modules['question'].config.requires_moderation", label="Questions require moderation", name="requires_moderation")
</template>
<script>
import UploadUrlInput from 'components/config/UploadUrlInput'
import mixin from './mixin'

const STREAM_SOURCE_OPTIONS = [
	{ id: 'hls', label: 'HLS' },
	{ id: 'youtube', label: 'YouTube' }
]

export default {
	components: { UploadUrlInput },
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
				const modMap = {
					hls: {insert: 'livestream.native', remove: 'livestream.youtube'},
					youtube: {insert: 'livestream.youtube', remove: 'livestream.native'}
				}
				const mod = modMap[value]
				this.addModule(mod.insert)
				this.removeModule(mod.remove)
			},
		},
		hasChat: {
			get () {
				return !!this.modules['chat.native']
			},
			set (value) {
				if (value) {
					this.addModule('chat.native', {volatile: true})
				} else {
					this.removeModule('chat.native')
				}
			}
		},
		hasQuestions: {
			get () {
				return !!this.modules.question
			},
			set (value) {
				if (value) {
					this.addModule('question', {
						active: true,
						requires_moderation: false
					})
				} else {
					this.removeModule('question')
				}
			}
		}
	},
	created () {
		if (this.modules['livestream.native']) {
			this.b_streamSource = 'hls'
		} else if (this.modules['livestream.youtube']) {
			this.b_streamSource = 'youtube'
		}
	}
}
</script>
<style lang="stylus">
</style>
