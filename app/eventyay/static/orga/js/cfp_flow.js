var api = {
    submit(data) {
        var fullHeaders = {}
        fullHeaders["Content-Type"] = "application/json"
        fullHeaders["X-CSRFToken"] = getCookie("eventyay_csrftoken")

        let options = {
            method: "POST",
            headers: fullHeaders,
            credentials: "include",
            body: JSON.stringify(data),
        }
        return window
            .fetch(window.location, options)
            .then((response) => {
                if (response.status === 204) {
                    return Promise.resolve()
                }
                return response.json().then((json) => {
                    if (!response.ok) {
                        return Promise.reject({ response, json })
                    }
                    return Promise.resolve(json)
                })
            })
            .catch((error) => {
                return Promise.reject(error)
            })
    },
}

let currentLanguage = "en"
let currentModal = Vue.reactive({
    type: null,
    data: null,
    show: false,
})
const markedOptions = {
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
}
document.onclick = (event) => {
    if (currentModal.data) {
        currentModal.data = null
    }
}
document.onkeydown = (event) => {
    if (!currentModal.data) return
    let isEscape = false
    if ("key" in event) {
        isEscape = event.key === "Escape" || event.key === "Esc"
    } else {
        isEscape = event.keyCode === 27
    }
    if (isEscape) {
        currentModal.data = null
    }
}

function areEqual() {
    var i, l, leftChain, rightChain

    function compare2Objects(x, y) {
        var p
        if (
            isNaN(x) &&
            isNaN(y) &&
            typeof x === "number" &&
            typeof y === "number"
        )
            return true
        if (x === y) return true
        if (!(x instanceof Object && y instanceof Object)) return false
        if (x.isPrototypeOf(y) || y.isPrototypeOf(x)) return false
        if (x.constructor !== y.constructor) return false
        if (x.prototype !== y.prototype) return false

        for (p in y) {
            if (y.hasOwnProperty(p) !== x.hasOwnProperty(p)) return false
            else if (typeof y[p] !== typeof x[p]) return false
        }
        for (p in x) {
            if (y.hasOwnProperty(p) !== x.hasOwnProperty(p)) return false
            else if (typeof y[p] !== typeof x[p]) return false

            switch (typeof x[p]) {
                case "object":
                case "function":
                    leftChain.push(x)
                    rightChain.push(y)

                    if (!compare2Objects(x[p], y[p])) {
                        return false
                    }

                    leftChain.pop()
                    rightChain.pop()
                    break

                default:
                    if (x[p] !== y[p]) {
                        return false
                    }
                    break
            }
        }
        return true
    }

    for (i = 1, l = arguments.length; i < l; i++) {
        leftChain = []
        rightChain = []
        if (!compare2Objects(arguments[0], arguments[i])) return false
    }
    return true
}

const FieldComponent = {
    render() {
    const h = Vue.h;
        const isQuestion = this.field.key.startsWith("question_");
        const questionUrl = window.location.pathname.replace(
            "flow/",
            this.field.key.replace("question_", "questions/")
        ) + "/edit";
        const displayHelpText = isQuestion ? 
            marked.parse(this.fixed_help_text, markedOptions) :
            marked.parse(
                this.field.help_text[currentLanguage] + " " + this.fixed_help_text,
                markedOptions
            );
        const labelContent = [];
        if (this.field.widget !== 'CheckboxInput') {
            if (this.isModal) {
                labelContent.push(
                    h('div', { class: 'i18n-form-group mb-2 title-input', onClick: (e) => e.stopPropagation() }, 
                        this.locales.map(locale => 
                            h('input', {
                                type: 'text',
                                class: 'form-control',
                                title: locale,
                                lang: locale,
                                value: this.field.label[locale],
                                onInput: (e) => { this.field.label[locale] = e.target.value; }
                            })
                        )
                    )
                );
                // Requirement editing logic
                if (this.editRequirement) {
                    if (!this.field.required && !this.field.hard_required) {
                        labelContent.push(
                            h('span', {
                                class: this.editable ? 'editable optional' : 'optional',
                                onClick: (e) => { e.stopPropagation(); this.field.required = true; }
                            }, 'Optional')
                        );
                    } else if (!this.field.hard_required) {
                        labelContent.push(
                            h('span', {
                                class: this.editable ? 'editable optional' : 'optional',
                                onClick: (e) => { e.stopPropagation(); this.field.required = false; }
                            }, [h('strong', 'Required')])
                        );
                    } else {
                        labelContent.push(h('span', { class: 'optional' }, [h('strong', 'Required')]));
                    }
                }
            } else {
                labelContent.push(
                    h('span', {
                        class: this.editable ? 'editable' : '',
                        onClick: (e) => {
                            e.stopPropagation();
                            if (this.editable) {
                                currentModal.data = this.field;
                                currentModal.type = 'field';
                                currentModal.show = true;
                            }
                        }
                    }, this.field.label[this.currentLanguage]),
                    h('br'),
                    !this.field.required ?
                        h('span', { class: 'optional' }, 'Optional') :
                        h('span', { class: 'optional' }, [h('strong', 'Required')])
                );
            }
        }
        const fieldInput = this.getFieldInput(h);
        // Help text content
        let helpTextContent;
        if (this.isModal) {
            helpTextContent = [
                h('div', { class: 'i18n-form-group', onClick: (e) => e.stopPropagation() },
                    this.locales.map(locale =>
                        h('input', {
                            type: 'text',
                            class: 'form-control',
                            title: locale,
                            lang: locale,
                            value: this.field.help_text[locale],
                            onInput: (e) => { this.field.help_text[locale] = e.target.value; }
                        })
                    )
                ),
                this.fixed_help_text ? h('div', { class: 'text-muted' }, this.fixed_help_text) : null
            ];
        } else {
            helpTextContent = h('div', {
                class: 'text-muted',
                innerHTML: this.display_help_text
            });
        }
        if (this.isModal && isQuestion) {
            return h('div', [
                h('h2', { class: 'mb-4' }, 'Change input field'),
                h('p', [
                    'This is a custom question you added to the CfP. You can change or remove this CfP question ',
                    h('a', { href: questionUrl }, 'here'),
                    '.'
                ])
            ]);
        }
        const mainContent = h('div', {
            class: ['form-group', 'row', this.field.field_source].concat(this.isModal ? '' : 'editable'),
            style: this.style,
            onClick: (e) => {
                e.stopPropagation();
                this.makeModal(e);
            }
        }, [
            h('label', { class: 'col-md-3 col-form-label pt-0' }, 
                this.field.widget === 'CheckboxInput' ? [
                    h('div', { class: 'form-check' }, [
                        h('input', { type: 'checkbox', class: 'form-check-input' }),
                        h('label', { class: 'form-check-label' }, this.field.label[this.currentLanguage])
                    ])
                ] : labelContent
            ),
            h('div', { class: 'col-md-9' }, [
                fieldInput,
                helpTextContent
            ])
        ]);
        return h('div', [
            this.isModal ? h('h2', { class: 'mb-4' }, 'Change input field') : null,
            mainContent
        ]);
    },
    data() {
        return {
            editRequirement: false,
            fixed_help_text: "",
        }
    },
    props: {
        field: Object,
        isModal: { type: Boolean, default: false },
        locales: Array,
    },
    computed: {
        style() {
            return ""
        },
        currentLanguage() {
            return currentLanguage
        },
        editable() {
            return !currentModal.data
        },
        display_help_text() {
            if (this.isQuestion)
                return marked.parse(this.fixed_help_text, markedOptions)
            return marked.parse(
                this.field.help_text[currentLanguage] +
                    " " +
                    this.fixed_help_text,
                markedOptions,
            )
        },
        isQuestion() {
            return this.field.key.startsWith("question_")
        },
        questionUrl() {
            return (
                window.location.pathname.replace(
                    "flow/",
                    this.field.key.replace("question_", "questions/"),
                ) + "/edit"
            )
        },
    },
    methods: {
        makeModal(event) {
            if (this.isModal) return
            if (!this.isModal && !this.editable) {
                currentModal.data = null
                currentModal.type = null
                currentModal.show = false
            } else {
                currentModal.data = this.field
                currentModal.type = "field"
                currentModal.show = true
            }
        },
        getFieldInput(h) {
            switch (this.field.widget) {
                case 'TextInput':
                case 'NumberInput':
                case 'EmailInput':
                    return h('input', { 
                        class: 'form-control', 
                        type: 'text', 
                        placeholder: this.field.title,
                        readonly: true,
                        disabled: true
                    });
                case 'Select':
                    return h('select', { 
                        class: 'form-control', 
                        type: 'text', 
                        placeholder: this.field.title,
                        readonly: true,
                        disabled: true
                    });
                case 'Textarea':
                case 'MarkdownWidget':
                    return h('textarea', { 
                        class: 'form-control', 
                        type: 'text', 
                        placeholder: this.field.title,
                        readonly: true,
                        disabled: true,
                        style: { height: '2.5em' }
                    });
                case 'CheckboxInput':
                    return null; // Handled in label
                case 'ClearableFileInput':
                    return h('div', { class: 'row bootstrap4-multi-input' }, [
                        h('div', { class: 'col-12' }, [
                            h('input', { type: 'file' })
                        ])
                    ]);
                default:
                    return null;
            }
        },
        getHelpTextContent(h, displayHelpText) {
            if (this.isModal) {
                return [
                    h('div', { class: 'i18n-form-group', onClick: (e) => e.stopPropagation() }, 
                        this.locales.map(locale => 
                            h('input', {
                                type: 'text',
                                class: 'form-control',
                                title: locale,
                                lang: locale,
                                modelValue: this.field.help_text[locale],
                                onInput: (e) => { this.field.help_text[locale] = e.target.value; }
                            })
                        )
                    ),
                    this.fixed_help_text ? h('div', { class: 'text-muted' }, this.fixed_help_text) : null
                ];
            } else {
                return h('div', { 
                    class: 'text-muted',
                    innerHTML: this.display_help_text
                });
            }
        }
    },
    created() {
        this.fixed_help_text = this.field.full_help_text.replace(
            this.field.help_text[currentLanguage],
            "",
        )
    },
}

const StepComponent = {
    render() {
    const h = Vue.h;
    const headerSteps = this.headerSteps;
    const stepPosition = this.stepPosition;
    const titleContent = this.editingTitle ? 
            h('span', { onClick: (e) => e.stopPropagation() }, [
                h('div', { class: 'col-md-9' }, [
                    h('div', { class: 'i18n-form-group', onClick: (e) => e.stopPropagation() }, 
                        this.locales.map(locale => 
                            h('input', {
                                type: 'text',
                                class: 'form-control',
                                title: locale,
                                lang: locale,
                                value: this.step.title[locale],
                                onInput: (e) => { this.step.title[locale] = e.target.value; }
                            })
                        )
                    )
                ])
            ]) :
            h('span', {
                class: this.editable ? 'editable' : '',
                onClick: (e) => {
                    if (this.editable) {
                        e.stopPropagation();
                        this.editingTitle = true;
                    }
                }
            }, this.step.title[this.currentLanguage] || '…');
        const textContent = this.editingText ?
            h('span', { onClick: (e) => e.stopPropagation() }, [
                h('div', { class: 'col-md-9' }, [
                    h('div', { class: 'i18n-form-group' }, 
                        this.locales.map(locale => 
                            h('textarea', {
                                class: 'form-control',
                                title: locale,
                                lang: locale,
                                value: this.step.text[locale],
                                onInput: (e) => { this.step.text[locale] = e.target.value; },
                                style: { height: '2.5em' }
                            })
                        )
                    )
                ])
            ]) :
            h('span', {
                class: this.editable ? 'editable' : '',
                onClick: (e) => {
                    if (this.editable) {
                        e.stopPropagation();
                        this.editingText = true;
                    }
                },
                innerHTML: this.marked(this.step.text[this.currentLanguage] || '…')
            });
        const fieldComponent = Vue.resolveComponent('field');
        const formContent = this.step.identifier !== 'user' ? 
            h('form', 
                this.step.fields.filter(field => field && field.widget !== 'HiddenInput').map(field => {
                    return h(fieldComponent, { 
                        field: field,
                        locales: this.locales,
                        key: field.key
                    });
                })
            ) :
            h('form', { id: 'auth-form' }, [
                h('div', { class: 'auth-form-block' }, [
                    h('h4', { class: 'text-center' }, 'I already have an account'),
                    h('div', { class: 'form-group' }, [h('input', { type: 'text', class: 'form-control', placeholder: 'Email address', readonly: true, disabled: true })]),
                    h('div', { class: 'form-group' }, [h('input', { type: 'password', class: 'form-control', placeholder: 'Password', readonly: true, disabled: true })]),
                    h('button', { type: 'submit', class: 'btn btn-lg btn-success btn-block', disabled: true }, 'Log in')
                ]),
                h('div', { class: 'auth-form-block' }, [
                    h('h4', { class: 'text-center' }, 'I need a new account'),
                    h('div', { class: 'form-group' }, [h('input', { type: 'text', class: 'form-control', placeholder: 'Name', readonly: true, disabled: true })]),
                    h('div', { class: 'form-group' }, [h('input', { type: 'text', class: 'form-control', placeholder: 'Email address', readonly: true, disabled: true })]),
                    h('div', { class: 'form-group' }, [h('input', { type: 'password', class: 'form-control', placeholder: 'Password', readonly: true, disabled: true })]),
                    h('div', { class: 'form-group' }, [h('input', { type: 'password', class: 'form-control', placeholder: 'Password (again)', readonly: true, disabled: true })]),
                    h('button', { type: 'submit', class: 'btn btn-lg btn-info btn-block', disabled: true }, 'Register'),
                    h('div', { class: 'overlay' }, 'This form cannot be modified – a page to login or register needs to be in place, but you can change the page title and description.')
                ])
            ]);
        const questionAlert = this.step.identifier === 'questions' ? 
            h('div', { class: 'alert alert-info' }, 'This step will only be shown if you have questions configured.') : 
            null;
        return h('div', { class: 'step', onClick: () => { this.editingTitle = false; this.editingText = false; } }, [
            h('div', { 
                class: ['step-header', 'header', this.eventConfiguration.header_pattern],
                style: this.headerStyle
            }, this.eventConfiguration.header_image ? 
                h('img', { src: this.eventConfiguration.header_image }) : 
                null
            ),
            h('div', { class: 'step-main-container' }, [
                h('div', { class: 'submission-steps stages' }, 
                    headerSteps.map(stp => 
                        h('span', { class: ['step', 'step-' + stp.phase] }, [
                            h('div', { class: 'step-icon' }, 
                                h('span', { class: ['fa', 'fa-' + stp.icon] })
                            ),
                            h('div', { class: 'step-label' }, stp.label)
                        ])
                    )
                ),
                h('h2', { class: 'edit-container' }, titleContent),
                h('div', { class: 'edit-container' }, textContent),
                formContent,
                questionAlert
            ])
        ]);
    },
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
        marked(value) {
            return marked.parse(value, markedOptions)
        },
    },
    computed: {
        currentLanguage() {
            return currentLanguage
        },
        headerStyle() {
            // logo_image, header_image, header_pattern
            return {
                "background-color": this.eventConfiguration.primary_color,
            }
        },
        editable() {
            return !currentModal.data
        },
        stepPosition() {
            return this.steps.findIndex((element) => {
                return element.identifier === this.step.identifier
            })
        },
        headerSteps() {
            let result = this.steps.map((element, index) => {
                let state = null
                if (index < this.stepPosition) {
                    state = "done"
                } else if (index === this.stepPosition) {
                    state = "current"
                } else {
                    state = "todo"
                }
                return {
                    icon: state === "done" ? "check" : element.icon,
                    label: element.header_label,
                    phase: state,
                }
            })
            result.push({
                icon: "check",
                label: "",
                phase: "todo",
            })
            return result
        },
    },
}

const app = Vue.createApp({
    render() {
        const h = Vue.h;
        const stepComponent = Vue.resolveComponent('step');
        const fieldComponent = Vue.resolveComponent('field');
        const modalContent = currentModal.data ? 
            h('div', { id: 'flow-modal' }, [
                h('form', [
                    h(fieldComponent, { 
                        field: currentModal.data,
                        isModal: true,
                        key: 'modal',
                        locales: this.locales
                    })
                ])
            ]) : null;
        const loadingContent = this.loading ?
            h('div', { id: 'loading' }, [
                h('i', { class: 'fa fa-spinner fa-pulse fa-4x fa-fw text-primary mb-4 mt-4' }),
                h('h3', { class: 'mt-2 mb-4' }, 'Loading talks, please wait.')
            ]) :
            h('div', { id: 'steps' }, 
                this.stepsConfiguration.map(step => {
                    return h(stepComponent, {
                        step: step,
                        eventConfiguration: this.eventConfiguration,
                        key: step.identifier,
                        steps: this.stepsConfiguration,
                        locales: this.locales
                    });
                })
            );
        const unassignedContent = h('div', { id: 'unassigned-group', class: 'd-none' }, [
            h('div', { class: 'step-header', ref: 'stepHeader' }),
            h('div', { id: 'unassigned-fields' }, [
                h('div', { class: 'input-group' }, [
                    h('div', { class: 'input-group-prepend input-group-text' }, 
                        h('i', { class: 'fa fa-search' })
                    ),
                    h('input', {
                        type: 'text',
                        class: 'form-control',
                        placeholder: 'Search...',
                        value: this.search,
                        onInput: (e) => { this.search = e.target.value; }
                    })
                ]),
                h('div', { id: 'unassigned-container', ref: 'unassigned' }, 
                    this.filteredFields.map(field => {
                        return h(fieldComponent, { field: field, key: field.id });
                    })
                )
            ])
        ]);
        const dirtyFlowContent = this.configurationChanged ?
            h('div', { id: 'dirty-flow', class: 'alert alert-warning' }, [
                h('span', 'Unsaved configuration changes!'),
                h('button', {
                    class: 'btn btn-success',
                    onClick: this.save,
                    disabled: this.saving
                }, this.saving ? 
                    h('span', [
                        h('i', { class: 'fa fa-spinner fa-pulse fa-fw text-success mb-2 mt-2' })
                    ]) : 
                    h('span', 'Save now')
                )
            ]) : null;
        return h('div', {
            class: currentModal.data ? 'defocused' : 'focused',
            style: { '--color': this.eventConfiguration.primary_color || '#2185d0' }
        }, [
            modalContent,
            h('div', { id: 'flow' }, loadingContent),
            unassignedContent,
            dirtyFlowContent
        ]);
    },
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
            locales: null,
        }
    },
    created() {
        this.eventConfiguration = JSON.parse(
            document.getElementById("eventConfiguration").textContent,
        )
        this.locales = this.eventConfiguration.locales
        if (!this.locales.includes("en")) currentLanguage = this.locales[0]
        let currentConfiguration = JSON.parse(
            document.getElementById("currentConfiguration").textContent,
        )
        this.eventSlug = currentConfiguration.event
        this.stepsConfiguration = currentConfiguration
        this.originalConfiguration = JSON.parse(
            JSON.stringify(this.stepsConfiguration),
        )
        this.loading = false
    },
    computed: {
        filteredFields() {
            if (!this.unassignedFields) return []
            return Object.values(this.unassignedFields).filter((field) => {
                return (
                    field.title
                        .toLowerCase()
                        .indexOf(this.search.toLowerCase()) > -1
                )
            })
        },
        configurationChanged() {
            return !areEqual(
                this.stepsConfiguration,
                this.originalConfiguration,
            )
        },
        currentModal() {
            return currentModal
        },
    },
    methods: {
        save() {
            this.saving = true
            api.submit(this.stepsConfiguration).then((response) => {
                this.originalConfiguration = JSON.parse(
                    JSON.stringify(this.stepsConfiguration),
                )
                this.saving = false
            })
        },
    },
})

app.component("field", FieldComponent)
app.component("step", StepComponent)
app.mount("#flow")
