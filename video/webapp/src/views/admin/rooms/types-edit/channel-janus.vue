<template lang="pug">
.c-channel-janus-settings
	sidebar-addons(v-bind="$props")
</template>
<script>
import mixin from './mixin'
import SidebarAddons from './SidebarAddons'

export default {
	components: { SidebarAddons },
	mixins: [mixin]
}
</script>
<style lang="stylus">
</style>
