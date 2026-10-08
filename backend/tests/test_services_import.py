def test_network_loader_exposes_main():
    import app.services.network_loader
    assert hasattr(app.services.network_loader, "main")
