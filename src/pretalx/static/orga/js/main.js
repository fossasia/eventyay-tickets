document.addEventListener("DOMContentLoaded", function() {
  "use strict"
  $('[data-toggle="tooltip"]').tooltip()
  function hideOptions (state) {
    if (!state.id || !state.element) return state.text
    if (state.element && state.element.classList.contains("hidden")) return
    return state.text
  }
  document.querySelectorAll(".select2").forEach(select => {
    $(select).select2({
      placeholder: select.title,
      templateResult: hideOptions,
      allowClear: !select.required && !select.multiple,
    })
  })

  $("input.submission_featured").change(function() {
    var id = this.dataset.id

    var $status = $(this)
      .parent()
      .siblings("i")
    var $working = $status.filter(".working")
    var $done = $status.filter(".done")
    var $fail = $status.filter(".fail")

    $working.removeClass("d-none")

    var url = window.location.pathname + id + "/toggle_featured"
    let options = {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("pretalx_csrftoken"),
      },
      credentials: "include",
    }

    function reset() {
      $status.addClass("d-none")
      setTimeout(function() {
        $status.addClass("d-none")
      }, 3000)
    }

    function fail() {
      this.checked = !this.checked
      $fail.removeClass("d-none")
    }

    window
      .fetch(url, options)
      .then(response => {
        reset()

        if (response.status === 200) {
          $done.removeClass("d-none")
        } else {
          fail()
        }
      })
      .catch(error => {
        reset()
        fail()
      })
  })


  $(".keep-scroll-position").click(ev => {
    sessionStorage.setItem('scroll-position', window.scrollY);
  });

  restore_scroll_position();

})

function restore_scroll_position() {
    var oldScrollY = sessionStorage.getItem('scroll-position');

    if (oldScrollY) {
        window.scroll(window.scrollX, Math.max(oldScrollY, window.innerHeight));
        sessionStorage.removeItem('scroll-position');
    }
}

function simplifyText(text) {
  const start = text.indexOf("(")
  if (start == -1) return text
  return text.substr(0, start).trim()
}

function update_multi_select_caption(element) {
  var checkboxes = element.querySelectorAll(".form-check")

  checkboxes = Array.from(checkboxes).filter(element => {
    return element.querySelector("input[type=checkbox]").checked
  })
  const text = checkboxes
    .map(box => simplifyText(box.querySelector("label").innerHTML))
    .join(", ")
  const title = element.querySelector(".multi-select-title")
  if (text) {
    title.innerHTML = text
  } else {
    title.innerHTML = title.dataset.title
  }
}

function getCookie(name) {
  let cookieValue = null
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";")
    for (var i = 0; i < cookies.length; i++) {
      let cookie = jQuery.trim(cookies[i])
      // Does this cookie string begin with the name we want?
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}
