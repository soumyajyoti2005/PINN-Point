import pytest

def test_torch_autograd():
    try:
        import torch
    except ImportError:
        pytest.skip("torch not installed, skipping ml tests")
        
    # Tiny autograd step
    x = torch.tensor(2.0, requires_grad=True)
    y = x ** 2
    y.backward()
    
    assert x.grad is not None
    assert x.grad.item() == 4.0

