$(function () {
    var $select = $('select[name=track]');
    var hasDescriptions = $select.find('option[data-description]').length > 0;

    if (hasDescriptions) {
        // Create the input-group, insert it into the DOM where the select was and move the select
        // into the newly cresated input-group
        var $inputGroup = $('<div class="input-group track-select-with-descriptions">')
            .insertAfter($select)
            .append($select)

        // Create the Trigger-Button, register the Click-Handler and insert the Icon into it
        var $trigger = $('<button type="button" class="btn btn-primary">')
            .on('click', showDescriptions)
            .append('<i class="fa fa fa-info-circle"></i>')

        // Create the input-group-append, insert the Trigger into it and insert the input-group-append
        // after the select (to the end of the input-group)
        $('<div class="input-group-append">')
            .append($trigger)
            .insertAfter($select);

        // Register for selection-changes
        $select.on('change.updateTrackDescription', function () {
            // Find selected Option and its description
            var $option = $select.find('option:selected');
            var description = $option.data('description');

            // Find the Description-Element, if there is any
            var $descriptionElement = $inputGroup.next('.description');

            // If an item without description was selected, delete the Description-Element
            if (!description) {
                $descriptionElement.remove();
                return;
            }

            // If there is no Description-Element,
            // create one and insert it after the Input-Group
            if ($descriptionElement.length === 0) {
                $descriptionElement = $('<div class="description">')
                    .insertAfter($inputGroup);
            }

            // Set the Description-Text
            $descriptionElement.text(description);
        }).trigger('change.updateTrackDescription');
    }

    function showDescriptions() {
        alert('showDescriptions');
    }
});
