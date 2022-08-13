if (document.querySelector("#id_speaker")) {
  var speakers = new Bloodhound({
    datumTokenizer: Bloodhound.tokenizers.obj.whitespace("value"),
    queryTokenizer: Bloodhound.tokenizers.whitespace,
    limit: Infinity,
    remote: {
      url: document.getElementById("vars").getAttribute("remoteUrl"),
      wildcard: "%QUERY",
      transform: function(object) {
        var results = object.results
        var suggestions = []
        var i = 0
        for (i = 0; i < results.length; i++) {
          suggestions.push({ value: results[i].email, name: results[i].name })
        }
        return suggestions
      },
    },
  })

  let selector = ""
  if (document.querySelector("#id_speaker")) {
    selector = "#id_speaker"
  } else if (document.querySelector("#id_email")) {
    selector = "#id_email"
  }

  $(selector).typeahead(null, {
    name: "email",
    display: "value",
    source: speakers,
    templates: {
      suggestion: function(data) {
        return (
          '<div class="tt-suggestion tt-selectable">' +
          data.value +
          " (" +
          data.name +
          ")" +
          "</div>"
        )
      },
    },
  })
  $(selector).bind("typeahead:select", function(ev, suggestion) {
    $(selector).text(suggestion.value)
    if (selector == "#id_speaker") {
      document.querySelector("#id_speaker_name").value = suggestion.name
    }
  })
}
