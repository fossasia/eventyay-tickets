var urls = new Bloodhound({
  datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
  queryTokenizer: Bloodhound.tokenizers.whitespace,
  limit: Infinity,
  remote: {
    url: document.getElementById('navigateUrl').getAttribute('remoteUrl'),
    wildcard: '%QUERY',
    transform: function (object) {
      var results = object.results
      console.log('yes')
      var suggestions = []
      for (i = 0; i < results.length; i++) {
        suggestions.push({value: results[i].url, name: results[i].name})
      }
      return suggestions
    },
  }
});

$('#navigate').typeahead(null, {
  name: 'name',
  display: 'name',
  source: urls,
  templates: {
    suggestion: function(data) {
      return '<div class="tt-suggestion tt-selectable">' + data.name + '</div>'
    }
  }
});
$("#navigate").bind("typeahead:select", function(ev, suggestion) {
  $("#navigate").text(suggestion.name);
  window.location = suggestion.value;
});
