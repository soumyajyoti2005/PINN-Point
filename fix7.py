with open('backend/tests/test_dataset.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for l in lines:
    if l.startswith('import pytest'):
        new_lines.extend([
            'import pytest\n',
            'pytest.importorskip("numpy")\n',
            'pytest.importorskip("pandas")\n',
            'pytest.importorskip("pyarrow")\n',
            'pytest.importorskip("pyswmm")\n'
        ])
    elif l.startswith('pytest.importorskip'):
        pass
    else:
        new_lines.append(l)

with open('backend/tests/test_dataset.py', 'w') as f:
    f.writelines(new_lines)
