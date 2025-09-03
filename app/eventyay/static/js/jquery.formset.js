/**
* Django formset helper
*/
(function($) {
    "use strict";

    var pluginName = 'formset';

    /**
    * Wraps up a formset, allowing adding, and removing forms
    */
    var Formset = function(el, options) {
        var _this = this;

        //Defaults:
        this.opts = $.extend({}, Formset.defaults, options);

        this.$formset = $(el);
        this.$emptyForm = this.$formset.find(this.opts.emptyForm);
        this.$body = this.$formset.find(this.opts.body);
        this.$add = this.$formset.find(this.opts.add);

        this.formsetPrefix = $(el).data('formset-prefix');
        this.deleteConfirmText = $(el).data('formset-delete-confirm-text');

        // Bind to the `Add form` button
        this.addForm = $.proxy(this, 'addForm');
        this.$add.click(this.addForm);

        // Bind receiver to `formAdded` and `formDeleted` events
        this.$formset.on('formAdded formDeleted', this.opts.form, $.proxy(this, 'checkMaxForms'));

        // Set up the existing forms
        this.$forms().each(function(i, form) {
            var $form = $(form);
            _this.bindForm($(this), i);
        });

        // Fill "ORDER" fields with the current order
        this.prefillOrder();

        // Store a reference to this in the formset element
        this.$formset.data(pluginName, this);

        var extras = ['animateForms'];
        $.each(extras, function(i, extra) {
            if ((extra in _this.opts) && (_this.opts[extra])) {
                _this[extra]();
            }
        });
    };

    Formset.defaults = {
        form: '[data-formset-form]',
        emptyForm: 'script[type=form-template][data-formset-empty-form]',
        body: '[data-formset-body]',
        add: '[data-formset-add]',
        deleteButton: '[data-formset-delete-button]',
        moveUpButton: '[data-formset-move-up-button]',
        moveDownButton: '[data-formset-move-down-button]',
        hasMaxFormsClass: 'has-max-forms',
        animateForms: false,
        reorderMode: 'none',
        empty_prefix: '__prefix__'
    };

    Formset.prototype.addForm = function() {
        // Don't proceed if the number of maximum forms has been reached
        if (this.hasMaxForms()) {
            throw new Error("MAX_NUM_FORMS reached");
        }

        var newIndex = this.totalFormCount();
        this.$managementForm('TOTAL_FORMS').val(newIndex + 1);

        var newFormHtml = this.$emptyForm.html()
            .replace(new RegExp(this.opts.empty_prefix, 'g'), newIndex)
            .replace(new RegExp('<\\\\/script>', 'g'), '</script>');

        var $newFormFragment = $($.parseHTML(newFormHtml, this.$body.document, true));
        this.$body.append($newFormFragment);

        var $newForm = $newFormFragment.filter(this.opts.form);
        this.bindForm($newForm, newIndex);

        var prefix = this.formsetPrefix + '-' + newIndex;
        $newForm.find('[name=' + prefix + '-ORDER]').val(newIndex);
        $newForm.attr("data-formset-created-at-runtime", "true");
        
        return $newForm;
    };

    /**
    * Attach any events needed to a new form
    */
    Formset.prototype.bindForm = function($form, index) {
        var _this = this;

        var prefix = this.formsetPrefix + '-' + index;
        $form.data(pluginName + '__formPrefix', prefix);

        var $delete = $form.find('[name=' + prefix + '-DELETE]');
        var $order = $form.find('[name=' + prefix + '-ORDER]');

        var onChangeDelete = function() {
            if ($delete.is(':checked')) {
                $form.attr('data-formset-form-deleted', '');
                // Remove required property and pattern attribute to allow submit, back it up to data field
                $form.find(':required').data(pluginName + '-required-field', true).prop('required', false);
                $form.find('input[pattern]').each(function() {
                    var pattern = $(this).attr('pattern');
                    $(this).data(pluginName + '-field-pattern', pattern).removeAttr('pattern');
                });
                $form.trigger('formDeleted');
            } else {
                $form.removeAttr('data-formset-form-deleted');
                // Restore required property and pattern attributes from data field
                $form.find('*').filter(function() {
                    return $(this).data(pluginName + '-required-field') === true;
                }).prop('required', true);
                $form.find('input').each(function() {
                    var pattern = $(this).data(pluginName + '-field-pattern');
                    if (pattern) {
                        $(this).attr('pattern', pattern);
                    }
                });
                $form.trigger('formAdded');
            }
        }

        // Trigger `formAdded` / `formDeleted` events when delete checkbox value changes
        $delete.change(onChangeDelete);

        // This will trigger `formAdded` for newly created forms.
        // It will also trigger `formAdded` or `formDeleted` for all forms when
        // the Formset is first created.
        // setTimeout so the caller can register events before the events are
        // triggered, during initialisation.
        window.setTimeout(onChangeDelete);

        // Delete the form if the delete button is pressed
        var $deleteButton = $form.find(this.opts.deleteButton);
        var deleteConfirmText = this.deleteConfirmText;
        $deleteButton.bind('click', function() {
            if(!deleteConfirmText || confirm(deleteConfirmText)) {
                $delete.attr('checked', true).change();
            }
        });

        $order.change(function(event) {
            _this.reorderForms();
        });
        
        var $moveUpButton = $form.find(this.opts.moveUpButton);

        $moveUpButton.bind('click', function() {
            // Find the closest form with an ORDER value lower
            // than ours
            var current = $order.val();
            var $nextOrder = null;
            _this.$activeForms().each(function(i, form) {
                var $o = $(form).find('[name*=ORDER]');
                var order = parseInt($o.val());
                if(order < current && ($nextOrder == null || order > parseInt($nextOrder.val()))) {
                    $nextOrder = $o;
                }
            });

            // Swap the order values
            if($nextOrder != null) {
                // Swap the order values
                $order.val($nextOrder.val());
                $nextOrder.val(current);
            }

            _this.reorderForms();
        });

        var $moveDownButton = $form.find(this.opts.moveDownButton);

        $moveDownButton.bind('click', function() {
            // Find the closest form with an ORDER value higher
            // than ours
            var current = $order.val();
            var $nextOrder = null;
            _this.$activeForms().each(function(i, form) {
                var $o = $(form).find('[name*=ORDER]');
                var order = parseInt($o.val());
                if (order > current && ($nextOrder == null || order < parseInt($nextOrder.val()))) {
                    $nextOrder = $o;
                }
            });

            // Swap the order values
            if($nextOrder != null) {
                $order.val($nextOrder.val());
                $nextOrder.val(current);
            }

            _this.reorderForms();
        });
    };

    /**
     * Enumerate the forms and fill numbers into their ORDER input
     * fields, if present.
     */
    Formset.prototype.prefillOrder = function() {
        var _this = this;
       this.$forms().each(function(i, form) {
            var prefix = _this.formsetPrefix + '-' + i;
            var $order = $(form).find('[name=' + prefix + '-ORDER]');
            $order.val(i);
        });
    }

    /**
     * Enumerate the forms and fill numbers into their ORDER input
     * fields, if present.
     */
    Formset.prototype.reorderForms = function() {
        var _this = this;

        var compareForms = function(form_a, form_b) {
            /**
             * Compare two forms based on their ORDER input value.
             */
            var a = parseInt($(form_a).find('[name*=-ORDER]').val());
            var b = parseInt($(form_b).find('[name*=-ORDER]').val());
            return (a < b ? -1 : (a > b ? 1 : 0));
        }
        var $forms = this.$activeForms().sort(compareForms);

        if (this.opts.reorderMode == 'dom') {
            $forms.reverse().each(function(i, form) {
                // Move the forms to the top of $body, one by one
                _this.$body.prepend($(form));
            });
        } else if (this.opts.reorderMode == 'animate') {
            var accumulatedHeight = 0;

            // Setup the CSS
            if (this.$body.css("position") != "relative") {
                this.$body.css("height", this.$body.outerHeight(true) + "px");
                this.$body.css("position", "relative");
                this.$activeForms().each(function(i, form) {
                    $(form).css("position", "absolute");
                    $(form).css("top", accumulatedHeight + "px");
                    accumulatedHeight += $(form).outerHeight(true);
                });
                accumulatedHeight = 0;
            }

            // Do the animation
            $forms.each(function(i, form) {
                $(form).stop().animate({
                    "top": accumulatedHeight + "px"
                }, 1000);
                accumulatedHeight += $(form).outerHeight(true);
            });
            this.$body.css("height", accumulatedHeight + "px");
            
            // Reset the CSS
            window.setTimeout(function() {
                $forms.reverse().each(function(i, form) {
                    $(form).css("position", "static");
                    // Move the forms to the top of $body, one by one
                    _this.$body.prepend($(form));
                });
                _this.$body.css("position", "static");
                _this.$body.css("height", "auto");
            }, 1000);
        }
    }

    Formset.prototype.$forms = function() {
        return this.$body.find(this.opts.form);
    };

    Formset.prototype.$activeForms = function() {
        return this.$body.find(this.opts.form).not("[data-formset-form-deleted]");
    };

    Formset.prototype.$managementForm = function(name) {
        return this.$formset.find('[name=' + this.formsetPrefix + '-' + name + ']');
    };

    Formset.prototype.totalFormCount = function() {
        return this.$forms().length;
    };

    Formset.prototype.deletedFormCount = function() {
        return this.$forms().filter('[data-formset-form-deleted]').length;
    };

    Formset.prototype.activeFormCount = function() {
        return this.totalFormCount() - this.deletedFormCount();
    };

    Formset.prototype.hasMaxForms = function() {
        var maxForms = parseInt(this.$managementForm('MAX_NUM_FORMS').val(), 10) || 1000;
        return this.activeFormCount() >= maxForms;
    };

    Formset.prototype.checkMaxForms = function() {
        if (this.hasMaxForms()) {
            this.$formset.addClass(this.opts.hasMaxFormsClass);
            this.$add.attr('disabled', 'disabled');
        } else {
            this.$formset.removeClass(this.opts.hasMaxFormsClass);
            this.$add.removeAttr('disabled');
        }
        return false;
    };

    Formset.prototype.animateForms = function() {
        this.$formset.on('formAdded', this.opts.form, function() {
            var $form = $(this);
            if ($form.attr("data-formset-created-at-runtime") == "true") {
                $form.slideUp(0);
                $form.slideDown();
            }
            return false;
        }).on('formDeleted', this.opts.form, function() {
            var $form = $(this);
            $form.slideUp();
            return false;
        });
        this.$forms().filter('[data-formset-form-deleted]').slideUp(0);
    };

    Formset.getOrCreate = function(el, options) {
        var rev = $(el).data(pluginName);
        if (!rev) {
            rev = new Formset(el, options);
        }

        return rev;
    };

    $.fn[pluginName] = function() {
        var options, fn, args;
        // Create a new Formset for each element
        if (arguments.length === 0 || (arguments.length === 1 && $.type(arguments[0]) != 'string')) {
            options = arguments[0];
            return this.each(function() {
                return Formset.getOrCreate(this, options);
            });
        }

        // Call a function on each Formset in the selector
        fn = arguments[0];
        args = $.makeArray(arguments).slice(1);

        if (fn in Formset) {
            // Call the Formset class method if it exists
            args.unshift(this);
            return Formset[fn].apply(Formset, args);
        } else {
            throw new Error("Unknown function call " + fn + " for $.fn.formset");
        }
    };
    
    // Enable the array function 'reverse' for collections of jQuery
    // elements by including the shortest jQuery plugin ever.
    $.fn.reverse = [].reverse;

})(jQuery);
