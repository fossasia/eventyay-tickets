var speakers = new Bloodhound({
  datumTokenizer: Bloodhound.tokenizers.obj.whitespace('value'),
  queryTokenizer: Bloodhound.tokenizers.whitespace,
  limit: Infinity,
  remote: {
    url: document.getElementById('vars').getAttribute('remoteUrl'),
    wildcard: '%QUERY',
    transform: function (object) {
      var results = object.results
      var suggestions = []
      for (i = 0; i < results.length; i++) {
        suggestions.push({value: results[i].nick, name: results[i].name})
      }
      return suggestions
    },
  }
});

$('#input-nick').typeahead(null, {
  name: 'nick',
  display: 'value',
  source: speakers,
  templates: {
    suggestion: function(data) {
      console.log(data)
      return '<div class="tt-suggestion tt-selectable">' + data.value + ' (' + data.name + ')' + '</div>'
    }
  }
});
