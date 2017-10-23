$('#id_get_gravatar').click(() => {
    if ($('#id_get_gravatar').is(':checked')) {
        $('.user-avatar-display').slideUp();
        $('.avatar-form img').attr('src', 'https://www.gravatar.com/avatar/' + $('.avatar-form img').attr('data-gravatar'));
    } else {
        $('.user-avatar-display').slideDown();
        $('.avatar-form img').attr('src', $('.avatar-form img').attr('data-avatar'));
    }
})
if ($('#id_get_gravatar').is(':checked')) {
    $('.user-avatar-display').hide()
}
