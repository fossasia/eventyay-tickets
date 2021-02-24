<template lang="pug">
.c-page-iframe-settings
	bunt-input(v-model="modules['page.iframe'].config.url", label="URL", name="url")
</template>
<script>
import mixin from './mixin'

export default {
	mixins: [mixin]
}
</script>
<style lang="stylus">
</style>
