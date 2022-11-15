<template lang="pug">
prompt.c-profile-greeting-prompt(:allowCancel="false")
	.content
		connect-gravatar(v-if="showConnectGravatar", @change="setGravatar", @close="showConnectGravatar = false")
		.step-connect-social(v-else-if="activeStep === 'connectSocial'")
			h1 {{ $t('profile/GreetingPrompt:step-social:heading') }}
			p {{ $t('profile/GreetingPrompt:step-social:text') }}
			bunt-button.social-connection.social-twitter(v-if="world.social_logins.includes('twitter')", @click="connectSocial('twitter')")
				.mdi.mdi-twitter
				.label twitter
			bunt-button.social-connection.social-linkedin(v-if="world.social_logins.includes('linkedin')", @click="connectSocial('linkedin')")
				.mdi.mdi-linkedin
				.label linkedin
			bunt-button.social-connection.social-gravatar(v-if="world.social_logins.includes('gravatar')",@click="showConnectGravatar = true")
				svg(viewBox="0 0 27 27")
					path(d="M10.8 2.699v9.45a2.699 2.699 0 005.398 0V5.862a8.101 8.101 0 11-8.423 1.913 2.702 2.702 0 00-3.821-3.821A13.5 13.5 0 1013.499 0 2.699 2.699 0 0010.8 2.699z")
				.label gravatar
			p.joiner or
			bunt-button.manual(@click="activeStep = 'displayName'") {{ $t('profile/GreetingPrompt:step-social:button-fill-manually:label') }}
		.step-display-name(v-else-if="activeStep === 'displayName'")
			template(v-if="steps.includes('connectSocial')")
				h1 {{ $t('profile/GreetingPrompt:step-display-name:heading') }}
				p {{ $t('profile/GreetingPrompt:step-display-name:text') }}
			template(v-else)
				h1 {{ $t('profile/GreetingPrompt:step-display-name~as-first-step:heading') }}
				p {{ $t('profile/GreetingPrompt:step-display-name~as-first-step:text') }}
			bunt-input.display-name(name="displayName", :label="$t('profile/GreetingPrompt:displayname:label')", v-model.trim="profile.display_name", :validation="$v.profile.display_name")
		.step-avatar(v-else-if="activeStep === 'avatar'")
			h1 {{ $t('profile/GreetingPrompt:step-avatar:heading') }}
			p {{ $t('profile/GreetingPrompt:step-avatar:text') }}
			change-avatar(ref="step", v-model="profile.avatar", @blockSave="blockSave = $event")
		.step-additional-fields(v-else-if="activeStep === 'additionalFields'")
			h1 {{ $t('profile/GreetingPrompt:step-fields:heading') }}
			p {{ $t('profile/GreetingPrompt:step-fields:text') }}
			change-additional-fields(v-model="profile.fields")
		.actions(v-if="activeStep !== 'connectSocial' && !showConnectGravatar")
			bunt-button#btn-back(v-if="previousStep", @click="activeStep = previousStep") {{ $t('profile/GreetingPrompt:button-back:label') }}
			bunt-button#btn-continue(v-if="nextStep", :class="{invalid: $v.$invalid && $v.$dirty}", :disabled="blockSave || $v.$invalid && $v.$dirty", :loading="processingStep", :key="activeStep", @click="toNextStep") {{ $t('profile/GreetingPrompt:button-continue:label') }}
			bunt-button#btn-finish(v-else, :loading="saving", :disabled="blockSave", @click="update") {{ $t('profile/GreetingPrompt:button-finish:label') }}
</template>
<script>
import { mapState } from 'vuex'
import { required } from 'buntpapier/src/vuelidate/validators'
import api from 'lib/api'
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
			if (this.world?.social_logins?.length) steps.unshift('connectSocial')
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
		// assume that when avatar url is set the social connection happened and skip first step
		if (this.activeStep === 'connectSocial' && this.profile.avatar.url) this.activeStep = this.nextStep
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
		async connectSocial (network) {
			const { url } = await api.call('user.social.connect', {
				network,
				return_url: window.location.href
			})
			window.location = url
		},
		setGravatar (gravatar) {
			Object.assign(this.profile, gravatar)
			this.showConnectGravatar = false
			this.activeStep = this.nextStep
		},
		async update () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.saving = true
			if (this.$refs.step?.update) {
				await this.$refs.step.update()
			}
			this.profile.greeted = true // override even if explicitly set to false by server
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
			text-align: center
		p
			margin: 0 0 8px 0
			width: 360px
			white-space: pre-wrap
		.step-connect-social, .step-display-name, .step-avatar, .step-additional-fields
			display: flex
			flex-direction: column
			align-items: center
		.step-connect-social
			margin-bottom: 16px
			.social-connection
				// margin-bottom: 8px
				.bunt-button-text
					display: flex
					align-items: center
					.mdi
						margin-right: 8px
						font-size: 24px
					.label
						width: 72px
			.social-twitter
				button-style(style: clear, color: #1DA1F2)
			.social-linkedin
				button-style(style: clear, color: #0A66C2)
			.social-gravatar
				button-style(style: clear, color: #4678eb)
				svg
					width: 20px
					margin: 0 12px 0 4px
					path
						fill: #4678eb
			.joiner
				text-align: center
			.manual
				themed-button-secondary()
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
