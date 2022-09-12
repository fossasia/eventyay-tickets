document.querySelectorAll("input.tokenfield").forEach(field => {
  const initial = JSON.parse(field.dataset["value"])
  const options = JSON.parse(field.dataset["options"])

  var engine = new Bloodhound({
    local: options,
    datumTokenizer: function(d) {
      return Bloodhound.tokenizers.whitespace(d.value);
    },
    queryTokenizer: Bloodhound.tokenizers.whitespace
  });
  engine.initialize();
  $(field).tokenfield({
      typeahead: {
      source: engine.ttAdapter(),
      displayKey: 'label'
    },
  })
})
