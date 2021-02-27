<template lang="pug">
.c-page-landing-settings
	bunt-input-outline-container(label="Content")
		textarea(slot-scope="{focus, blur}", @focus="focus", @blur="blur", v-model="modules['page.landing'].config.content")
	upload-url-input(v-model="modules['page.landing'].config.header_image", label="Header image", name="headerimage")
	bunt-input(v-model="modules['page.landing'].config.header_background_color", label="Header background color", name="headerbackgroundcolor")
</template>
<script>
import mixin from './mixin'

export default {
	mixins: [mixin]
}
</script>
<style lang="stylus">
</style>
