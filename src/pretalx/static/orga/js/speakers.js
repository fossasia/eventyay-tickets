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
        suggestions.push(results[i].nick)
      }
      return results
    }
  }
});

$('#input-nick').typeahead(null, {
  name: 'nick',
  display: 'value',
  source: speakers
});
