$('#id_get_gravatar').click(() => {
    if ($('#id_get_gravatar').is(':checked')) {
        $('.user-avatar-display').slideUp();
    } else {
        $('.user-avatar-display').slideDown();
    }
})
if ($('#id_get_gravatar').is(':checked')) {
    $('.user-avatar-display').hide()
}
