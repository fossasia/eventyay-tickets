['#id_get_gravatar', '#id_profile-get_gravatar'].forEach((selector) => {
    var $avatarImg = $('.avatar-form img');
    var $avatarInput = $('.user-avatar-display');
    $(selector).click(() => {
        if ($(selector).is(':checked')) {
            $avatarInput.slideUp();
            $avatarImg.css('display', 'block');
            $avatarImg.attr('src', 'https://www.gravatar.com/avatar/' + $avatarImg.attr('data-gravatar'));
        } else {
            $avatarInput.slideDown();
            var local_avatar = $avatarImg.attr('data-avatar');
            if (local_avatar) {
                $avatarImg.css('display', 'block');
                $avatarImg.attr('src', $avatarImg.attr('data-avatar'));
            } else {
                $avatarImg.css('display', 'none');
            }
        }
    })
});
if ($('#id_get_gravatar').is(':checked')) {
    $('.user-avatar-display').hide()
}
