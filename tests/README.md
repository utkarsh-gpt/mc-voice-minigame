# Tests

This directory contains tests for the Minecraft Discord Bot.

## Running Tests

**Note:** Make sure you have installed all dependencies first:
```bash
pip install -r requirements.txt
```

### Run all tests:
```bash
pytest
```

### Run with coverage:
```bash
pytest --cov=src --cov-report=html
```

### Run specific test file:
```bash
pytest tests/test_minecraft_rcon.py
```

### Run specific test:
```bash
pytest tests/test_minecraft_rcon.py::TestMinecraftRCON::test_connect_success
```

### Run with verbose output:
```bash
pytest -v
```

## Test Structure

- `test_minecraft_rcon.py` - Tests for RCON connection and command execution

## Writing New Tests

When adding new tests:

1. Create test files with `test_` prefix
2. Use descriptive test names starting with `test_`
3. Use pytest fixtures for setup/teardown
4. Mock external dependencies (like MCRcon) to avoid needing real servers
5. Test both success and failure cases

## Example Test

```python
def test_example():
    """Test description."""
    # Arrange
    client = MinecraftRCON("host", 25575, "password")
    
    # Act
    result = client.some_method()
    
    # Assert
    assert result == expected_value
```
