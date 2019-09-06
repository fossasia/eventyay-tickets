document.addEventListener("DOMContentLoaded", function() {
  const avatarImage = document.querySelector(".avatar-form img")
  const avatarInput = document.querySelector(".user-avatar-display")
  if (!avatarImage || !avatarInput)
    return
  for (const selector of ["#id_get_gravatar", "#id_profile-get_gravatar"]) {
    let element = document.querySelector(selector)
    if (element) {
      element.addEventListener("click", () => {
        if (element.checked) {
          avatarImage.style.display = "block"
          avatarImage.src =
            "https://www.gravatar.com/avatar/" + avatarImage.dataset.gravatar
          avatarInput.style.display = "none"
        } else {
          avatarInput.style.display = "block"
          if (avatarImage.dataset.avatar) {
            avatarImage.style.display = "block"
            avatarImage.src = avatarImage.dataset.avatar
          } else {
            avatarImage.style.display = "none"
          }
        }
      })
    }
  }
  const gravatarInput = document.querySelector("#id_get_gravatar")
  if (gravatarInput && gravatarInput.checked) {
    avatarInput.style.display = "none"
    avatarImage.src =
      "https://www.gravatar.com/avatar/" + avatarImage.dataset.gravatar
  }
})
