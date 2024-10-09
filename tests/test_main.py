def test_empty():
    from exhibitor.apps import ExhibitorConfig
    assert ExhibitorConfig.name == 'exhibitor'
    assert isinstance(ExhibitorConfig.verbose_name, str)
    assert isinstance(ExhibitorConfig.description, str)
    assert isinstance(ExhibitorConfig.version, str)
    assert ExhibitorConfig.author == 'OpenCraft'
