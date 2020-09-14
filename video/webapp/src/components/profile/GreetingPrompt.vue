<template lang="pug">
prompt.c-profile-greeting-prompt(:allowCancel="false")
	.content
		connect-gravatar(v-if="showConnectGravatar", @change="setGravatar", @close="showConnectGravatar = false")
		.step-display-name(v-else-if="activeStep === 'displayName'")
			h1 {{ $t('profile/GreetingPrompt:step-display-name:heading') }}
			p {{ $t('profile/GreetingPrompt:step-display-name:text') }}
			//- link here not strictly good UX
			a.gravatar-connected-hint(v-if="profile.gravatar_hash", href="#", @click="connectedGravatar = false; showConnectGravatar = true") {{ $t('profile/GreetingPrompt:gravatar-change:label') }}
			p.gravatar-hint(v-else-if="!showConnectGravatar") {{ $t('profile/GreetingPrompt:gravatar-hint:text') }} #[a(href="#", @click="showConnectGravatar = true") gravatar].
			bunt-input.display-name(name="displayName", :label="$t('profile/GreetingPrompt:displayname:label')", v-model.trim="profile.display_name", :validation="$v.profile.display_name")
		.step-avatar(v-else-if="activeStep === 'avatar'")
			h1 {{ $t('profile/GreetingPrompt:step-avatar:heading') }}
			p {{ $t('profile/GreetingPrompt:step-avatar:text') }}
			change-avatar(ref="step", v-model="profile.avatar", @blockSave="blockSave = $event")
		.step-additional-fields(v-else-if="activeStep === 'additionalFields'")
			h1 {{ $t('profile/GreetingPrompt:step-fields:heading') }}
			p {{ $t('profile/GreetingPrompt:step-fields:text') }}
			change-additional-fields(v-model="profile.fields")
		.actions(v-if="!showConnectGravatar")
			bunt-button#btn-back(v-if="previousStep", @click="activeStep = previousStep") {{ $t('profile/GreetingPrompt:button-back:label') }}
			bunt-button#btn-continue(v-if="nextStep", :class="{invalid: $v.$invalid && $v.$dirty}", :disabled="blockSave || $v.$invalid && $v.$dirty", :loading="processingStep", :key="activeStep", @click="toNextStep") {{ $t('profile/GreetingPrompt:button-continue:label') }}
			bunt-button#btn-finish(v-else, :loading="saving", :disabled="blockSave", @click="update") {{ $t('profile/GreetingPrompt:button-finish:label') }}
</template>
<script>
import { mapState } from 'vuex'
import { required } from 'buntpapier/src/vuelidate/validators'
import api from 'lib/api'
import { getAvatarUrl } from 'lib/gravatar'
import Prompt from 'components/Prompt'
import ChangeAvatar from './ChangeAvatar'
import ChangeAdditionalFields from './ChangeAdditionalFields'
import ConnectGravatar from './ConnectGravatar'

export default {
	components: { Prompt, ChangeAvatar, ChangeAdditionalFields, ConnectGravatar },
	data () {
		return {
			activeStep: null,
			showConnectGravatar: false,
			profile: null,
			processingStep: false,
			blockSave: false,
			saving: false,
		}
	},
	validations () {
		if (this.activeStep !== 'displayName') return {}
		return {
			profile: {
				display_name: {
					required: required('Display name cannot be empty')
				}
			}
		}
	},
	computed: {
		...mapState(['user', 'world']),
		steps () {
			const steps = [
				'displayName',
				'avatar'
			]
			if (this.world?.profile_fields?.length) steps.push('additionalFields')
			return steps
		},
		previousStep () {
			return this.steps[this.steps.indexOf(this.activeStep) - 1]
		},
		nextStep () {
			return this.steps[this.steps.indexOf(this.activeStep) + 1]
		}
	},
	async created () {
		this.activeStep = this.steps[0]
		this.profile = Object.assign({
			greeted: true,
			display_name: '',
			avatar: {
				identicon: this.user.id
			},
			fields: {}
		}, this.user.profile)
		// TODO delete this after pycon au
		if (this.profile.gravatar_hash) {
			const avatarUrl = getAvatarUrl(this.profile.gravatar_hash, 128)
			const imageBlob = await (await fetch(avatarUrl)).blob()
			const request = api.uploadFile(imageBlob, 'avatar.png')
			request.addEventListener('load', (event) => {
				const response = JSON.parse(request.responseText)
				this.profile.avatar = {url: response.url}
			})
			delete this.profile.gravatar_hash
		}
	},
	mounted () {
		this.$nextTick(() => {
		})
	},
	methods: {
		async toNextStep () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			if (this.$refs.step?.update) {
				this.processingStep = true
				await this.$refs.step.update()
				this.processingStep = false
			}
			this.activeStep = this.nextStep
		},
		setGravatar (gravatar) {
			Object.assign(this.profile, gravatar)
			this.showConnectGravatar = false
		},
		async update () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.saving = true
			if (this.$refs.step?.update) {
				await this.$refs.step.update()
			}
			await this.$store.dispatch('updateUser', {profile: this.profile})
			// TODO error handling
			this.$emit('close')
		}
	}
}
</script>
<style lang="stylus">
.c-profile-greeting-prompt
	.content
		flex: auto
		display: flex
		flex-direction: column
		align-items: center
		position: relative
		padding: 16px
		h1
			margin: 8px 0
		p
			margin: 0 0 8px 0
			width: 360px
		.step-display-name, .step-avatar, .step-additional-fields
			display: flex
			flex-direction: column
			align-items: center
		.display-name
			max-width: 280px
			margin-top: 16px
		.actions
			margin-top: 32px
			align-self: stretch
			display: flex
			justify-content: flex-end
		#btn-back
			themed-button-secondary()
			margin-right: 8px
		#btn-continue, #btn-finish
			themed-button-primary()
			&.invalid
				button-style(color: $clr-danger)
		+below('m')
			p
				width: auto
</style>
