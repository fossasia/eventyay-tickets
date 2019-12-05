document.addEventListener("DOMContentLoaded", function() {
  "use strict"
  $('[data-toggle="tooltip"]').tooltip()
  if ($("#answer-options").length) {
    $("#id_variant").change(question_page_toggle_view)
    $("#id_required").change(question_page_toggle_view)
    question_page_toggle_view()
    $("#id_target").change(question_page_toggle_target_view)
    question_page_toggle_target_view()
  }

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

  $(".checkbox-multi-select input[type=checkbox]").change(ev => {
    const checkbox = ev.target
    var multiSelect = checkbox.parentNode
    while (
      multiSelect &&
      !multiSelect.classList.contains("checkbox-multi-select")
    ) {
      multiSelect = multiSelect.parentNode
    }
    if (multiSelect) {
      update_multi_select_caption(multiSelect)
    }
  })

  $(".keep-scroll-position").click(ev => {
    sessionStorage.setItem('scroll-position', window.scrollY);
  });

  restore_scroll_position();

  document.querySelectorAll(".checkbox-multi-select").forEach(element => {
    update_multi_select_caption(element)
  })
  $("#id_is_reviewer").change(ev => {
    update_review_override_votes()
  })
  update_review_override_votes()
})

function restore_scroll_position() {
    var oldScrollY = sessionStorage.getItem('scroll-position');

    if (oldScrollY) {
        window.scroll(window.scrollX, Math.max(oldScrollY, window.innerHeight));
        sessionStorage.removeItem('scroll-position');
    }
}

function update_review_override_votes() {
  const review = document.querySelector("#id_is_reviewer")
  if (review) {
    setVisibility("label[for=id_review_override_votes]", review.checked)
    setVisibility("#id_review_override_votes", review.checked)
    setVisibility("#id_review_override_votes + small", review.checked)
  }
}
function update_multi_select_caption(element) {
  var checkboxes = element.querySelectorAll(".checkbox")
  checkboxes = Array.from(checkboxes).filter(element => {
    return element.querySelector("input[type=checkbox]").checked
  })
  const text = checkboxes
    .map(box => box.querySelector("label").innerHTML)
    .join(", ")
  const title = element.querySelector(".multi-select-title")
  if (text) {
    title.innerHTML = text
  } else {
    title.innerHTML = title.dataset.title
  }
}

function question_page_toggle_view() {
  const variant = document.querySelector("#id_variant").value
  setVisibility(
    "#answer-options",
    variant === "choices" || variant === "multiple_choice"
  )
  setVisibility(
    "#alert-required-boolean",
    variant === "boolean" && document.querySelector("#id_required").checked
  )
  setVisibility("#limit-length", variant === "text" || variant === "string")
}

function question_page_toggle_target_view() {
  if ($("#limit-submission").length) {
    setVisibility(
      "#limit-submission",
      document.querySelector("#id_target").value === "submission"
    )
  }
  setVisibility(
    "#is-visible-to-reviewers",
    document.querySelector("#id_target").value !== "reviewer"
  )
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

function setVisibility(element, value) {
  if (typeof element === "string") {
    element = document.querySelector(element)
  }
  if (element) {
    element.style.display = value ? "" : "none"
  }
}
