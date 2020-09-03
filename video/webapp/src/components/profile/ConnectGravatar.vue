<template lang="pug">
form.c-connect-gravatar(@submit.prevent="connectGravatar")
	h1 {{ $t('profile/ConnectGravatar:headline') }}
	p {{ $t('profile/ConnectGravatar:text') }}
	bunt-input(name="gravatar", :label="$t('profile/ConnectGravatar:gravatar-email:label')", v-model="email")
	.actions
		bunt-button#btn-cancel(@click="$emit('close')") {{ $t('Prompt:cancel:label') }}
		bunt-button#btn-connect-gravatar(@click="connectGravatar", :loading="searchingGravatar", :error="gravatarError") {{ $t('profile/ConnectGravatar:gravatar-connect:label') }}
</template>
<script>
import api from 'lib/api'
import { getHash, getProfile, getAvatarUrl } from 'lib/gravatar'

export default {
	components: {},
	data () {
		return {
			email: '',
			searchingGravatar: false,
			connectedGravatar: false,
			gravatarError: null
		}
	},
	methods: {
		async connectGravatar () {
			// TODO load image and upload
			this.searchingGravatar = true
			this.gravatarError = null
			const hash = getHash(this.email)
			let avatarUrl = getAvatarUrl(hash, 128)
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
				const output = {}
				if (profile?.entry?.length > 0) {
					avatarUrl = getAvatarUrl(profile.entry[0].hash, 128)
					output.display_name = profile.entry[0].displayName
				}
				const imageBlob = await (await fetch(avatarUrl)).blob()
				const request = api.uploadFile(imageBlob, 'avatar.png')
				request.addEventListener('load', (event) => {
					const response = JSON.parse(request.responseText)
					output.avatar = {url: response.url}
					this.$emit('change', output)
				})
			} catch (e) {
				this.gravatarError = e
			}
			this.searchingGravatar = false
		},
	}
}
</script>
<style lang="stylus">
.c-connect-gravatar
	display: flex
	flex-direction: column
	align-items: center
	margin: 16px 0 32px 0
	.bunt-input
		width: 286px
	#btn-cancel
		themed-button-secondary()
	#btn-connect-gravatar
		themed-button-primary()
		margin: 0 0 0 4px
</style>
