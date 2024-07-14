<template lang="pug">
div.c-audio-translation
    h4 Audio Translation
    bunt-select(
    name="audio-translation",
    v-model="selectedLanguage",
    :options="languageOptions",
    label="Audio Translation",
    @input="sendLanguageChange"
)
</template>
<script>
export default {
  name: 'AudioTranslationDropdown',
	props: {
		languages: {
			type: Array,
			required: true
		}
	},
	data() {
		return {
      selectedLanguage: null, // Selected language for audio translation
      languageOptions: [] // Options for the dropdown
    };
  },
  watch: {
    languages: {
      immediate: true,
      handler(newLanguages) {
        this.languageOptions = newLanguages.map(entry => entry.language); // Directly assigning the list of languages
      }
    }
  },
  methods: {
    sendLanguageChange() {
      const selected = this.languages.find(item => item.language == this.selectedLanguage)
      const regex = /(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})/;
      const matchId = selected.url.match(regex);
      this.$emit('languageChanged', matchId ? matchId[1] : null);
    }
  }
};
</script>

<style scoped>
.c-audio-translation {
    margin-bottom: 3em;
}

.c-audio-translation h4 {
    margin-bottom: 0.5em;
}

.bunt-select {
    width: 100%;
}
</style>
