<template lang="pug">
.c-manage-poster
	.error(v-if="error") {{ $t('poster-manager/poster:poster-not-found:text') }}
	template(v-else-if="poster")
		.ui-page-header
			bunt-icon-button(@click="$router.push({name: 'posters'})") arrow_left
			h1 {{ create ? $t('poster-manager/poster:new-poster:title') : poster.title }}
			.actions
				//- bunt-button.btn-delete-poster(@click="showDeletePrompt = true") delete
		scrollbars(y)
			.ui-form-body
				bunt-select(name="parent_room", v-model="poster.parent_room_id", :label="$t('poster-manager/poster:input-parent-room:label')", :options="rooms", option-label="name")
				template(v-if="room")
					bunt-input(name="title", v-model="poster.title", :label="$t('poster-manager/poster:input-title:label')", :validation="$v.poster.title")
					rich-text-editor(v-model="poster.abstract", :label="$t('poster-manager/poster:input-abstract:label')")
					bunt-select(name="category", v-model="poster.category", :options="posterModule.config.categories", :label="$t('poster-manager/poster:input-category:label')")
					bunt-input(name="tags", v-model="tags", :label="$t('poster-manager/poster:input-tags:label')", hint="comma separated tag keys")
					upload-url-input(name="poster-pdf", v-model="poster.poster_url", :label="$t('poster-manager/poster:input-poster-pdf:label')", @input="generatePosterPreview")
					img(:src="poster.poster_preview")
					h2 {{ $t('poster-manager/poster:authors:headline') }}
					.authors
						.header
							.name {{ $t('poster-manager/poster:authors:header:name') }}
							.orgs
								.org(v-for="(org, index) of poster.authors.organizations") {{ index + 1 }}.
						.author(v-for="author of poster.authors.authors")
							bunt-input.name(name="name", v-model="author.name", :label="$t('poster-manager/poster:authors:input-name:label')")
							.orgs
								bunt-checkbox.org(v-for="(org, index) of poster.authors.organizations", name="org", :value="author.orgs.includes(index)", @input="toggleAuthorOrg(author, index)")
					bunt-button(@click="addAuthor") {{ $t('poster-manager/poster:btn-add-author') }}
					h3 {{ $t('poster-manager/poster:organizations:headline') }}
					.organizations
						.organization(v-for="(organization, index) of poster.authors.organizations")
							.index {{ index + 1 }}.
							bunt-input(name="organization", :value="organization", @input="$set(poster.authors.organizations, index, $event)")
					bunt-button(@click="poster.authors.organizations.push('')") {{ $t('poster-manager/poster:btn-add-organization') }}
					h2 {{ $t('poster-manager/poster:presenters:headline') }}
					.presenters
						.presenter(v-for="(presenter, index) in poster.presenters")
							.user
								avatar(:user="presenter", :size="36")
								span.display-name {{ presenter.profile.display_name }}
							td.actions
								bunt-icon-button(v-if="hasPermission('world:rooms.create.exhibition')", @click="removePresenter(presenter)") delete-outline
					bunt-button(@click="showPresenterPrompt = true") {{ $t('poster-manager/poster:btn-add-presenter') }}
					bunt-select(name="presentation-room", v-model="poster.presentation_room_id", :disabled="!hasPermission('world:rooms.create.poster')", :label="$t('poster-manager/poster:input-presentation-room:label')",  :options="presentationRoomOptions", option-label="name")
					bunt-input(name="schedule-session", v-model="poster.schedule_session", :label="$t('poster-manager/poster:input-schedule-session:label')")
					h2 {{ $t('poster-manager/poster:files:headline') }}
					.links(v-for="(link, index) in poster.links")
						.header
							.label {{ $t('poster-manager/poster:files:header:label') }}
							.url {{ $t('poster-manager/poster:files:header:url') }}
							//- .actions
						.link
							bunt-input.label(name="display-text", v-model="link.display_text")
							upload-url-input.url(name="url", v-model="link.url")
						//- .actions
						//- 	bunt-icon-button(@click="remove_link(index, link.category)") delete-outline
						//- 	bunt-icon-button(@click="up_link(index, link.category)") arrow-up-bold-outline
						//- 	bunt-icon-button(@click="down_link(index, link.category)") arrow-down-bold-outline
					bunt-button(@click="poster.links.push({display_text: '', url: ''})") {{ $t('poster-manager/poster:btn-add-file') }}
		.ui-form-actions
			bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") {{ create ? $t('poster-manager/poster:btn-create') : $t('poster-manager/poster:btn-save') }}
			//- .errors {{ validationErrors.join(', ') }}
	bunt-progress-circular(v-else, size="huge")
	transition(name="prompt")
		prompt.add-presenter-prompt(v-if="showPresenterPrompt", :scrollable="false", @close="showPresenterPrompt = false")
			.content
				h1 {{ $t('poster-manager/poster:add-presenter-prompt:headline') }}
				user-select(:button-label="$t('poster-manager/poster:add-presenter-prompt:btn-label')", @selected="addPresenters")
</template>
<script>
// TODO
// - better tag input
// - deletable authors and organizations
// - file attachments
// - delete

import * as pdfjs from 'pdfjs-dist/webpack'
import Quill from 'quill'
import { mapGetters } from 'vuex'
import { required} from 'buntpapier/src/vuelidate/validators'
import api from 'lib/api'
import router from 'router'
import Avatar from 'components/Avatar'
import Prompt from 'components/Prompt'
import UserSelect from 'components/UserSelect'
import UploadUrlInput from 'components/UploadUrlInput'
import RichTextEditor from 'components/RichTextEditor'
import ExhibitorPreview from 'views/exhibitors/item'

const Delta = Quill.import('delta')

export default {
	components: { Avatar, ExhibitorPreview, Prompt, UploadUrlInput, UserSelect, RichTextEditor },
	props: {
		create: Boolean,
		posterId: String
	},
	data () {
		return {
			error: null,
			poster: null,
			tags: '',
			showPresenterPrompt: false,
			saving: false
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		rooms () {
			return this.$store.state.rooms.filter(room => room.modules.some(m => m.type === 'poster.native'))
		},
		room () {
			if (!this.poster.parent_room_id) return
			return this.rooms.find(room => room.id === this.poster.parent_room_id)
		},
		posterModule () {
			return this.room?.modules.find(module => module.type === 'poster.native')
		},
		presentationRoomOptions () {
			return [{name: '', id: ''}, ...this.$store.state.rooms]
		},
	},
	validations () {
		return {
			poster: {
				title: {
					required: required('title is required')
				},
			}
		}
	},
	async created () {
		if (this.create) {
			this.poster = {
				id: '', // needs to be empty string for creation to work
				parent_room_id: null,
				title: '',
				abstract: new Delta(),
				authors: {
					authors: [],
					organizations: []
				},
				presenters: [],
				category: '',
				tags: [],
				poster_url: '',
				poster_preview: null,
				presentation_room_id: null,
				schedule_session: null,
				links: []
			}
		} else {
			this.poster = await api.call('poster.get', {poster: this.posterId})
			this.poster.abstract = new Delta(this.poster.abstract)
			this.tags = this.poster.tags.join(',')
		}
	},
	methods: {
		async generatePosterPreview () {
			const pdf = await pdfjs.getDocument(this.poster.poster_url).promise
			const page = await pdf.getPage(1)
			const unscaledViewport = page.getViewport({scale: 1})
			const viewport = page.getViewport({scale: 360 / unscaledViewport.height})
			const canvas = document.createElement('canvas')
			canvas.height = viewport.height
			canvas.width = viewport.width
			await page.render({
				canvasContext: canvas.getContext('2d'),
				viewport
			}).promise
			const blob = await new Promise(canvas.toBlob.bind(canvas))
			const {url} = await api.uploadFilePromise(blob, 'poster_preview.png')
			// TODO handle error (const {url, error} = …)
			this.poster.poster_preview = url
		},
		addAuthor () {
			this.poster.authors.authors.push({
				name: '',
				orgs: []
			})
		},
		toggleAuthorOrg (author, orgIndex) {
			const index = author.orgs.indexOf(orgIndex)
			if (index >= 0) {
				author.orgs.splice(index, 1)
			} else {
				author.orgs.push(orgIndex)
			}
		},
		addPresenters (presenters) {
			for (const presenter of presenters) {
				if (this.poster.presenters.some(existing => existing.id === presenter.id)) continue
				this.poster.presenters.push(presenter)
			}
			this.showPresenterPrompt = false
		},
		removePresenter (presenter) {
			const index = this.poster.presenters.indexOf(presenter)
			this.poster.presenters.splice(index, 1)
		},
		async save () {
			this.$v.$touch()
			if (this.$v.$invalid) return
			this.saving = true
			this.poster.tags = this.tags === '' ? [] : this.tags.split(',').map(tag => tag.trim())
			let poster = Object.assign({}, this.poster)
			poster.abstract = poster.abstract.ops
			poster.links.forEach((link, index) => link.sorting_priority = index)
			poster = await api.call('poster.patch', poster)
			if (this.create) await router.push({name: 'posters:poster', params: {posterId: poster.id}})
			this.saving = false
		}
	}
}
</script>
<style lang="stylus">
.c-manage-poster
	display: flex
	flex-direction: column
	flex: auto
	min-height: 0
	.scroll-content
		height: 100%
	.authors
		display: flex
		flex-direction: column
		.header, .author
			display: flex
			align-items: center
			.name
				flex: auto
				width: 50%
			.orgs
				flex: auto
				width: 50%
				display: flex
				margin: 0 4px
				.org
					flex: none
					width: 32px
					text-align: center
					margin: 0 4px
		.author
			// .bunt-input
			// 	input-style(size: compact)
			.orgs .org
				justify-content: center
				.bunt-checkbox-box
					margin: 0
	.organizations
		display: flex
		flex-direction: column
		.organization
			display: flex
			align-items: baseline
			.bunt-input
				flex: auto
				input-style(size: compact)
	.presenters
		display: flex
		flex-direction: column
		.presenter
			display: flex
			align-items: center
			height: 56px
			.user
				flex: auto
				display: flex
				align-items: center
				.c-avatar
					margin-right: 8px
			.bunt-icon-button
				icon-button-style(style: clear)
	.links
		display: flex
		flex-direction: column
		gap: 8px
		margin: 8px 0
		.header, .link
			display: flex
			gap: 8px
		.label, .url
			flex: 1
		.bunt-input
			input-style(size: compact)
			padding-top: 0
	.add-presenter-prompt
		.prompt-wrapper
			height: 80vh
			width: 600px
</style>
