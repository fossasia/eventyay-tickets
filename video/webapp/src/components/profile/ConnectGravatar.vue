<template lang="pug">
form.c-connect-gravatar(@submit.prevent="connectGravatar")
	bunt-input(name="gravatar", :label="$t('ProfilePrompt:gravatar-email:label')", :hint="$t('ProfilePrompt:gravatar-email:hint')", v-model="email")
	bunt-button#btn-connect-gravatar(@click="connectGravatar", :loading="searchingGravatar", :error="gravatarError") {{ $t('ProfilePrompt:gravatar-connect:label') }}
</template>
<script>
import { getHash, getProfile, getAvatarUrl } from 'lib/gravatar'

export default {
	components: {},
	data () {
		return {
			email: '',
			searchingGravatar: false,
			connectedGravatar: false,
			gravatarError: null,
			gravatarAvatarUrl: null,
			gravatarHash: null,
		}
	},
	computed: {},
	created () {},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		async connectGravatar () {
			// TODO load image and upload
			this.searchingGravatar = true
			const hash = getHash(this.email)
			const avatarUrl = getAvatarUrl(hash, 128)
			try {
				// gravatar docs say profile only works on primary email, which I think is a lie, but let's check for an image separately anyways
				const avatarResponse = await fetch(avatarUrl)
				if (avatarResponse.status !== 200) {
					// no gravatar
					this.searchingGravatar = false
					this.gravatarError = true
					return
				}
				const profile = await getProfile(hash)
				if (profile?.entry?.length > 0) {
					this.gravatarHash = profile.entry[0].hash
					this.gravatarAvatarUrl = getAvatarUrl(this.gravatarHash, 128)
					this.displayName = profile.entry[0].displayName
				} else {
					this.gravatarHash = getHash(this.email)
					this.gravatarAvatarUrl = avatarUrl
				}
				this.connectedGravatar = true
			} catch (e) {
				this.gravatarError = e
			}
			this.searchingGravatar = false
		},
	}
}
</script>
<style lang="stylus">
</style>
