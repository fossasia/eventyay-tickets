var remoteUrls = [];
var urls = null;
fetch(document.getElementById('navigateUrl').getAttribute('remoteUrl')).then((response) => {
  response.json().then(response => {
    remoteUrls = response.results.map(element => {return {value: element.url, name: element.name}})
    urls = new Bloodhound({
      datumTokenizer: Bloodhound.tokenizers.obj.whitespace('name'),
      queryTokenizer: Bloodhound.tokenizers.whitespace,
      local: remoteUrls,
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
  })
})
