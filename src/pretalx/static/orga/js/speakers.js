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

$("#id_speaker").typeahead(null, {
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
$("#id_speaker").bind("typeahead:select", function(ev, suggestion) {
  $("#id_speaker").text(suggestion.value)
  document.querySelector("#id_speaker_name").value = suggestion.name
})
