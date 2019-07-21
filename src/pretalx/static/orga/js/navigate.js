var remoteUrls = []
var urls = null
fetch(document.getElementById("navigateUrl").getAttribute("data-remoteUrl"), {
  credentials: "same-origin",
}).then(response => {
  response.json().then(response => {
    remoteUrls = response.results.map(element => {
      return { value: element.url, name: element.name }
    })
    urls = new Bloodhound({
      datumTokenizer: Bloodhound.tokenizers.obj.whitespace("name"),
      queryTokenizer: Bloodhound.tokenizers.whitespace,
      local: remoteUrls,
    })
    $("#navigate").typeahead(
      { autoselect: true },
      {
        name: "name",
        display: "name",
        source: urls,
        templates: {
          suggestion: function(data) {
            return (
              '<div class="tt-suggestion tt-selectable">' + data.name + "</div>"
            )
          },
        },
      }
    )
    $("#navigate").bind("typeahead:select", function(ev, suggestion) {
      $("#navigate").text(suggestion.name)
      window.location = suggestion.value
    })
    $("#navigate").bind("keypress", function(ev) {
      if (ev.which == 13 /* ENTER */) {
        const typeahead = $(this).data().ttTypeahead
        const menu = typeahead.menu
        const sel = menu.getActiveSelectable() || menu.getTopSelectable()
        if (menu.isOpen()) {
          menu.trigger("selectableClicked", sel)
          ev.preventDefault()
        }
      }
    })
  })
})
