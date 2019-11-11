var api = {
  submit(data) {
    var fullHeaders = {}
    fullHeaders["Content-Type"] = "application/json"
    fullHeaders["X-CSRFToken"] = getCookie("pretalx_csrftoken")

    let options = {
      method: "POST",
      headers: fullHeaders,
      credentials: "include",
      body: JSON.stringify(data),
    }
    return window
      .fetch(window.location, options)
      .then(response => {
        if (response.status === 204) {
          return Promise.resolve()
        }
        return response.json().then(json => {
          if (!response.ok) {
            return Promise.reject({ response, json })
          }
          return Promise.resolve(json)
        })
      })
      .catch(error => {
        return Promise.reject(error)
      })
  },
}

let currentLanguage = "en"
let currentModal = Vue.observable({
  type: null,
  data: null,
  show: false,
})
marked.setOptions({
  baseUrl: null,
  breaks: false,
  gfm: true,
  headerIds: true,
  headerPrefix: "",
  highlight: null,
  langPrefix: "language-",
  mangle: true,
  pedantic: false,
  sanitize: false,
  sanitizer: null,
  silent: false,
  smartLists: true,
  smartypants: false,
  tables: true,
  xhtml: false,
})
document.onclick = (event) => {
  if (currentModal.data) {
    currentModal.data = null;
  }
}
document.onkeypress = (event) => {
  if (!currentModal.data) return
  let isEscape = false;
  if ("key" in evt) {
    isEscape = (evt.key === "Escape" || evt.key === "Esc");
  } else {
    isEscape = (evt.keyCode === 27);
  }
  currentModal.data = null
}

function areEqual () {
  var i, l, leftChain, rightChain;

  function compare2Objects (x, y) {
    var p;
    if (isNaN(x) && isNaN(y) && typeof x === 'number' && typeof y === 'number') return true;
    if (x === y) return true;
    if (!(x instanceof Object && y instanceof Object)) return false;
    if (x.isPrototypeOf(y) || y.isPrototypeOf(x)) return false;
    if (x.constructor !== y.constructor) return false;
    if (x.prototype !== y.prototype) return false;

    for (p in y) {
        if (y.hasOwnProperty(p) !== x.hasOwnProperty(p)) return false;
        else if (typeof y[p] !== typeof x[p]) return false;
    }
    for (p in x) {
        if (y.hasOwnProperty(p) !== x.hasOwnProperty(p)) return false;
        else if (typeof y[p] !== typeof x[p]) return false;

        switch (typeof (x[p])) {
            case 'object':
            case 'function':

                leftChain.push(x);
                rightChain.push(y);

                if (!compare2Objects (x[p], y[p])) {
                    return false;
                }

                leftChain.pop();
                rightChain.pop();
                break;

            default:
                if (x[p] !== y[p]) {
                    return false;
                }
                break;
        }
    }
    return true;
  }

  for (i = 1, l = arguments.length; i < l; i++) {
      leftChain = [];
      rightChain = [];
      if (!compare2Objects(arguments[0], arguments[i])) return false;
  }
  return true;
}

Vue.component("field", {
  template: `
    <div :class="['form-group', 'row', field.field_source].concat(isModal ? '' : 'editable')" v-bind:style="style" @click.stop="makeModal">
      <label class="col-md-3 col-form-label">
        {{ field.title }}
        <br>
        <template v-if="isModal">
          <span v-if="!field.required & !field.hard_required" :class="[editable ? 'editable' : '', 'optional']" @click.stop="field.required=true">Optional</span>
          <span v-else-if="!field.hard_required" :class="[editable ? 'editable' : '', 'optional']" @click.stop="field.required=false"><strong>Required</strong></span>
          <span v-else class="optional"><strong>Required</strong></span>
        </template>
        <template v-else>
          <span v-if="!field.required" class="optional">Optional</span>
          <span v-else class="optional"><strong>Required</strong></span>
        </template>
      </label>
      <div class="col-md-9">
        <input class="form-control" type="text" :placeholder="field.title" readonly v-if="field.widget === 'TextInput'">
        <select class="form-control" type="text" :placeholder="field.title" readonly v-else-if="field.widget === 'Select'"></select>
        <textarea class="form-control" type="text" :placeholder="field.title" readonly v-else-if="field.widget === 'Textarea'"></textarea>

        <small class="form-text text-muted" v-if="help_text">{{ field.help_text[currentLanguage] }}</small>
      </div>
    </div>
  `, // TODO: file upload, checkboxes, help_text to html
  data() {
    return {}
  },
  props: {
    field: Object,
    isModal: { type: Boolean, default: false },
  },
  computed: {
    style () {
      return ""
    },
    currentLanguage () {
      return currentLanguage
    },
    editable () {
      return !currentModal.data
    },
    help_text () {
      return this.field.help_text || this.field.defaultHelpText
    }
  },
  methods: {
    makeModal(event) {
      if (this.isModal) return
      if (!this.isModal && !this.editable) {
        Vue.set(currentModal, 'data', null)
        currentModal.type = null
        currentModal.show = false
      } else {
        currentModal.data = this.field
        currentModal.type = "field"
        currentModal.show = true
      }
    }
  },
})

Vue.component("step", {
  template: `
    <div class="step" @click="editingTitle = false; editingText = false">
      <div :class="['step-header', 'header', eventConfiguration.header_pattern]" :style="headerStyle">
        <img :src="eventConfiguration.header_image" v-if="eventConfiguration.header_image">
      </div>
      <div class="step-main-container">
        <div class="submission-steps stages">
          <span :class="['step', 'step-' + stp.phase]" v-for="stp in headerSteps">
              <div class="step-icon">
                  <span :class="['fa', 'fa-' + stp.icon]"></span>
              </div>
              <div class="step-label">
                  {{ stp.label }}
              </div>
          </span>
        </div>
        <h2 class="edit-container">
          <span v-if="!editingTitle" :class="[editable ? 'editable' : '']" @click.stop="editTitle">{{ step.title[currentLanguage] }}</span>
          <span v-else>
          <div class="col-md-9"><div class="i18n-form-group" @click.stop="">
            <input type="text" class="form-control" :title="locale" :lang="locale" v-model="step.title[locale]" v-for="locale in locales">
          </div></div>
          </span>
        </h2>
        <div class="edit-container">
          <span v-if="!editingText" :class="[editable ? 'editable' : '']" @click.stop="editText" v-html="marked(step.text[currentLanguage])"></span>
          <span v-else @click.stop="">
            <div class="col-md-9"><div class="i18n-form-group">
              <textarea type="text" class="form-control" :title="locale" :lang="locale" v-model="step.text[locale]" v-for="locale in locales"></textarea>
            </div></div>
          </span>
        </div>
        <form v-if="step.identifier != 'user'">
        </form>
        <form v-else id="auth-form">
          <div class="auth-form-block">
            <h4 class="text-center">I already have an account</h4>
            <div class="form-group"><input type="text" class="form-control" placeholder="Email address" readonly></div>
            <div class="form-group"><input type="password" class="form-control" placeholder="Password" readonly></div>
            <button type="submit" class="btn btn-lg btn-success btn-block" disabled>Log in</button>
          </div>
          <div class="auth-form-block">
            <h4 class="text-center">I need a new account</h4>
            <div class="form-group"><input type="text" class="form-control" placeholder="Name" readonly></div>
            <div class="form-group"><input type="text" class="form-control" placeholder="Email address" readonly></div>
            <div class="form-group"><input type="password" class="form-control" placeholder="Password" readonly></div>
            <div class="form-group"><input type="password" class="form-control" placeholder="Password (again)" readonly></div>
            <button type="submit" class="btn btn-lg btn-info btn-block" disabled>Register</button>
            <div class="overlay">
              This form cannot be modified – a page to login or register needs to be in place, but you can change the page title and description.
            </div>
          </div>
        </form>
        <div v-if="step.identifier == 'questions'" class="alert alert-info">
          This step will only be shown if you have questions configured.
        </div>
      </div>
    </div>
  `,
  data() {
    return {
      editingTitle: false,
      editingText: false,
    }
  },
  props: {
    eventConfiguration: Object,
    step: Object,
    steps: Array,
    locales: Array,
  },
  methods: {
    editTitle() {
      if (this.editable) this.editingTitle = true
    },
    editText() {
      if (this.editable) this.editingText = true
    },
    marked (value) {
      return marked(value)
    },
  },
  computed: {
    currentLanguage () {
      return currentLanguage
    },
    headerStyle () {
      // logo_image, header_image, header_pattern
      return {
        "background-color": this.eventConfiguration.primary_color || "#1a4c3b",
      }
    },
    editable () {
      return !currentModal.data
    },
    stepPosition () {
      return this.steps.findIndex((element) => { return element.fields === this.fields })
    },
    headerSteps () {
      let result = this.steps.map((element, index) => {
        let state = null;
        if (index < this.stepPosition) { state = "done" }
        else if (index === this.stepPosition) { state = "current" }
        else { state = "todo" }
        return {
          "icon": state === "done" ? "check" : element.icon,
          "label": element.header_label,
          "phase": state,
        }
      })
      result.push({
        "icon": "done",
        "label": "Done!",
        "phase": "todo"
      })
    }
  },
})

var app = new Vue({
  el: "#workflow",
  template: `
    <div :class="currentModal.data ? 'defocused' : 'focused'">
      <div id="workflow-modal" v-if="currentModal.data">
        <form>
          <field :field="currentModal.data" :isModal="true" key="modal"></field>
        </form>
      </div>
      <div id="workflow">
        <div id="loading" v-if="loading">
            <i class="fa fa-spinner fa-pulse fa-4x fa-fw text-primary mb-4 mt-4"></i>
            <h3 class="mt-2 mb-4">Loading talks, please wait.</h3>
        </div>
        <div id="steps" v-else>
          <step v-for="step in stepsConfiguration.steps" :step="step" :eventConfiguration="eventConfiguration" :key="step.identifier" :steps="stepsConfiguration.steps" :locales="locales">
          </step>
        </div>
      </div>
      <div id="unassigned-group" class="d-none">
        <div class="step-header" ref="stepHeader"></div>
        <div id='unassigned-fields'>
          <div class="input-group">
            <div class="input-group-prepend input-group-text"><i class="fa fa-search"></i></div>
            <input type="text" class="form-control" placeholder="Search..." v-model="search">
          </div>
          <div id="unassigned-container" ref="unassigned">
              <field v-for="field in filteredFields" :field="field" :key="field.id"></field>
          </div>
        </div>
      </div>
      <div id="dirty-workflow" class="alert alert-warning" v-if="configurationChanged">
        <span>
          Unsaved configuration changes!
        </span>
        <button class="btn btn-success" @click="save" :disabled="saving">
          <span v-if="saving">
            <i class="fa fa-spinner fa-pulse fa-fw text-success mb-2 mt-2"></i>
          </span>
          <span v-else>
            Save now
          </span>
        </button>
      </div>
    </div>
  `,
  data() {
    return {
      steps: null,
      fieldLookup: null,
      unassignedFields: null,
      search: "",
      loading: true,
      saving: false,
      eventSlug: "",
      eventConfiguration: null,
      stepsConfiguration: null,
      originalConfiguration: null,
      locales: null
    }
  },
  created() {
    this.eventConfiguration = JSON.parse(document.getElementById('eventConfiguration').textContent);
    this.locales = this.eventConfiguration.locales;
    if (!this.locales.includes("en")) currentLanguage = this.locales[0];
    // let allFields = JSON.parse(document.getElementById('allFields').textContent);
    // this.fieldLookup = allFields.reduce((accumulator, currentValue) => {
    //   currentValue.key = currentValue.field_type + '_' + currentValue.field_source
    //   accumulator[currentValue.key] = currentValue
    //   return accumulator
    // }, {})
    // this.unassignedFields = JSON.parse(JSON.stringify(this.fieldLookup))
    let currentConfiguration = JSON.parse(document.getElementById('currentConfiguration').textContent);
    this.eventSlug = currentConfiguration.event
    this.stepsConfiguration = currentConfiguration
    this.stepsConfiguration.steps.forEach((step) => {
      if (!step.fields) {
        return
      }
      step.fields.forEach((field) => {
        const defaultField = this.fieldLookup[field.field_type + '_' + field.field_source]
        field.key = defaultField.key
        field.hardRequired = (defaultField.hardRequired || false)
        field.defaultHelpText = defaultField.help_text
        field.title = defaultField.title
        field.widget = defaultField.widget
        delete this.unassignedFields[field.key]
      })
    })
    this.originalConfiguration = JSON.parse(JSON.stringify(this.stepsConfiguration))
    this.loading = false
  },
  computed: {
    filteredFields() {
      if (!this.unassignedFields) return []
      return Object.values(this.unassignedFields).filter(field => {
        return field.title.toLowerCase().indexOf(this.search.toLowerCase()) > -1
      })
    },
    configurationChanged() {
      return !areEqual(this.stepsConfiguration, this.originalConfiguration)
    },
    currentModal () {
      return currentModal
    },
  },
  methods: {
    save() {
      this.saving = true
      api.submit(this.stepsConfiguration).then((response) => {
        this.originalConfiguration = JSON.parse(JSON.stringify(this.stepsConfiguration))
        this.saving = false
      })
    },
  },
})
