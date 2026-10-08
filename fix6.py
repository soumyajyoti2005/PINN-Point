with open('backend/tests/test_dataset.py', 'r') as f:
    content = f.read()

content = content.replace('import pytest\n', 'import pytest\npytest.importorskip("numpy")\n')

with open('backend/tests/test_dataset.py', 'w') as f:
    f.write(content)
