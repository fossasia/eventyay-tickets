$(function () {
    var $root = $('.track-select-with-descriptions'),
        $select = $root.find('select'),
        $description = $root.find('.description'),
        $trigger = $root.find('button'),
        $modal = $root.find('.modal');

    $select.on('change.updateTrackDescription', function () {
        var $option = $select.find('option:selected'),
            descriptionText = $option.data('description');

        $description
            .text(descriptionText)
            .toggle(!!descriptionText);
    }).trigger('change.updateTrackDescription');

    $trigger.on('click.showTrackDescriptionModal', function () {
        $modal.modal();
    })
});
