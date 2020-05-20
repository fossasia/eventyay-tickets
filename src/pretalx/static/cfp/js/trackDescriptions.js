$(function () {
    var $select = $('select[name=track]');

    // Add/Update/Remove Description based on selection
    $select.on('change.updateTrackDescription', function () {
        var $option = $select.find('option:selected');
        var description = $option.data('description');
        var $descriptionElement = $select.next('.description');

        if (!description) {
            $descriptionElement.remove();
            return;
        }

        if ($descriptionElement.length === 0) {
            $descriptionElement = $('<div class="description"></div>').insertAfter($select);
        }

        $descriptionElement.text(description);
    }).trigger('change.updateTrackDescription');
});
