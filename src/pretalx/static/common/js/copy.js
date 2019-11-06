$(function() {
  $('[data-toggle="tooltip"]').tooltip()
  $('[data-toggle="tooltip"], .copyable-text').click(function(e) {
    var $temp = $("<input>")
    $("body").append($temp)
    const currentTarget = $(e.currentTarget)
    $temp.val(currentTarget.data("destination")).select()
    document.execCommand("copy")
    $temp.remove()
    const previousTitle = currentTarget.title
    currentTarget.title = "Copied!"
    currentTarget.tooltip('show')
    window.setTimeout(400, () => {
      currentTarget.title = previousTitle;
      currentTarget.tooltip('hide')
    })
  })
})
