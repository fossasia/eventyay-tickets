$(function() {
  $('[data-toggle="tooltip"]').tooltip()
  $('[data-toggle="tooltip"], .copyable-text').click(function(e) {
    var $temp = $("<input>")
    $("body").append($temp)
    const currentTarget = $(e.currentTarget)
    $temp.val(currentTarget.data("destination")).select()
    document.execCommand("copy")
    $temp.remove()
    const previousTitle = e.currentTarget.dataset["originalTitle"]
    e.currentTarget.title = "Copied!"
    e.currentTarget.dataset["originalTitle"] = "Copied!"
    currentTarget.tooltip('show')
    window.setTimeout(() => {
      e.currentTarget.title = previousTitle
      e.currentTarget.dataset["originalTitle"] = previousTitle
      currentTarget.tooltip('hide')
    }, 400)
  })
})
