function question_page_toggle_view() {
  const variant = document.querySelector("#id_variant").value
  setVisibility(
    "#answer-options",
    variant === "choices" || variant === "multiple_choice"
  )
  setVisibility(
    "#alert-required-boolean",
    variant === "boolean" && document.querySelector("#id_question_required input[value=required]").checked
  )
  setVisibility("#limit-length", variant === "text" || variant === "string")
  setVisibility("#limit-number", variant === "number")
  setVisibility("#limit-date", variant === "date")
  setVisibility("#limit-datetime", variant === "datetime")
}

function question_page_toggle_target_view() {
  if (document.querySelector(".limit-submission")) {
    setVisibility(
      ".limit-submission",
      document.querySelector("#id_target").value === "submission"
    )
  }
  setVisibility(
    "#is-visible-to-reviewers",
    document.querySelector("#id_target").value !== "reviewer"
  )
}

function question_page_toggle_deadline() {
    const deadline = document.querySelector("#id_deadline");
    const deadlineWrapper = deadline.closest(".form-group");
    const deadlineRequired = document.querySelector("#id_question_required_2");

    if (deadlineRequired.checked) {
        setVisibility(deadlineWrapper, true)
        deadline.setAttribute("required", "required")
    }
    else {
        setVisibility(deadlineWrapper, false)
        deadline.removeAttribute("required")
    }
}

function setVisibility(element, value) {
  if (typeof element === "string") {
    document.querySelectorAll(element).forEach(e => setVisibility(e, value))
    return
  }
  if (element) {
    if (value) {
      element.classList.remove("d-none");
    } else {
      element.classList.add("d-none");
    }
  }
}
document.addEventListener("DOMContentLoaded", function() {
    document.querySelector("#id_variant").addEventListener("change", question_page_toggle_view)
    document.querySelectorAll("#id_question_required input").forEach(e => e.addEventListener("change", question_page_toggle_view))
    question_page_toggle_view()
    document.querySelector("#id_target").addEventListener("change", question_page_toggle_target_view)
    question_page_toggle_target_view()

    document.querySelectorAll("#id_question_required input").forEach(e => e.addEventListener("change", question_page_toggle_deadline))
    question_page_toggle_deadline()
})
